"""
API endpoints для Walk-Forward Validation.

Endpoints:
- POST /validation/walk-forward - запуск валидации
- GET /validation/results - список всех результатов
- GET /validation/results/{run_id} - детали конкретной валидации
- GET /validation/latest - последняя валидация
- DELETE /validation/results/{run_id} - удалить результаты
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from pathlib import Path
import json
import glob
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..dependencies import get_db, require_api_key
from ..modeling import walk_forward_cv

router = APIRouter(prefix="/validation", tags=["Validation"])


# ============================
# Pydantic модели
# ============================

class WalkForwardRequest(BaseModel):
    """Запрос на Walk-Forward валидацию"""
    exchange: str = Field("bybit", description="Биржа")
    symbol: str = Field("BTC/USDT", description="Торговая пара")
    timeframe: str = Field("1h", description="Таймфрейм")
    limit: int = Field(3000, description="Количество свечей для загрузки")
    window_train_days: int = Field(30, description="Размер train окна в днях")
    window_test_days: int = Field(7, description="Размер test окна в днях")
    step_days: int = Field(7, description="Шаг смещения окна в днях")
    commission_bps: float = Field(8.0, description="Комиссии в bps")
    slippage_bps: float = Field(5.0, description="Проскальзывание в bps")


class ValidationSummary(BaseModel):
    """Краткая информация о валидации"""
    run_id: str
    timestamp: str
    symbol: str
    timeframe: str
    n_windows: int
    avg_return: float
    avg_sharpe: float
    global_return: float
    profitable_pct: float
    all_criteria_met: bool


class ValidationDetails(BaseModel):
    """Детальная информация о валидации"""
    run_id: str
    config: Dict
    windows: List[Dict]
    global_metrics: Dict
    summary: Dict


# ============================
# Вспомогательные функции
# ============================

def load_validation_results(run_id: str) -> Optional[Dict]:
    """Загружает результаты валидации по run_id"""
    artifacts_dir = Path("artifacts/validation")
    
    # Ищем файл с соответствующим run_id
    pattern = f"walk_forward_{run_id}.json"
    matches = list(artifacts_dir.glob(pattern))
    
    if not matches:
        return None
    
    with open(matches[0], 'r') as f:
        return json.load(f)


def list_all_validations() -> List[Dict]:
    """Возвращает список всех валидаций"""
    artifacts_dir = Path("artifacts/validation")
    
    if not artifacts_dir.exists():
        return []
    
    results = []
    
    for file_path in sorted(artifacts_dir.glob("walk_forward_*.json"), reverse=True):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Извлекаем run_id из имени файла
            run_id = file_path.stem.replace("walk_forward_", "")
            
            # Создаём краткое описание
            config = data.get('config', {})
            summary = data.get('summary', {})
            
            results.append({
                'run_id': run_id,
                'timestamp': config.get('timestamp', run_id),
                'symbol': config.get('symbol', 'N/A'),
                'timeframe': config.get('timeframe', 'N/A'),
                'n_windows': len(data.get('windows', [])),
                'avg_return': summary.get('avg_return', 0),
                'avg_sharpe': summary.get('avg_sharpe', 0),
                'global_return': summary.get('global_return', 0),
                'profitable_pct': summary.get('profitable_pct', 0),
                'all_criteria_met': summary.get('all_criteria_met', False)
            })
            
        except Exception as e:
            print(f"Ошибка чтения {file_path}: {e}")
            continue
    
    return results


def load_historical_data_for_validation(exchange: str, symbol: str, timeframe: str, limit: int):
    """Загружает исторические данные для валидации"""
    import ccxt
    
    exchange_class = getattr(ccxt, exchange)
    exchange_instance = exchange_class({
        'sandbox': False,
        'enableRateLimit': True,
    })
    
    ohlcv = exchange_instance.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    
    return df


def create_features_simple(df_prices):
    """Создаём технические индикаторы (упрощенная версия)"""
    df = df_prices.copy()
    
    # Базовые возвраты
    df['ret_1'] = df['close'].pct_change()
    df['ret_4'] = df['close'].pct_change(4)
    df['ret_24'] = df['close'].pct_change(24)
    df['ret_168'] = df['close'].pct_change(168)
    
    # Moving Averages
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    
    # Crossovers
    df['ema_cross_9_21'] = (df['ema_9'] > df['ema_21']).astype(int)
    df['ema_cross_21_50'] = (df['ema_21'] > df['ema_50']).astype(int)
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    bb_sma = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = bb_sma + (bb_std * 2)
    df['bb_lower'] = bb_sma - (bb_std * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / bb_sma
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr_14'] = true_range.rolling(14).mean()
    df['atr_pct'] = df['atr_14'] / df['close']
    
    # Williams %R
    df['williams_r'] = ((df['high'].rolling(14).max() - df['close']) / 
                       (df['high'].rolling(14).max() - df['low'].rolling(14).min())) * -100
    
    # Volume
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Volatility
    df['volatility_14'] = df['ret_1'].rolling(14).std()
    df['volatility_ratio'] = df['volatility_14'] / df['volatility_14'].rolling(50).mean()
    
    # Momentum
    df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
    df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
    
    # Price ratios
    df['price_vs_sma20'] = df['close'] / df['sma_20'] - 1
    df['price_vs_ema21'] = df['close'] / df['ema_21'] - 1
    
    # Target
    df['future_ret'] = df['close'].shift(-1) / df['close'] - 1
    df['y'] = (df['future_ret'] > 0.001).astype(int)
    
    # Очистка
    df = df.dropna()
    
    return df


# ============================
# API Endpoints
# ============================

@router.post("/walk-forward", response_model=Dict)
async def run_walk_forward_validation(
    request: WalkForwardRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_api_key)
):
    """
    Запускает Walk-Forward валидацию модели.
    
    Метод разбивает датасет на временные окна и обучает модель
    на каждом train окне, тестируя на следующем test окне.
    
    Критерии успеха:
    - Average Return > +3%
    - Average Sharpe > 1.0
    - Std Return < 5%
    - Минимум 60% окон прибыльны
    """
    try:
        # 1. Загружаем данные
        df_prices = load_historical_data_for_validation(
            request.exchange,
            request.symbol,
            request.timeframe,
            request.limit
        )
        
        if df_prices is None or len(df_prices) == 0:
            raise HTTPException(status_code=400, detail="Не удалось загрузить данные")
        
        # 2. Создаём фичи
        df = create_features_simple(df_prices)
        
        if len(df) < 1000:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно данных: {len(df)} строк (нужно минимум 1000)"
            )
        
        # 3. Определяем feature columns
        feature_cols = [col for col in df.columns if col not in [
            'future_ret', 'y', 'open', 'high', 'low', 'close', 'volume'
        ]]
        
        # 4. Конвертируем дни в бары
        time_diff = df.index[1] - df.index[0]
        hours_per_bar = time_diff.total_seconds() / 3600
        bars_per_day = int(24 / hours_per_bar)
        
        window_train = request.window_train_days * bars_per_day
        window_test = request.window_test_days * bars_per_day
        step = request.step_days * bars_per_day
        
        # 5. Запускаем Walk-Forward CV
        results = walk_forward_cv(
            df,
            feature_cols,
            window_train=window_train,
            window_test=window_test,
            step=step,
            inner_valid_ratio=0.2,
            threshold_grid=np.arange(0.45, 0.75, 0.05)
        )
        
        if not results or not results.get('windows'):
            raise HTTPException(status_code=500, detail="Валидация не вернула результаты")
        
        # 6. Анализируем результаты
        windows = results['windows']
        n_windows = len(windows)
        
        returns = [w['test']['total_return'] for w in windows]
        sharpes = [w['test']['sharpe_like'] for w in windows if w['test']['sharpe_like'] is not None]
        
        avg_return = float(np.mean(returns))
        std_return = float(np.std(returns))
        avg_sharpe = float(np.mean(sharpes)) if sharpes else 0
        
        profitable_windows = sum(1 for r in returns if r > 0)
        profitable_pct = (profitable_windows / n_windows) * 100
        
        global_return = results.get('global', {}).get('total_return', 0)
        global_sharpe = results.get('global', {}).get('sharpe_like', 0)
        
        # Критерии успеха
        all_criteria_met = (
            avg_return >= 0.03 and
            avg_sharpe >= 1.0 and
            std_return <= 0.05 and
            profitable_pct >= 60
        )
        
        summary = {
            'avg_return': avg_return,
            'std_return': std_return,
            'avg_sharpe': avg_sharpe,
            'profitable_windows': profitable_windows,
            'profitable_pct': profitable_pct,
            'global_return': global_return,
            'global_sharpe': global_sharpe,
            'all_criteria_met': all_criteria_met
        }
        
        # 7. Сохраняем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = Path(f"artifacts/validation/walk_forward_{timestamp}.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        def convert_to_json_serializable(obj):
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_to_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            return obj
        
        results_serializable = convert_to_json_serializable(results)
        results_serializable['summary'] = summary
        results_serializable['config'] = {
            'window_train_days': request.window_train_days,
            'window_test_days': request.window_test_days,
            'step_days': request.step_days,
            'symbol': request.symbol,
            'timeframe': request.timeframe,
            'timestamp': timestamp
        }
        
        with open(results_file, 'w') as f:
            json.dump(results_serializable, f, indent=2, default=str)
        
        return {
            "success": True,
            "run_id": timestamp,
            "message": "Walk-Forward валидация завершена",
            "summary": summary,
            "n_windows": n_windows,
            "results_file": str(results_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации: {str(e)}")


@router.get("/results", response_model=List[ValidationSummary])
async def get_all_validations(_=Depends(require_api_key)):
    """
    Возвращает список всех выполненных валидаций.
    
    Отсортированы по времени (новые первыми).
    """
    try:
        validations = list_all_validations()
        
        return [
            ValidationSummary(
                run_id=v['run_id'],
                timestamp=v['timestamp'],
                symbol=v['symbol'],
                timeframe=v['timeframe'],
                n_windows=v['n_windows'],
                avg_return=v['avg_return'],
                avg_sharpe=v['avg_sharpe'],
                global_return=v['global_return'],
                profitable_pct=v['profitable_pct'],
                all_criteria_met=v['all_criteria_met']
            )
            for v in validations
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка: {str(e)}")


@router.get("/results/{run_id}", response_model=Dict)
async def get_validation_details(run_id: str, _=Depends(require_api_key)):
    """
    Возвращает детальную информацию о конкретной валидации.
    
    Включает:
    - Конфигурацию валидации
    - Метрики по каждому окну
    - Глобальные метрики
    - Итоговый анализ
    """
    try:
        results = load_validation_results(run_id)
        
        if results is None:
            raise HTTPException(status_code=404, detail=f"Валидация {run_id} не найдена")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")


@router.get("/latest", response_model=Dict)
async def get_latest_validation(_=Depends(require_api_key)):
    """
    Возвращает результаты последней валидации.
    """
    try:
        validations = list_all_validations()
        
        if not validations:
            raise HTTPException(status_code=404, detail="Нет выполненных валидаций")
        
        latest = validations[0]
        results = load_validation_results(latest['run_id'])
        
        if results is None:
            raise HTTPException(status_code=404, detail="Не удалось загрузить последнюю валидацию")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.delete("/results/{run_id}")
async def delete_validation(run_id: str, _=Depends(require_api_key)):
    """
    Удаляет результаты валидации.
    """
    try:
        artifacts_dir = Path("artifacts/validation")
        pattern = f"walk_forward_{run_id}.json"
        matches = list(artifacts_dir.glob(pattern))
        
        if not matches:
            raise HTTPException(status_code=404, detail=f"Валидация {run_id} не найдена")
        
        matches[0].unlink()
        
        return {
            "success": True,
            "message": f"Валидация {run_id} удалена"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")

