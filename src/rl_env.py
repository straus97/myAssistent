"""
Reinforcement Learning Environment для крипто-трейдинга.

Custom Gym environment для обучения PPO-агента динамическому sizing позиций.
"""

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class CryptoTradingEnv(gym.Env):
    """
    Custom Gym environment для крипто-трейдинга.
    
    State Space:
        - Equity (1)
        - Open positions: [symbol, direction, size, entry_price, current_pnl] (5 * max_positions)
        - Features (78 технических/фундаментальных)
        - Risk metrics: [volatility, max_dd, sharpe] (3)
        Total: 1 + 5*max_positions + 78 + 3 = 87 (для max_positions=1)
    
    Action Space:
        - Discrete(3): [0=hold, 1=buy, 2=sell]
        - Box(0, 1): sizing (доля от капитала)
    
    Reward:
        - Rolling Sharpe ratio (риск-adjusted returns)
    """
    
    metadata = {"render_modes": []}
    
    def __init__(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000.0,
        commission_bps: float = 8.0,
        slippage_bps: float = 5.0,
        max_positions: int = 1,
        sharpe_window: int = 30,
        max_position_size: float = 0.20,  # Максимум 20% капитала
        min_position_size: float = 0.01,  # Минимум 1%
    ):
        """
        Args:
            df: DataFrame с OHLCV + features (должен содержать колонки: close, ret_1, ...)
            initial_capital: Начальный капитал
            commission_bps: Комиссия в basis points
            slippage_bps: Проскальзывание в basis points
            max_positions: Максимум одновременных позиций
            sharpe_window: Окно для расчёта Sharpe
            max_position_size: Максимальный размер позиции (доля от капитала)
            min_position_size: Минимальный размер позиции
        """
        super().__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_capital = initial_capital
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.max_positions = max_positions
        self.sharpe_window = sharpe_window
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        
        # Проверка обязательных колонок
        required_cols = ["close"]
        missing = [c for c in required_cols if c not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Извлечение фич (все колонки кроме служебных)
        exclude_cols = ["open", "high", "low", "close", "volume", "timestamp"]
        self.feature_cols = [c for c in self.df.columns if c not in exclude_cols]
        
        if not self.feature_cols:
            raise ValueError("No feature columns found in DataFrame")
        
        logger.info(f"Initialized RL env with {len(self.feature_cols)} features")
        
        # Нормализация фич (z-score)
        for col in self.feature_cols:
            if self.df[col].std() > 0:
                self.df[col] = (self.df[col] - self.df[col].mean()) / self.df[col].std()
            else:
                self.df[col] = 0.0
        
        # Action space: MultiDiscrete([3, 20]) → [direction, sizing_decile]
        # direction: 0=hold, 1=buy, 2=sell
        # sizing: 0-19 → 1% to 20% (дискретизация для простоты)
        self.action_space = spaces.MultiDiscrete([3, 20])
        
        # Observation space
        obs_size = (
            1 +  # equity
            5 * self.max_positions +  # positions
            len(self.feature_cols) +  # features
            3  # risk metrics
        )
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_size,),
            dtype=np.float32
        )
        
        # State variables
        self.current_step = 0
        self.equity = initial_capital
        self.positions = []  # List of dicts: {symbol, direction, size, entry_price, entry_step}
        self.equity_history = [initial_capital]
        self.returns_history = []
        self.trades_history = []
        
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Сброс окружения."""
        super().reset(seed=seed)
        
        self.current_step = 0
        self.equity = self.initial_capital
        self.positions = []
        self.equity_history = [self.initial_capital]
        self.returns_history = []
        self.trades_history = []
        
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, info
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Выполнение шага.
        
        Args:
            action: [direction, sizing_decile]
        
        Returns:
            observation, reward, terminated, truncated, info
        """
        direction = int(action[0])  # 0=hold, 1=buy, 2=sell
        sizing_decile = int(action[1])  # 0-19
        sizing_fraction = (sizing_decile + 1) * 0.01  # 1% to 20%
        
        # Клиппинг sizing
        sizing_fraction = np.clip(sizing_fraction, self.min_position_size, self.max_position_size)
        
        # Текущая цена
        current_price = self.df.loc[self.current_step, "close"]
        
        # Обновление открытых позиций (unrealized PnL)
        self._update_positions(current_price)
        
        # Выполнение действия
        if direction == 1:  # Buy
            self._execute_trade("buy", sizing_fraction, current_price)
        elif direction == 2:  # Sell
            self._execute_trade("sell", sizing_fraction, current_price)
        # direction == 0 → hold, ничего не делаем
        
        # Переход к следующему шагу
        self.current_step += 1
        
        # Проверка завершения эпизода
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        
        # Расчёт reward
        reward = self._calculate_reward()
        
        # Обновление equity history
        self.equity_history.append(self.equity)
        
        # Observation и info
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, reward, terminated, truncated, info
    
    def _execute_trade(self, direction: str, sizing_fraction: float, price: float) -> None:
        """Выполнить сделку."""
        # Проверка лимита позиций
        if len(self.positions) >= self.max_positions and direction in ["buy", "sell"]:
            # Закрыть старую позицию перед открытием новой
            if self.positions:
                self._close_position(self.positions[0], price)
        
        # Расчёт размера позиции
        position_value = self.equity * sizing_fraction
        
        # Комиссия и проскальзывание
        total_cost_bps = self.commission_bps + self.slippage_bps
        effective_price = price * (1 + total_cost_bps / 10000) if direction == "buy" else price * (1 - total_cost_bps / 10000)
        
        # Размер позиции в монетах
        size = position_value / effective_price
        
        # Открытие позиции
        pos = {
            "symbol": "CRYPTO",  # Generic
            "direction": direction,
            "size": size,
            "entry_price": effective_price,
            "entry_step": self.current_step,
        }
        self.positions.append(pos)
        
        # Вычитание комиссии из equity
        commission = position_value * (self.commission_bps / 10000)
        self.equity -= commission
        
        logger.debug(f"Step {self.current_step}: {direction.upper()} {size:.4f} @ {effective_price:.2f} (equity={self.equity:.2f})")
    
    def _close_position(self, position: Dict, current_price: float) -> None:
        """Закрыть позицию."""
        entry_price = position["entry_price"]
        size = position["size"]
        direction = position["direction"]
        
        # Комиссия при закрытии
        total_cost_bps = self.commission_bps + self.slippage_bps
        exit_price = current_price * (1 - total_cost_bps / 10000) if direction == "buy" else current_price * (1 + total_cost_bps / 10000)
        
        # PnL
        if direction == "buy":
            pnl = (exit_price - entry_price) * size
        else:  # sell (short)
            pnl = (entry_price - exit_price) * size
        
        # Обновление equity
        self.equity += pnl
        
        # Комиссия при закрытии
        commission = size * exit_price * (self.commission_bps / 10000)
        self.equity -= commission
        
        # Логирование сделки
        self.trades_history.append({
            "entry_step": position["entry_step"],
            "exit_step": self.current_step,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "commission": commission,
        })
        
        # Удаление из позиций
        self.positions.remove(position)
        
        logger.debug(f"Step {self.current_step}: CLOSE {direction.upper()} @ {exit_price:.2f} PnL={pnl:.2f}")
    
    def _update_positions(self, current_price: float) -> None:
        """Обновить нереализованный PnL для открытых позиций."""
        total_unrealized_pnl = 0.0
        
        for pos in self.positions:
            entry_price = pos["entry_price"]
            size = pos["size"]
            direction = pos["direction"]
            
            if direction == "buy":
                unrealized_pnl = (current_price - entry_price) * size
            else:  # sell (short)
                unrealized_pnl = (entry_price - current_price) * size
            
            total_unrealized_pnl += unrealized_pnl
        
        # Обновление equity с учётом unrealized PnL
        # (но не модифицируем self.equity напрямую, это только для отображения)
        # Для расчёта reward используем realized equity
    
    def _calculate_reward(self) -> float:
        """
        Расчёт reward: Rolling Sharpe Ratio.
        
        Reward = (mean_return / std_return) * sqrt(252) если std > 0, иначе 0
        """
        if len(self.equity_history) < 2:
            return 0.0
        
        # Возвраты
        returns = pd.Series(self.equity_history).pct_change().dropna()
        
        if len(returns) < self.sharpe_window:
            # Недостаточно данных для расчёта Sharpe
            # Используем простой return
            ret = (self.equity - self.equity_history[-2]) / self.equity_history[-2]
            return ret * 100  # Масштабирование
        
        # Rolling window
        recent_returns = returns.iloc[-self.sharpe_window:]
        
        mean_ret = recent_returns.mean()
        std_ret = recent_returns.std()
        
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(252)  # Annualized
        else:
            sharpe = 0.0
        
        return sharpe
    
    def _get_observation(self) -> np.ndarray:
        """Получить observation."""
        obs = []
        
        # 1. Equity (normalized)
        obs.append(self.equity / self.initial_capital)
        
        # 2. Open positions (padded)
        for i in range(self.max_positions):
            if i < len(self.positions):
                pos = self.positions[i]
                current_price = self.df.loc[self.current_step, "close"]
                entry_price = pos["entry_price"]
                size = pos["size"]
                direction_encoded = 1.0 if pos["direction"] == "buy" else -1.0
                
                # Unrealized PnL
                if pos["direction"] == "buy":
                    unrealized_pnl = (current_price - entry_price) * size
                else:
                    unrealized_pnl = (entry_price - current_price) * size
                
                obs.extend([
                    direction_encoded,
                    size / self.equity,  # Normalized size
                    entry_price / current_price,  # Price ratio
                    unrealized_pnl / self.equity,  # PnL ratio
                    (self.current_step - pos["entry_step"]) / 100,  # Hold time normalized
                ])
            else:
                # Padding
                obs.extend([0.0, 0.0, 1.0, 0.0, 0.0])
        
        # 3. Features (уже нормализованы)
        features = self.df.loc[self.current_step, self.feature_cols].values
        obs.extend(features)
        
        # 4. Risk metrics
        # Volatility (rolling std of returns)
        if len(self.equity_history) >= 20:
            returns = pd.Series(self.equity_history).pct_change().dropna()
            volatility = returns.iloc[-20:].std() * np.sqrt(252)  # Annualized
        else:
            volatility = 0.0
        
        # Max Drawdown
        if len(self.equity_history) > 1:
            peak = max(self.equity_history)
            current = self.equity_history[-1]
            max_dd = (peak - current) / peak if peak > 0 else 0.0
        else:
            max_dd = 0.0
        
        # Sharpe (последний расчёт)
        if len(self.equity_history) >= self.sharpe_window:
            returns = pd.Series(self.equity_history).pct_change().dropna()
            recent = returns.iloc[-self.sharpe_window:]
            sharpe = (recent.mean() / recent.std()) * np.sqrt(252) if recent.std() > 0 else 0.0
        else:
            sharpe = 0.0
        
        obs.extend([volatility, max_dd, sharpe])
        
        return np.array(obs, dtype=np.float32)
    
    def _get_info(self) -> Dict[str, Any]:
        """Дополнительная информация."""
        return {
            "step": self.current_step,
            "equity": self.equity,
            "positions": len(self.positions),
            "total_trades": len(self.trades_history),
        }
    
    def render(self) -> None:
        """Отрисовка (не используется)."""
        pass


def create_trading_env(
    df: pd.DataFrame,
    initial_capital: float = 1000.0,
    **kwargs
) -> CryptoTradingEnv:
    """
    Factory function для создания окружения.
    
    Args:
        df: DataFrame с OHLCV + features
        initial_capital: Начальный капитал
        **kwargs: Дополнительные параметры (commission_bps, slippage_bps, etc.)
    
    Returns:
        CryptoTradingEnv instance
    """
    return CryptoTradingEnv(df=df, initial_capital=initial_capital, **kwargs)
