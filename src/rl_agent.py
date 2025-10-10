"""
RL Agent для динамического position sizing с использованием Stable-Baselines3 PPO.

Функционал:
- Обучение PPO агента на историческ

их данных
- Walk-forward training (30-дневные окна)
- Сохранение/загрузка обученных моделей
- Предсказание optimal sizing для торговых сигналов
- Интеграция с XGBoost (Hybrid модель)

Hybrid подход:
- XGBoost → направление (buy/sell probability)
- RL Agent → sizing (0.01-0.20 от капитала)
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

from .rl_env import CryptoTradingEnv, create_trading_env
from .features import build_dataset

logger = logging.getLogger(__name__)


class TensorboardCallback(BaseCallback):
    """
    Callback для логирования дополнительных метрик в Tensorboard.
    """
    
    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
    
    def _on_step(self) -> bool:
        # Логируем метрики каждый шаг
        if len(self.locals.get("infos", [])) > 0:
            info = self.locals["infos"][0]
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
                self.episode_lengths.append(info["episode"]["l"])
                
                # Логируем в tensorboard
                self.logger.record("train/episode_reward", info["episode"]["r"])
                self.logger.record("train/episode_length", info["episode"]["l"])
        
        return True


def train_rl_agent(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    total_timesteps: int = 100_000,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 64,
    n_epochs: int = 10,
    initial_capital: float = 1000.0,
    commission_bps: float = 8.0,
    model_save_path: Optional[str] = None,
    tensorboard_log: Optional[str] = None,
) -> Tuple[PPO, Dict]:
    """
    Обучить RL агента на исторических данных.
    
    Args:
        db: SQLAlchemy session
        exchange: Биржа (bybit, binance)
        symbol: Торговая пара (BTC/USDT)
        timeframe: Таймфрейм (1h, 4h, 1d)
        start_date: Дата начала обучения
        end_date: Дата окончания обучения
        total_timesteps: Общее количество шагов обучения
        learning_rate: Learning rate для PPO
        n_steps: Количество шагов до обновления policy
        batch_size: Размер батча
        n_epochs: Количество эпох обновления policy
        initial_capital: Начальный капитал
        commission_bps: Комиссии
        model_save_path: Путь для сохранения модели
        tensorboard_log: Путь для логов Tensorboard
    
    Returns:
        model: Обученная PPO модель
        metrics: Метрики обучения
    """
    logger.info(f"[rl_agent] Starting RL training: {exchange} {symbol} {timeframe}")
    logger.info(f"[rl_agent] Training period: {start_date} → {end_date}")
    logger.info(f"[rl_agent] Total timesteps: {total_timesteps}")
    
    # 1. Построение датасета
    logger.info("[rl_agent] Building dataset with features...")
    try:
        df, feature_cols = build_dataset(
            db=db,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
    except Exception as e:
        logger.error(f"[rl_agent] Failed to build dataset: {e}")
        raise
    
    if df.empty:
        raise ValueError("Empty dataset")
    
    # Фильтрация по датам
    df = df.sort_values("timestamp").reset_index(drop=True)
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    
    if len(df) < 100:
        raise ValueError(f"Insufficient data for training ({len(df)} rows)")
    
    logger.info(f"[rl_agent] Dataset ready: {len(df)} rows, {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    # 2. Создание environment
    env = create_trading_env(
        df=df,
        initial_capital=initial_capital,
        commission_bps=commission_bps,
    )
    
    # Оборачиваем в DummyVecEnv (требуется для SB3)
    vec_env = DummyVecEnv([lambda: env])
    
    # 3. Создание PPO агента
    logger.info("[rl_agent] Initializing PPO agent...")
    model = PPO(
        policy="MlpPolicy",
        env=vec_env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,  # Entropy coefficient для exploration
        vf_coef=0.5,  # Value function coefficient
        max_grad_norm=0.5,
        verbose=1,
        tensorboard_log=tensorboard_log,
    )
    
    # 4. Обучение
    logger.info("[rl_agent] Starting training...")
    callback = TensorboardCallback()
    
    model.learn(
        total_timesteps=total_timesteps,
        callback=callback,
        progress_bar=True,
    )
    
    logger.info("[rl_agent] Training completed!")
    
    # 5. Сохранение модели
    if model_save_path is None:
        models_dir = Path("artifacts/rl_models")
        models_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_save_path = str(models_dir / f"ppo_{exchange}_{symbol.replace('/', '_')}_{timeframe}_{timestamp}.zip")
    
    model.save(model_save_path)
    logger.info(f"[rl_agent] Model saved to {model_save_path}")
    
    # 6. Метрики
    metrics = {
        "total_timesteps": total_timesteps,
        "final_reward": float(callback.episode_rewards[-1]) if callback.episode_rewards else 0.0,
        "avg_reward": float(np.mean(callback.episode_rewards)) if callback.episode_rewards else 0.0,
        "avg_episode_length": float(np.mean(callback.episode_lengths)) if callback.episode_lengths else 0.0,
        "model_path": model_save_path,
        "training_duration_steps": len(df),
    }
    
    logger.info(f"[rl_agent] Training metrics: Avg Reward={metrics['avg_reward']:.3f}, Avg Length={metrics['avg_episode_length']:.1f}")
    
    return model, metrics


def load_rl_agent(model_path: str) -> PPO:
    """
    Загрузить обученную PPO модель.
    
    Args:
        model_path: Путь к сохранённой модели (.zip)
    
    Returns:
        model: Загруженная PPO модель
    """
    logger.info(f"[rl_agent] Loading RL model from {model_path}")
    model = PPO.load(model_path)
    return model


def predict_sizing(
    model: PPO,
    observation: np.ndarray,
    deterministic: bool = True,
) -> Tuple[int, float]:
    """
    Предсказать действие (buy/sell/hold + sizing) на основе observation.
    
    Args:
        model: Обученная PPO модель
        observation: Текущее состояние (observation из environment)
        deterministic: Детерминированное предсказание (без exploration)
    
    Returns:
        action_type: 0=hold, 1=buy, 2=sell
        sizing_pct: Размер позиции (0.0-1.0)
    """
    action, _states = model.predict(observation, deterministic=deterministic)
    
    # action = [action_type, sizing (0-100)]
    action_type = int(action[0])
    sizing_pct = float(action[1]) / 100.0
    
    return action_type, sizing_pct


def predict_hybrid_sizing(
    rl_model: PPO,
    xgboost_proba: float,
    observation: np.ndarray,
    threshold_buy: float = 0.6,
    threshold_sell: float = 0.4,
) -> Tuple[str, float]:
    """
    Hybrid модель: XGBoost (направление) + RL (sizing).
    
    Логика:
    1. XGBoost определяет направление (buy/sell/hold)
    2. RL агент определяет sizing (если XGBoost дал сигнал)
    
    Args:
        rl_model: Обученная PPO модель
        xgboost_proba: Вероятность от XGBoost (0.0-1.0)
        observation: Текущее состояние
        threshold_buy: Порог для BUY сигнала
        threshold_sell: Порог для SELL сигнала
    
    Returns:
        signal: "buy" / "sell" / "hold"
        sizing_pct: Размер позиции (0.0-1.0)
    """
    # 1. XGBoost решает направление
    if xgboost_proba >= threshold_buy:
        xgb_signal = "buy"
    elif xgboost_proba <= threshold_sell:
        xgb_signal = "sell"
    else:
        xgb_signal = "hold"
    
    # 2. RL агент решает sizing
    if xgb_signal != "hold":
        # Получаем action от RL
        action_type, rl_sizing = predict_sizing(rl_model, observation, deterministic=True)
        
        # Если RL согласен с XGBoost, используем его sizing
        if (xgb_signal == "buy" and action_type == 1) or (xgb_signal == "sell" and action_type == 2):
            sizing_pct = rl_sizing
        else:
            # Если RL не согласен, используем консервативный sizing
            sizing_pct = 0.05  # 5% капитала
    else:
        # HOLD - нет позиции
        sizing_pct = 0.0
    
    return xgb_signal, sizing_pct


def walk_forward_training(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    window_days: int = 30,
    step_days: int = 7,
    total_timesteps_per_window: int = 50_000,
    **kwargs
) -> list[Dict]:
    """
    Walk-forward обучение RL агента.
    
    Процесс:
    1. Разбиваем данные на окна (window_days)
    2. Обучаем агента на каждом окне
    3. Тестируем на следующем окне (out-of-sample)
    4. Двигаем окно вперёд (step_days)
    
    Args:
        db: SQLAlchemy session
        exchange, symbol, timeframe: Параметры данных
        start_date, end_date: Период
        window_days: Размер обучающего окна (дни)
        step_days: Шаг между окнами (дни)
        total_timesteps_per_window: Шагов обучения на окно
        **kwargs: Дополнительные параметры для train_rl_agent
    
    Returns:
        results: Список результатов для каждого окна
    """
    logger.info(f"[rl_agent] Starting walk-forward training: {window_days}d windows, {step_days}d step")
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    results = []
    current_start = start
    window_id = 0
    
    while current_start + pd.Timedelta(days=window_days) < end:
        window_end = current_start + pd.Timedelta(days=window_days)
        test_end = window_end + pd.Timedelta(days=step_days)
        
        logger.info(f"\n[rl_agent] === Window {window_id} ===")
        logger.info(f"[rl_agent] Train: {current_start.date()} → {window_end.date()}")
        logger.info(f"[rl_agent] Test: {window_end.date()} → {test_end.date()}")
        
        # Обучение на окне
        try:
            model, metrics = train_rl_agent(
                db=db,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                start_date=str(current_start.date()),
                end_date=str(window_end.date()),
                total_timesteps=total_timesteps_per_window,
                **kwargs
            )
            
            results.append({
                "window_id": window_id,
                "train_start": str(current_start.date()),
                "train_end": str(window_end.date()),
                "test_start": str(window_end.date()),
                "test_end": str(test_end.date()),
                "metrics": metrics,
            })
        
        except Exception as e:
            logger.error(f"[rl_agent] Failed to train window {window_id}: {e}")
        
        # Двигаем окно
        current_start += pd.Timedelta(days=step_days)
        window_id += 1
    
    logger.info(f"\n[rl_agent] Walk-forward completed: {len(results)} windows")
    
    return results


def evaluate_rl_agent(
    model: PPO,
    env: CryptoTradingEnv,
    n_episodes: int = 10,
) -> Dict:
    """
    Оценить производительность RL агента.
    
    Args:
        model: Обученная PPO модель
        env: Trading environment
        n_episodes: Количество эпизодов для оценки
    
    Returns:
        metrics: Метрики производительности
    """
    logger.info(f"[rl_agent] Evaluating agent for {n_episodes} episodes...")
    
    episode_rewards = []
    episode_lengths = []
    final_equities = []
    
    for episode in range(n_episodes):
        obs, _ = env.reset()
        done = False
        episode_reward = 0
        step_count = 0
        
        while not done:
            action, _states = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            step_count += 1
            done = terminated or truncated
        
        episode_rewards.append(episode_reward)
        episode_lengths.append(step_count)
        final_equities.append(info["equity"])
        
        logger.info(f"[rl_agent] Episode {episode+1}/{n_episodes}: Reward={episode_reward:.3f}, Equity=${info['equity']:.2f}")
    
    metrics = {
        "avg_reward": float(np.mean(episode_rewards)),
        "std_reward": float(np.std(episode_rewards)),
        "avg_length": float(np.mean(episode_lengths)),
        "avg_final_equity": float(np.mean(final_equities)),
        "best_reward": float(np.max(episode_rewards)),
        "worst_reward": float(np.min(episode_rewards)),
    }
    
    logger.info(f"[rl_agent] Evaluation completed: Avg Reward={metrics['avg_reward']:.3f}, Avg Equity=${metrics['avg_final_equity']:.2f}")
    
    return metrics

