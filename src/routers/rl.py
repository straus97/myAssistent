"""
API endpoints для Reinforcement Learning агента (PPO).

Endpoints:
- POST /rl/train - Обучение RL агента
- POST /rl/predict - Предсказание sizing
- POST /rl/predict/hybrid - Hybrid модель (XGBoost + RL)
- GET /rl/models - Список обученных моделей
- GET /rl/evaluate/{model_id} - Оценка производительности
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from pathlib import Path
import logging
import numpy as np
import pandas as pd

from ..dependencies import require_api_key, get_db
from ..rl_agent import (
    train_rl_agent,
    load_rl_agent,
    predict_sizing,
    predict_hybrid_sizing,
    evaluate_rl_agent,
    walk_forward_training,
)
from ..rl_env import create_trading_env
from ..features import build_dataset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rl", tags=["RL Agent"])


# ============================
# Pydantic Models
# ============================

class RLTrainRequest(BaseModel):
    """Запрос на обучение RL агента."""
    exchange: str = Field(..., description="Биржа (bybit, binance)")
    symbol: str = Field(..., description="Торговая пара (BTC/USDT)")
    timeframe: str = Field(..., description="Таймфрейм (1h, 4h, 1d)")
    start_date: str = Field(..., description="Дата начала обучения (YYYY-MM-DD)")
    end_date: str = Field(..., description="Дата окончания обучения (YYYY-MM-DD)")
    total_timesteps: int = Field(100_000, ge=1000, description="Общее количество шагов обучения")
    learning_rate: float = Field(3e-4, gt=0, description="Learning rate")
    initial_capital: float = Field(1000.0, gt=0, description="Начальный капитал")
    commission_bps: float = Field(8.0, ge=0, description="Комиссии в базисных пунктах")
    walk_forward: bool = Field(False, description="Использовать walk-forward training")
    
    class Config:
        json_schema_extra = {
            "example": {
                "exchange": "bybit",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
                "total_timesteps": 100000,
                "learning_rate": 0.0003,
                "initial_capital": 1000.0,
                "commission_bps": 8.0,
                "walk_forward": False,
            }
        }


class RLPredictRequest(BaseModel):
    """Запрос на предсказание sizing."""
    model_path: str = Field(..., description="Путь к обученной модели")
    observation: List[float] = Field(..., description="Текущее состояние (observation)")
    deterministic: bool = Field(True, description="Детерминированное предсказание")


class RLHybridRequest(BaseModel):
    """Запрос на hybrid предсказание (XGBoost + RL)."""
    rl_model_path: str = Field(..., description="Путь к RL модели")
    xgboost_proba: float = Field(..., ge=0.0, le=1.0, description="Вероятность от XGBoost")
    observation: List[float] = Field(..., description="Текущее состояние")
    threshold_buy: float = Field(0.6, ge=0.0, le=1.0, description="Порог для BUY")
    threshold_sell: float = Field(0.4, ge=0.0, le=1.0, description="Порог для SELL")


# ============================
# Endpoints
# ============================

@router.post("/train", dependencies=[Depends(require_api_key)])
def train_rl_endpoint(
    request: RLTrainRequest,
    db: Session = Depends(get_db),
):
    """
    Обучить RL агента (PPO) на исторических данных.
    
    **Процесс:**
    1. Загрузка исторических данных с фичами
    2. Создание Custom Gym Environment
    3. Обучение PPO агента
    4. Сохранение модели в artifacts/rl_models/
    
    **Walk-forward training:**
    - Если `walk_forward=True`, обучение происходит на скользящих окнах
    - Каждое окно: 30 дней обучения → 7 дней тест
    - Более реалистичная оценка производительности
    
    **Пример:**
    ```json
    {
      "exchange": "bybit",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "start_date": "2024-01-01",
      "end_date": "2024-06-01",
      "total_timesteps": 100000
    }
    ```
    """
    logger.info(f"[rl] Starting RL training: {request.exchange} {request.symbol} {request.timeframe}")
    
    try:
        if request.walk_forward:
            # Walk-forward training
            results = walk_forward_training(
                db=db,
                exchange=request.exchange,
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                window_days=30,
                step_days=7,
                total_timesteps_per_window=request.total_timesteps // 3,  # Делим на 3 окна
                learning_rate=request.learning_rate,
                initial_capital=request.initial_capital,
                commission_bps=request.commission_bps,
            )
            
            return {
                "success": True,
                "method": "walk_forward",
                "windows": len(results),
                "results": results,
            }
        
        else:
            # Обычное обучение
            model, metrics = train_rl_agent(
                db=db,
                exchange=request.exchange,
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                total_timesteps=request.total_timesteps,
                learning_rate=request.learning_rate,
                initial_capital=request.initial_capital,
                commission_bps=request.commission_bps,
            )
            
            return {
                "success": True,
                "method": "standard",
                "metrics": metrics,
            }
    
    except Exception as e:
        logger.error(f"[rl] Training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/predict", dependencies=[Depends(require_api_key)])
def predict_rl_endpoint(request: RLPredictRequest):
    """
    Предсказать действие (buy/sell/hold + sizing) на основе observation.
    
    **Observation format:**
    - Features (78+): Технические, новости, on-chain, macro, social
    - Meta metrics (6): equity_pct, max_equity_pct, drawdown, position_ratio, volatility, rolling_sharpe
    
    **Returns:**
    - action_type: 0=hold, 1=buy, 2=sell
    - sizing_pct: Размер позиции (0.0-1.0, доля капитала)
    
    **Пример:**
    ```json
    {
      "model_path": "artifacts/rl_models/ppo_bybit_BTC_USDT_1h_20250110_120000.zip",
      "observation": [0.1, 0.5, ...],  # 84 значения
      "deterministic": true
    }
    ```
    """
    logger.info(f"[rl] Predicting with model: {request.model_path}")
    
    try:
        # Загрузка модели
        model = load_rl_agent(request.model_path)
        
        # Предсказание
        observation = np.array(request.observation, dtype=np.float32)
        action_type, sizing_pct = predict_sizing(model, observation, request.deterministic)
        
        action_map = {0: "hold", 1: "buy", 2: "sell"}
        
        return {
            "success": True,
            "action_type": action_type,
            "action": action_map[action_type],
            "sizing_pct": float(sizing_pct),
            "sizing_description": f"{sizing_pct*100:.1f}% of capital",
        }
    
    except Exception as e:
        logger.error(f"[rl] Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/hybrid", dependencies=[Depends(require_api_key)])
def predict_hybrid_endpoint(request: RLHybridRequest):
    """
    Hybrid предсказание: XGBoost (направление) + RL (sizing).
    
    **Логика:**
    1. XGBoost определяет направление (buy/sell/hold) на основе вероятности
    2. RL агент определяет optimal sizing (если XGBoost дал сигнал)
    3. Если RL согласен с XGBoost → используем RL sizing
    4. Если RL не согласен → консервативный sizing (5%)
    
    **Преимущества:**
    - XGBoost: точное направление (обучен на исторических данных)
    - RL: адаптивный sizing (учитывает текущее состояние equity, риски)
    
    **Пример:**
    ```json
    {
      "rl_model_path": "artifacts/rl_models/ppo_bybit_BTC_USDT_1h_20250110_120000.zip",
      "xgboost_proba": 0.75,
      "observation": [0.1, 0.5, ...],
      "threshold_buy": 0.6,
      "threshold_sell": 0.4
    }
    ```
    """
    logger.info(f"[rl] Hybrid prediction: XGBoost proba={request.xgboost_proba:.3f}")
    
    try:
        # Загрузка RL модели
        rl_model = load_rl_agent(request.rl_model_path)
        
        # Hybrid предсказание
        observation = np.array(request.observation, dtype=np.float32)
        signal, sizing_pct = predict_hybrid_sizing(
            rl_model=rl_model,
            xgboost_proba=request.xgboost_proba,
            observation=observation,
            threshold_buy=request.threshold_buy,
            threshold_sell=request.threshold_sell,
        )
        
        return {
            "success": True,
            "signal": signal,
            "sizing_pct": float(sizing_pct),
            "sizing_description": f"{sizing_pct*100:.1f}% of capital",
            "xgboost_proba": request.xgboost_proba,
            "method": "hybrid",
        }
    
    except Exception as e:
        logger.error(f"[rl] Hybrid prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Hybrid prediction failed: {str(e)}")


@router.get("/models", dependencies=[Depends(require_api_key)])
def list_rl_models():
    """
    Получить список обученных RL моделей.
    
    **Возвращает:**
    - Список моделей в artifacts/rl_models/
    - Для каждой модели: имя, размер, дата создания
    """
    models_dir = Path("artifacts/rl_models")
    
    if not models_dir.exists():
        return {"models": [], "total": 0}
    
    models = []
    for model_path in sorted(models_dir.glob("ppo_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        models.append({
            "name": model_path.name,
            "path": str(model_path),
            "size_mb": round(model_path.stat().st_size / 1024 / 1024, 2),
            "created": model_path.stat().st_mtime,
        })
    
    return {"models": models, "total": len(models)}


@router.get("/evaluate/{model_name}", dependencies=[Depends(require_api_key)])
def evaluate_rl_endpoint(
    model_name: str,
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    start_date: str = "2024-06-01",
    end_date: str = "2024-07-01",
    n_episodes: int = 10,
    db: Session = Depends(get_db),
):
    """
    Оценить производительность RL агента на out-of-sample данных.
    
    **Процесс:**
    1. Загрузка модели
    2. Создание test environment (новые данные)
    3. Запуск n_episodes
    4. Расчёт метрик: avg_reward, avg_equity, best/worst
    
    **Пример:**
    ```
    GET /rl/evaluate/ppo_bybit_BTC_USDT_1h_20250110_120000.zip?n_episodes=10
    ```
    """
    logger.info(f"[rl] Evaluating model: {model_name}")
    
    try:
        # Загрузка модели
        model_path = Path("artifacts/rl_models") / model_name
        if not model_path.exists():
            raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
        
        model = load_rl_agent(str(model_path))
        
        # Построение test датасета
        df, feature_cols = build_dataset(
            db=db,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
        
        if len(df) < 100:
            raise HTTPException(status_code=400, detail="Insufficient test data")
        
        # Создание environment
        env = create_trading_env(df=df)
        
        # Оценка
        metrics = evaluate_rl_agent(model, env, n_episodes=n_episodes)
        
        return {
            "success": True,
            "model_name": model_name,
            "test_period": f"{start_date} → {end_date}",
            "n_episodes": n_episodes,
            "metrics": metrics,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[rl] Evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

