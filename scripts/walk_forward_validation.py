#!/usr/bin/env python3
"""
Walk-Forward Validation для защиты от overfitting.

Метод:
1. Разбиваем датасет на временные окна (30 дней train + 7 дней test)
2. Обучаем модель на каждом train окне
3. Тестируем на следующем test окне
4. Агрегируем метрики по всем окнам

Критерии успеха:
- Average Return > +3%
- Average Sharpe > 1.0
- Std Return < 5% (стабильность)
- Минимум 60% окон прибыльны
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import ccxt
from typing import Dict, List

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modeling import walk_forward_cv
from src.features import build_dataset
from src.db import SessionLocal


def load_historical_data(exchange='bybit', symbol='BTC/USDT', timeframe='1h', limit=3000):
    """Загружаем исторические данные для walk-forward валидации"""
    print(f"[DATA] Загружаем данные: {symbol} {timeframe} (последние {limit} свечей)")
    
    try:
        exchange_class = getattr(ccxt, exchange)
        exchange_instance = exchange_class({
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        ohlcv = exchange_instance.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        print(f"OK: Загружено {len(df)} свечей")
        print(f"   Период: {df.index[0]} - {df.index[-1]}")
        print(f"   Диапазон цен: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        
        return df
        
    except Exception as e:
        print(f"ERROR: Ошибка загрузки данных: {e}")
        return None


def create_features_for_validation(df_prices):
    """Создаём фичи для валидации (упрощенная версия без БД)"""
    print("[FEATURES] Создаём технические индикаторы...")
    
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
    
    # EMA Crossovers
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
    
    # Target variable
    df['future_ret'] = df['close'].shift(-1) / df['close'] - 1
    df['y'] = (df['future_ret'] > 0.001).astype(int)
    
    # Очистка
    df = df.dropna()
    
    print(f"OK: Создано {len(df.columns)} фичей, {len(df)} строк после очистки")
    
    return df


def run_walk_forward_validation(
    df: pd.DataFrame,
    window_train_days: int = 30,
    window_test_days: int = 7,
    step_days: int = 7,
    commission_bps: float = 8.0,
    slippage_bps: float = 5.0
) -> Dict:
    """
    Запускает Walk-Forward валидацию.
    
    Args:
        df: DataFrame с фичами и target
        window_train_days: Размер train окна в днях
        window_test_days: Размер test окна в днях
        step_days: Шаг смещения окна в днях
        commission_bps: Комиссии в базисных пунктах
        slippage_bps: Проскальзывание в базисных пунктах
    
    Returns:
        Dict с результатами валидации
    """
    print(f"\n[VALIDATION] Walk-Forward Validation")
    print(f"=" * 60)
    print(f"Параметры:")
    print(f"  Train window: {window_train_days} дней")
    print(f"  Test window: {window_test_days} дней")
    print(f"  Step: {step_days} дней")
    print(f"  Commission: {commission_bps} bps")
    print(f"  Slippage: {slippage_bps} bps")
    
    # Определяем feature columns
    feature_cols = [col for col in df.columns if col not in [
        'future_ret', 'y', 'open', 'high', 'low', 'close', 'volume'
    ]]
    
    print(f"\nФичи: {len(feature_cols)} колонок")
    print(f"Датасет: {len(df)} строк")
    
    # Определяем временной интервал между наблюдениями
    time_diff = df.index[1] - df.index[0]
    hours_per_bar = time_diff.total_seconds() / 3600
    bars_per_day = int(24 / hours_per_bar)
    
    print(f"Таймфрейм: {hours_per_bar:.1f}h ({bars_per_day} баров/день)")
    
    # Конвертируем дни в количество баров
    window_train = window_train_days * bars_per_day
    window_test = window_test_days * bars_per_day
    step = step_days * bars_per_day
    
    print(f"\nКонвертировано в бары:")
    print(f"  Train window: {window_train} баров")
    print(f"  Test window: {window_test} баров")
    print(f"  Step: {step} баров")
    
    # Используем существующую функцию walk_forward_cv из modeling.py
    try:
        results = walk_forward_cv(
            df,
            feature_cols,
            window_train=window_train,
            window_test=window_test,
            step=step,
            inner_valid_ratio=0.2,
            threshold_grid=np.arange(0.45, 0.75, 0.05)
        )
        
        print(f"\nOK: Walk-Forward валидация завершена")
        
        return results
        
    except Exception as e:
        print(f"\nERROR: Ошибка валидации: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_results(results: Dict):
    """Анализируем и выводим результаты валидации"""
    # walk_forward_cv возвращает 'folds', а не 'windows'
    folds = results.get('folds', [])
    if not folds:
        print("ERROR: Нет результатов для анализа (folds пустой)")
        return
    
    # Преобразуем folds в windows для единообразия
    windows = []
    for fold in folds:
        windows.append({
            'train_end': fold.get('end', 'N/A'),
            'test': {
                'total_return': fold.get('total_return', 0),
                'sharpe_like': fold.get('sharpe_like', None),
                'accuracy': fold.get('accuracy', 0)
            }
        })
    
    n_windows = len(windows)
    
    print(f"\n[RESULTS] АНАЛИЗ РЕЗУЛЬТАТОВ")
    print(f"=" * 60)
    print(f"Количество окон: {n_windows}")
    
    # Собираем метрики по окнам
    returns = [w['test']['total_return'] for w in windows]
    sharpes = [w['test']['sharpe_like'] for w in windows if w['test']['sharpe_like'] is not None]
    accuracies = [w['test']['accuracy'] for w in windows]
    
    # Агрегированные метрики
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    avg_sharpe = np.mean(sharpes) if sharpes else 0
    avg_accuracy = np.mean(accuracies)
    
    profitable_windows = sum(1 for r in returns if r > 0)
    profitable_pct = (profitable_windows / n_windows) * 100
    
    # Глобальные метрики (из агрегированной equity curve)
    global_return = results.get('global', {}).get('total_return', 0)
    global_sharpe = results.get('global', {}).get('sharpe_like', 0)
    
    print(f"\n[AGGREGATE] Агрегированные метрики (по окнам):")
    print(f"  Average Return: {avg_return:.4f} ({avg_return*100:.2f}%)")
    print(f"  Std Return: {std_return:.4f} ({std_return*100:.2f}%)")
    print(f"  Average Sharpe: {avg_sharpe:.4f}")
    print(f"  Average Accuracy: {avg_accuracy:.4f} ({avg_accuracy*100:.2f}%)")
    print(f"  Profitable Windows: {profitable_windows}/{n_windows} ({profitable_pct:.1f}%)")
    
    print(f"\n[GLOBAL] Глобальные метрики (вся equity curve):")
    print(f"  Total Return: {global_return:.4f} ({global_return*100:.2f}%)")
    print(f"  Global Sharpe: {global_sharpe:.4f}")
    
    # Лучшее и худшее окно
    best_window_idx = np.argmax(returns)
    worst_window_idx = np.argmin(returns)
    
    print(f"\n[BEST] Лучшее окно (#{best_window_idx + 1}):")
    print(f"  Return: {returns[best_window_idx]*100:.2f}%")
    print(f"  Period: {windows[best_window_idx].get('train_end', 'N/A')}")
    
    print(f"\n[WORST] Худшее окно (#{worst_window_idx + 1}):")
    print(f"  Return: {returns[worst_window_idx]*100:.2f}%")
    print(f"  Period: {windows[worst_window_idx].get('train_end', 'N/A')}")
    
    # Оценка критериев успеха
    print(f"\n[CRITERIA] ОЦЕНКА КРИТЕРИЕВ УСПЕХА:")
    print(f"=" * 60)
    
    target_avg_return = 0.03  # 3%
    target_sharpe = 1.0
    target_std = 0.05  # 5%
    target_profitable_pct = 60  # 60%
    
    return_ok = avg_return >= target_avg_return
    sharpe_ok = avg_sharpe >= target_sharpe
    std_ok = std_return <= target_std
    profitable_ok = profitable_pct >= target_profitable_pct
    
    print(f"  Average Return >= {target_avg_return*100}%: {'PASS' if return_ok else 'FAIL'} ({avg_return*100:.2f}%)")
    print(f"  Average Sharpe >= {target_sharpe}: {'PASS' if sharpe_ok else 'FAIL'} ({avg_sharpe:.2f})")
    print(f"  Std Return <= {target_std*100}%: {'PASS' if std_ok else 'FAIL'} ({std_return*100:.2f}%)")
    print(f"  Profitable Windows >= {target_profitable_pct}%: {'PASS' if profitable_ok else 'FAIL'} ({profitable_pct:.1f}%)")
    
    all_criteria_met = return_ok and sharpe_ok and std_ok and profitable_ok
    
    if all_criteria_met:
        print(f"\n[SUCCESS] ВСЕ КРИТЕРИИ ДОСТИГНУТЫ! Модель устойчива к overfitting!")
    else:
        print(f"\n[WARNING] Не все критерии достигнуты. Модель требует улучшений.")
        
        if not return_ok:
            print(f"   > Увеличить доходность (текущая {avg_return*100:.2f}% < цель {target_avg_return*100}%)")
        if not sharpe_ok:
            print(f"   > Улучшить risk-adjusted returns (Sharpe {avg_sharpe:.2f} < цель {target_sharpe})")
        if not std_ok:
            print(f"   > Снизить нестабильность (Std {std_return*100:.2f}% > цель {target_std*100}%)")
        if not profitable_ok:
            print(f"   > Увеличить долю прибыльных окон ({profitable_pct:.1f}% < цель {target_profitable_pct}%)")
    
    return {
        'avg_return': avg_return,
        'std_return': std_return,
        'avg_sharpe': avg_sharpe,
        'avg_accuracy': avg_accuracy,
        'profitable_pct': profitable_pct,
        'global_return': global_return,
        'global_sharpe': global_sharpe,
        'all_criteria_met': all_criteria_met
    }


def main():
    """Основная функция"""
    print("=" * 60)
    print("[WFV] Walk-Forward Validation")
    print("=" * 60)
    
    # 1. Загружаем данные
    print("\n[1/4] Загрузка данных...")
    df_prices = load_historical_data(
        exchange='bybit',
        symbol='BTC/USDT',
        timeframe='1h',
        limit=5000  # ~208 дней для 1h
    )
    
    if df_prices is None:
        print("ERROR: Не удалось загрузить данные")
        return
    
    # 2. Создаём фичи
    print("\n[2/4] Создание фичей...")
    df = create_features_for_validation(df_prices)
    
    if len(df) < 800:
        print(f"ERROR: Недостаточно данных: {len(df)} строк (нужно минимум 800)")
        return
    
    # 3. Запускаем Walk-Forward валидацию
    print("\n[3/4] Запуск валидации...")
    results = run_walk_forward_validation(
        df,
        window_train_days=20,  # 20 дней обучения (480 баров для 1h)
        window_test_days=5,    # 5 дней тестирования (120 баров)
        step_days=5,           # Сдвиг на 5 дней
        commission_bps=8.0,
        slippage_bps=5.0
    )
    
    if results is None:
        print("ERROR: Валидация не выполнена")
        return
    
    # 4. Анализируем результаты
    print("\n[4/4] Анализ результатов...")
    summary = analyze_results(results)
    
    if summary is None:
        print("ERROR: Не удалось проанализировать результаты")
        return
    
    # 5. Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"artifacts/validation/walk_forward_{timestamp}.json"
    
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    
    # Подготовка данных для сохранения (конвертация numpy types)
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
    
    # Добавляем 'windows' как алиас для 'folds' для обратной совместимости
    if 'folds' in results_serializable and 'windows' not in results_serializable:
        results_serializable['windows'] = results_serializable['folds']
    
    results_serializable['summary'] = summary
    results_serializable['config'] = {
        'window_train_days': 20,
        'window_test_days': 5,
        'step_days': 5,
        'symbol': 'BTC/USDT',
        'timeframe': '1h',
        'timestamp': timestamp
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_serializable, f, indent=2, default=str)
    
    print(f"\n[SAVE] Результаты сохранены: {results_file}")
    
    # Итоговое сообщение
    print(f"\n{'='*60}")
    if summary.get('all_criteria_met'):
        print("[SUCCESS] ВАЛИДАЦИЯ УСПЕШНА! Модель готова к production.")
    else:
        print("[WARNING] ТРЕБУЕТСЯ УЛУЧШЕНИЕ. Модель не прошла все критерии.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

