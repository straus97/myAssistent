"""
RL (Reinforcement Learning) Router

API endpoints для обучения и inference PPO-агента.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.dependencies import require_api_key
from src.rl_agent import RLAgent, load_latest_rl_model
from src.prices import fetch_ohlcv
from src.features import build_dataset_for_rl
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rl", tags=["RL"])


# === Request/Response Models ===

class TrainRequest(BaseModel):
    """Запрос на обучение RL-агента."""
    exchange: str = Field(..., description="Биржа (bybit, binance)")
    symbol: str = Field(..., description="Символ (BTC/USDT)")
    timeframe: str = Field(..., description="Таймфрейм (1h, 4h, 1d)")
    start_date: Optional[str] = Field(None, description="Дата начала (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Дата окончания (YYYY-MM-DD)")
    initial_capital: float = Field(1000.0, description="Начальный капитал")
    total_timesteps: int = Field(100000, description="Количество шагов обучения")
    learning_rate: float = Field(3e-4, description="Learning rate")
    n_steps: int = Field(2048, description="Шагов на rollout")
    batch_size: int = Field(64, description="Batch size")


class PredictRequest(BaseModel):
    """Запрос на inference."""
    exchange: str = Field(..., description="Биржа")
    symbol: str = Field(..., description="Символ")
    timeframe: str = Field(..., description="Таймфрейм")
    model_path: Optional[str] = Field(None, description="Путь к модели (опционально, иначе последняя)")
    start_date: Optional[str] = Field(None, description="Дата начала")
    end_date: Optional[str] = Field(None, description="Дата окончания")
    initial_capital: float = Field(1000.0, description="Начальный капитал")


class PerformanceRequest(BaseModel):
    """Запрос на оценку производительности."""
    exchange: str = Field(..., description="Биржа")
    symbol: str = Field(..., description="Символ")
    timeframe: str = Field(..., description="Таймфрейм")
    model_path: Optional[str] = Field(None, description="Путь к модели")
    n_eval_episodes: int = Field(10, description="Количество эпизодов для оценки")
    start_date: Optional[str] = Field(None, description="Дата начала")
    end_date: Optional[str] = Field(None, description="Дата окончания")


# === API Endpoints ===

@router.post("/train")
def train_rl_agent(req: TrainRequest, _=Depends(require_api_key)):
    """
    Обучение PPO-агента для динамического sizing.
    
    Процесс:
    1. Загрузка OHLCV данных
    2. Построение датасета с фичами
    3. Обучение PPO модели (Stable-Baselines3)
    4. Сохранение в artifacts/rl_models/
    
    Example:
        ```bash
        POST /rl/train
        {
          "exchange": "bybit",
          "symbol": "BTC/USDT",
          "timeframe": "1h",
          "start_date": "2024-01-01",
          "end_date": "2025-01-01",
          "initial_capital": 1000,
          "total_timesteps": 100000
        }
        ```
    """
    try:
        logger.info(f"Training RL agent: {req.exchange} {req.symbol} {req.timeframe}")
        
        # 1. Загрузка данных
        logger.info("Fetching OHLCV data...")
        prices_df = fetch_ohlcv(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            since=req.start_date,
            limit=10000,
        )
        
        if prices_df.empty:
            raise HTTPException(400, "No OHLCV data fetched")
        
        # Фильтрация по датам
        if req.start_date:
            prices_df = prices_df[prices_df["timestamp"] >= req.start_date]
        if req.end_date:
            prices_df = prices_df[prices_df["timestamp"] <= req.end_date]
        
        if len(prices_df) < 100:
            raise HTTPException(400, f"Insufficient data: {len(prices_df)} rows")
        
        logger.info(f"Loaded {len(prices_df)} OHLCV bars")
        
        # 2. Построение датасета с фичами
        logger.info("Building dataset with features...")
        df = build_dataset_for_rl(
            prices_df=prices_df,
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
        )
        
        logger.info(f"Dataset built: {len(df)} rows, {len(df.columns)} features")
        
        # 3. Обучение RL-агента
        agent = RLAgent()
        
        metrics = agent.train(
            df=df,
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            initial_capital=req.initial_capital,
            total_timesteps=req.total_timesteps,
            learning_rate=req.learning_rate,
            n_steps=req.n_steps,
            batch_size=req.batch_size,
        )
        
        return {
            "status": "success",
            "message": "RL agent trained successfully",
            "metrics": metrics,
        }
    
    except Exception as e:
        logger.error(f"Failed to train RL agent: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.post("/predict")
def predict_with_rl(req: PredictRequest, _=Depends(require_api_key)):
    """
    Inference с использованием обученного RL-агента.
    
    Возвращает:
        - actions: Список действий (direction, sizing)
        - equity_curve: Кривая капитала
        - trades: История сделок
        - metrics: Итоговые метрики (return, sharpe, max_dd, etc.)
    
    Example:
        ```bash
        POST /rl/predict
        {
          "exchange": "bybit",
          "symbol": "BTC/USDT",
          "timeframe": "1h",
          "model_path": "artifacts/rl_models/ppo_bybit_BTC_USDT_1h_20250101_120000.zip"
        }
        ```
    """
    try:
        logger.info(f"RL prediction: {req.exchange} {req.symbol} {req.timeframe}")
        
        # 1. Определение пути к модели
        if req.model_path:
            model_path = req.model_path
        else:
            # Загрузка последней модели
            model_path = load_latest_rl_model(req.exchange, req.symbol, req.timeframe)
            if not model_path:
                raise HTTPException(404, f"No trained model found for {req.exchange} {req.symbol} {req.timeframe}")
        
        if not Path(model_path).exists():
            raise HTTPException(404, f"Model not found: {model_path}")
        
        logger.info(f"Using model: {model_path}")
        
        # 2. Загрузка данных
        prices_df = fetch_ohlcv(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            since=req.start_date,
            limit=10000,
        )
        
        if prices_df.empty:
            raise HTTPException(400, "No OHLCV data fetched")
        
        # Фильтрация по датам
        if req.start_date:
            prices_df = prices_df[prices_df["timestamp"] >= req.start_date]
        if req.end_date:
            prices_df = prices_df[prices_df["timestamp"] <= req.end_date]
        
        # 3. Построение датасета
        df = build_dataset_for_rl(
            prices_df=prices_df,
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
        )
        
        # 4. Загрузка агента
        agent = RLAgent()
        agent.load(model_path)
        
        # 5. Inference
        results = agent.predict(df=df, initial_capital=req.initial_capital)
        
        return {
            "status": "success",
            "model_path": model_path,
            "results": results,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to predict with RL: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.post("/performance")
def evaluate_rl_performance(req: PerformanceRequest, _=Depends(require_api_key)):
    """
    Оценка производительности RL-агента на тестовых данных.
    
    Возвращает агрегированные метрики (mean, std) по нескольким эпизодам.
    
    Example:
        ```bash
        POST /rl/performance
        {
          "exchange": "bybit",
          "symbol": "BTC/USDT",
          "timeframe": "1h",
          "n_eval_episodes": 10
        }
        ```
    """
    try:
        logger.info(f"Evaluating RL performance: {req.exchange} {req.symbol} {req.timeframe}")
        
        # 1. Определение модели
        if req.model_path:
            model_path = req.model_path
        else:
            model_path = load_latest_rl_model(req.exchange, req.symbol, req.timeframe)
            if not model_path:
                raise HTTPException(404, "No trained model found")
        
        if not Path(model_path).exists():
            raise HTTPException(404, f"Model not found: {model_path}")
        
        # 2. Загрузка данных
        prices_df = fetch_ohlcv(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            since=req.start_date,
            limit=10000,
        )
        
        # Фильтрация
        if req.start_date:
            prices_df = prices_df[prices_df["timestamp"] >= req.start_date]
        if req.end_date:
            prices_df = prices_df[prices_df["timestamp"] <= req.end_date]
        
        # 3. Построение датасета
        df = build_dataset_for_rl(
            prices_df=prices_df,
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
        )
        
        # 4. Загрузка агента
        agent = RLAgent()
        agent.load(model_path)
        
        # 5. Оценка
        metrics = agent.evaluate(df=df, n_eval_episodes=req.n_eval_episodes)
        
        return {
            "status": "success",
            "model_path": model_path,
            "n_eval_episodes": req.n_eval_episodes,
            "metrics": metrics,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to evaluate RL performance: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/models")
def list_rl_models(_=Depends(require_api_key)):
    """
    Список обученных RL моделей.
    
    Returns:
        List[Dict] с информацией о моделях (name, size, modified_at)
    """
    try:
        model_dir = Path("artifacts/rl_models")
        
        if not model_dir.exists():
            return {"models": []}
        
        models = []
        for model_file in model_dir.glob("ppo_*.zip"):
            stat = model_file.stat()
            models.append({
                "name": model_file.name,
                "path": str(model_file),
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        
        # Сортировка по дате (новые сверху)
        models.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {"models": models}
    
    except Exception as e:
        logger.error(f"Failed to list RL models: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))
