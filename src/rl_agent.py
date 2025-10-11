"""
RL Agent для динамического sizing позиций (PPO).

Обучение и inference с использованием Stable-Baselines3.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from src.rl_env import CryptoTradingEnv, create_trading_env

logger = logging.getLogger(__name__)


class TensorboardCallback(BaseCallback):
    """Custom callback для логирования метрик в Tensorboard."""
    
    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
    
    def _on_step(self) -> bool:
        """Вызывается на каждом шаге."""
        # Проверка завершения эпизода
        if self.locals.get("dones"):
            for i, done in enumerate(self.locals["dones"]):
                if done:
                    # Логирование метрик эпизода
                    info = self.locals["infos"][i]
                    if "episode" in info:
                        ep_reward = info["episode"]["r"]
                        ep_length = info["episode"]["l"]
                        
                        self.episode_rewards.append(ep_reward)
                        self.episode_lengths.append(ep_length)
                        
                        # Запись в tensorboard
                        self.logger.record("rollout/ep_reward_mean", np.mean(self.episode_rewards[-100:]))
                        self.logger.record("rollout/ep_length_mean", np.mean(self.episode_lengths[-100:]))
        
        return True


class RLAgent:
    """
    RL Agent для крипто-трейдинга (PPO).
    
    Гибридная модель:
        - XGBoost → направление (buy/sell probability)
        - RL Agent → sizing (динамический размер позиции)
    """
    
    def __init__(
        self,
        model_dir: str = "artifacts/rl_models",
        tensorboard_dir: str = "artifacts/tensorboard",
    ):
        """
        Args:
            model_dir: Директория для сохранения моделей
            tensorboard_dir: Директория для Tensorboard логов
        """
        self.model_dir = Path(model_dir)
        self.tensorboard_dir = Path(tensorboard_dir)
        
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.tensorboard_dir.mkdir(parents=True, exist_ok=True)
        
        self.model: Optional[PPO] = None
        self.env: Optional[CryptoTradingEnv] = None
    
    def train(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        timeframe: str,
        initial_capital: float = 1000.0,
        total_timesteps: int = 100000,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        verbose: int = 1,
    ) -> Dict[str, Any]:
        """
        Обучение PPO агента.
        
        Args:
            df: DataFrame с OHLCV + features (должен быть подготовлен через src/features.py)
            exchange: Биржа (для сохранения)
            symbol: Символ (для сохранения)
            timeframe: Таймфрейм (для сохранения)
            initial_capital: Начальный капитал
            total_timesteps: Количество шагов обучения
            learning_rate: Learning rate
            n_steps: Шагов на rollout
            batch_size: Batch size
            n_epochs: Epochs per update
            gamma: Discount factor
            gae_lambda: GAE lambda
            clip_range: PPO clip range
            ent_coef: Entropy coefficient
            vf_coef: Value function coefficient
            max_grad_norm: Max gradient norm
            verbose: Verbosity level
        
        Returns:
            Dict с метриками обучения
        """
        logger.info(f"Training RL agent on {len(df)} samples...")
        
        # Создание окружения
        self.env = create_trading_env(
            df=df,
            initial_capital=initial_capital,
            commission_bps=8.0,
            slippage_bps=5.0,
            max_positions=1,
            sharpe_window=30,
        )
        
        # Обёртка Monitor для логирования
        self.env = Monitor(self.env)
        
        # Vectorized environment (требуется для SB3)
        vec_env = DummyVecEnv([lambda: self.env])
        
        # Инициализация PPO модели
        self.model = PPO(
            policy="MlpPolicy",
            env=vec_env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            verbose=verbose,
            tensorboard_log=str(self.tensorboard_dir),
        )
        
        # Callback для tensorboard
        callback = TensorboardCallback()
        
        # Обучение
        logger.info(f"Starting PPO training for {total_timesteps} timesteps...")
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            progress_bar=True,
        )
        
        # Сохранение модели
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"ppo_{exchange}_{symbol.replace('/', '_')}_{timeframe}_{timestamp}"
        model_path = self.model_dir / f"{model_name}.zip"
        
        self.model.save(model_path)
        logger.info(f"Model saved to {model_path}")
        
        # Метрики обучения
        metrics = {
            "model_path": str(model_path),
            "total_timesteps": total_timesteps,
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "initial_capital": initial_capital,
            "mean_episode_reward": np.mean(callback.episode_rewards) if callback.episode_rewards else 0.0,
            "mean_episode_length": np.mean(callback.episode_lengths) if callback.episode_lengths else 0.0,
        }
        
        return metrics
    
    def load(self, model_path: str) -> None:
        """
        Загрузка обученной модели.
        
        Args:
            model_path: Путь к .zip файлу модели
        """
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        logger.info(f"Loading RL model from {model_path}")
        self.model = PPO.load(model_path)
    
    def predict(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000.0,
        deterministic: bool = True,
    ) -> Dict[str, Any]:
        """
        Inference: прогон модели на данных для получения сигналов и sizing.
        
        Args:
            df: DataFrame с OHLCV + features
            initial_capital: Начальный капитал
            deterministic: Детерминированное предсказание (без exploration noise)
        
        Returns:
            Dict с результатами:
                - actions: List[Tuple[direction, sizing]]
                - equity_curve: List[float]
                - trades: List[Dict]
                - metrics: Dict (final equity, total return, sharpe, etc.)
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")
        
        logger.info(f"Running inference on {len(df)} samples...")
        
        # Создание окружения
        env = create_trading_env(
            df=df,
            initial_capital=initial_capital,
            commission_bps=8.0,
            slippage_bps=5.0,
        )
        
        obs, info = env.reset()
        
        actions_history = []
        equity_curve = [env.equity]
        
        done = False
        while not done:
            # Предсказание действия
            action, _states = self.model.predict(obs, deterministic=deterministic)
            
            # Шаг в окружении
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            # Логирование
            actions_history.append({
                "step": info["step"],
                "direction": int(action[0]),
                "sizing": (int(action[1]) + 1) * 0.01,
            })
            equity_curve.append(env.equity)
        
        # Финальные метрики
        final_equity = env.equity
        total_return = (final_equity - initial_capital) / initial_capital
        
        # Sharpe ratio
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        
        # Max Drawdown
        peak = pd.Series(equity_curve).expanding().max()
        dd = (pd.Series(equity_curve) - peak) / peak
        max_dd = dd.min()
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        sortino = (returns.mean() / downside_returns.std()) * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0.0
        
        metrics = {
            "final_equity": final_equity,
            "total_return": total_return * 100,  # В процентах
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd * 100,  # В процентах
            "total_trades": len(env.trades_history),
        }
        
        # Win rate
        if env.trades_history:
            winning_trades = [t for t in env.trades_history if t["pnl"] > 0]
            metrics["win_rate"] = len(winning_trades) / len(env.trades_history) * 100
            
            # Avg win/loss
            if winning_trades:
                metrics["avg_win"] = np.mean([t["pnl"] for t in winning_trades])
            else:
                metrics["avg_win"] = 0.0
            
            losing_trades = [t for t in env.trades_history if t["pnl"] <= 0]
            if losing_trades:
                metrics["avg_loss"] = np.mean([t["pnl"] for t in losing_trades])
            else:
                metrics["avg_loss"] = 0.0
        else:
            metrics["win_rate"] = 0.0
            metrics["avg_win"] = 0.0
            metrics["avg_loss"] = 0.0
        
        results = {
            "actions": actions_history,
            "equity_curve": equity_curve,
            "trades": env.trades_history,
            "metrics": metrics,
        }
        
        logger.info(f"Inference complete. Final equity: {final_equity:.2f}, Return: {total_return*100:.2f}%, Sharpe: {sharpe:.2f}")
        
        return results
    
    def evaluate(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000.0,
        n_eval_episodes: int = 10,
    ) -> Dict[str, Any]:
        """
        Оценка производительности модели на тестовых данных.
        
        Args:
            df: DataFrame с OHLCV + features
            initial_capital: Начальный капитал
            n_eval_episodes: Количество эпизодов для оценки
        
        Returns:
            Dict с метриками (mean, std)
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")
        
        logger.info(f"Evaluating model over {n_eval_episodes} episodes...")
        
        all_metrics = []
        
        for ep in range(n_eval_episodes):
            results = self.predict(df=df, initial_capital=initial_capital, deterministic=True)
            all_metrics.append(results["metrics"])
        
        # Агрегация метрик
        aggregated = {
            "mean_return": np.mean([m["total_return"] for m in all_metrics]),
            "std_return": np.std([m["total_return"] for m in all_metrics]),
            "mean_sharpe": np.mean([m["sharpe_ratio"] for m in all_metrics]),
            "std_sharpe": np.std([m["sharpe_ratio"] for m in all_metrics]),
            "mean_max_dd": np.mean([m["max_drawdown"] for m in all_metrics]),
            "mean_win_rate": np.mean([m["win_rate"] for m in all_metrics]),
        }
        
        logger.info(f"Evaluation complete. Mean return: {aggregated['mean_return']:.2f}% ± {aggregated['std_return']:.2f}%")
        
        return aggregated


def load_latest_rl_model(exchange: str, symbol: str, timeframe: str, model_dir: str = "artifacts/rl_models") -> Optional[str]:
    """
    Загрузить последнюю обученную RL модель для заданной пары.
    
    Args:
        exchange: Биржа
        symbol: Символ (e.g. 'BTC/USDT')
        timeframe: Таймфрейм (e.g. '1h')
        model_dir: Директория с моделями
    
    Returns:
        Путь к модели или None
    """
    model_dir_path = Path(model_dir)
    if not model_dir_path.exists():
        return None
    
    # Поиск моделей
    symbol_clean = symbol.replace("/", "_")
    pattern = f"ppo_{exchange}_{symbol_clean}_{timeframe}_*.zip"
    
    models = list(model_dir_path.glob(pattern))
    
    if not models:
        return None
    
    # Сортировка по дате модификации (последняя)
    latest = max(models, key=lambda p: p.stat().st_mtime)
    
    return str(latest)
