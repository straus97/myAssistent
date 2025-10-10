"""
Custom Gymnasium Environment для криптотрейдинга с RL.

State Space:
- Позиции (open positions, sizing)
- Equity history (rolling window)
- Features (технические + фундаментальные + sentiment)
- Risk metrics (volatility, DD, Sharpe)

Action Space:
- Дискретные: buy/sell/hold (3 действия)
- Непрерывные: sizing (0.0-1.0 от доступного капитала)

Reward Function:
- Sharpe ratio (risk-adjusted returns)
- Sortino ratio (downside deviation penalty)
- Penalty за чрезмерную торговлю (комиссии)
"""

from __future__ import annotations
import logging
from typing import Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

logger = logging.getLogger(__name__)


class CryptoTradingEnv(gym.Env):
    """
    Custom Gym Environment для крипто trading с continuous action space для sizing.
    
    Observation Space:
    - Features: 78+ фич (технические, новости, on-chain, macro, social)
    - Equity metrics: current_equity, max_equity, drawdown
    - Position info: current_position, entry_price
    - Risk metrics: volatility, sharpe (rolling)
    
    Action Space:
    - MultiDiscrete([3, 101]): 
      - action[0]: 0=hold, 1=buy, 2=sell
      - action[1]: sizing от 0% до 100% (в шагах по 1%)
    
    Reward:
    - Rolling Sharpe Ratio (risk-adjusted returns)
    - Penalty за комиссии и проскальзывание
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000.0,
        commission_bps: float = 8.0,
        slippage_bps: float = 5.0,
        max_position_size: float = 1.0,
        reward_window: int = 24,  # Rolling window для Sharpe (24 часа)
        features_columns: list | None = None,
    ):
        """
        Args:
            df: DataFrame с историческими данными (цены + фичи)
            initial_capital: Начальный капитал
            commission_bps: Комиссии в базисных пунктах
            slippage_bps: Проскальзывание в базисных пунктах
            max_position_size: Максимальный размер позиции (доля капитала)
            reward_window: Размер окна для расчёта Sharpe
            features_columns: Список колонок с фичами
        """
        super().__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_capital = initial_capital
        self.commission_rate = commission_bps / 10000.0
        self.slippage_rate = slippage_bps / 10000.0
        self.max_position_size = max_position_size
        self.reward_window = reward_window
        
        # Определяем колонки с фичами
        if features_columns is None:
            # Автоматически берём все колонки кроме служебных
            exclude_cols = ['timestamp', 'close', 'open', 'high', 'low', 'volume', 'future_ret', 'y']
            self.features_columns = [c for c in df.columns if c not in exclude_cols]
        else:
            self.features_columns = features_columns
        
        self.n_features = len(self.features_columns)
        
        # Action space: [action_type (0=hold, 1=buy, 2=sell), sizing (0-100%)]
        self.action_space = spaces.MultiDiscrete([3, 101])
        
        # Observation space: features + equity metrics + position info + risk metrics
        # Features (78+) + 6 meta metrics
        obs_dim = self.n_features + 6
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32
        )
        
        # Внутреннее состояние
        self.current_step = 0
        self.equity = initial_capital
        self.cash = initial_capital
        self.position = 0.0  # Количество монет
        self.entry_price = 0.0
        self.max_equity = initial_capital
        self.returns_history = []
        
        logger.info(f"[rl_env] Initialized CryptoTradingEnv: {len(df)} steps, {self.n_features} features")
    
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """
        Сброс environment в начальное состояние.
        
        Returns:
            observation: Начальное состояние
            info: Дополнительная информация
        """
        super().reset(seed=seed)
        
        self.current_step = 0
        self.equity = self.initial_capital
        self.cash = self.initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.max_equity = self.initial_capital
        self.returns_history = []
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, info
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Выполнить действие в environment.
        
        Args:
            action: [action_type, sizing]
                - action_type: 0=hold, 1=buy, 2=sell
                - sizing: 0-100 (процент капитала)
        
        Returns:
            observation: Новое состояние
            reward: Награда
            terminated: Эпизод завершён (нормально)
            truncated: Эпизод обрезан (по времени)
            info: Дополнительная информация
        """
        action_type = int(action[0])
        sizing_pct = float(action[1]) / 100.0  # 0-100 → 0.0-1.0
        sizing_pct = np.clip(sizing_pct, 0.0, self.max_position_size)
        
        # Получаем текущую цену
        current_price = float(self.df.loc[self.current_step, 'close'])
        
        # Выполняем действие
        reward = self._execute_action(action_type, sizing_pct, current_price)
        
        # Переходим к следующему шагу
        self.current_step += 1
        
        # Проверяем завершение
        terminated = False  # Не завершаем досрочно (можно добавить условия банкротства)
        truncated = self.current_step >= len(self.df) - 1
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, reward, terminated, truncated, info
    
    def _execute_action(self, action_type: int, sizing_pct: float, price: float) -> float:
        """
        Выполнить торговое действие и вернуть reward.
        
        Args:
            action_type: 0=hold, 1=buy, 2=sell
            sizing_pct: Размер позиции (доля капитала)
            price: Текущая цена
        
        Returns:
            reward: Награда за действие
        """
        old_equity = self.equity
        
        if action_type == 1:  # BUY
            # Закрываем короткую позицию если была
            if self.position < 0:
                self._close_position(price)
            
            # Открываем длинную позицию
            target_value = self.equity * sizing_pct
            commission = target_value * (self.commission_rate + self.slippage_rate)
            buy_power = target_value - commission
            
            if buy_power > 0:
                coins_to_buy = buy_power / price
                self.position += coins_to_buy
                self.cash -= target_value
                self.entry_price = price
        
        elif action_type == 2:  # SELL
            # Закрываем длинную позицию если была
            if self.position > 0:
                self._close_position(price)
            
            # Открываем короткую позицию (для крипто это сложно, но для симуляции OK)
            target_value = self.equity * sizing_pct
            commission = target_value * (self.commission_rate + self.slippage_rate)
            sell_power = target_value - commission
            
            if sell_power > 0:
                coins_to_sell = sell_power / price
                self.position -= coins_to_sell
                self.cash += sell_power
                self.entry_price = price
        
        # action_type == 0 (HOLD) - ничего не делаем
        
        # Обновляем equity
        position_value = self.position * price
        self.equity = self.cash + position_value
        self.max_equity = max(self.max_equity, self.equity)
        
        # Расчёт return
        equity_return = (self.equity - old_equity) / old_equity if old_equity > 0 else 0.0
        self.returns_history.append(equity_return)
        
        # Reward: Rolling Sharpe Ratio
        reward = self._calculate_reward()
        
        return reward
    
    def _close_position(self, price: float):
        """Закрыть текущую позицию."""
        if self.position == 0:
            return
        
        position_value = abs(self.position) * price
        commission = position_value * self.commission_rate
        
        if self.position > 0:
            # Закрываем длинную позицию
            proceeds = position_value - commission
            self.cash += proceeds
        else:
            # Закрываем короткую позицию
            cost = position_value + commission
            self.cash -= cost
        
        self.position = 0.0
        self.entry_price = 0.0
    
    def _calculate_reward(self) -> float:
        """
        Расчёт reward на основе Rolling Sharpe Ratio.
        
        Sharpe = (mean_return / std_return) * sqrt(window_size)
        
        Returns:
            reward: Sharpe ratio (risk-adjusted returns)
        """
        if len(self.returns_history) < 2:
            return 0.0
        
        # Используем последние reward_window returns
        recent_returns = self.returns_history[-self.reward_window:]
        
        mean_ret = np.mean(recent_returns)
        std_ret = np.std(recent_returns)
        
        if std_ret == 0 or np.isnan(std_ret):
            return 0.0
        
        # Sharpe ratio (annualized для крипто = 24*365)
        sharpe = (mean_ret / std_ret) * np.sqrt(len(recent_returns))
        
        return float(sharpe)
    
    def _get_observation(self) -> np.ndarray:
        """
        Получить текущее observation (state).
        
        Returns:
            observation: [features, equity_pct, max_equity_pct, drawdown, 
                          position_ratio, volatility, rolling_sharpe]
        """
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1
        
        # Features
        features = self.df.loc[self.current_step, self.features_columns].values.astype(np.float32)
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Meta metrics
        equity_pct = (self.equity / self.initial_capital) - 1.0  # % изменение
        max_equity_pct = (self.max_equity / self.initial_capital) - 1.0
        drawdown = (self.equity - self.max_equity) / self.max_equity if self.max_equity > 0 else 0.0
        
        # Position ratio (доля капитала в позиции)
        current_price = float(self.df.loc[self.current_step, 'close'])
        position_value = self.position * current_price
        position_ratio = position_value / self.equity if self.equity > 0 else 0.0
        
        # Volatility (std последних returns)
        if len(self.returns_history) >= 5:
            volatility = float(np.std(self.returns_history[-20:]))
        else:
            volatility = 0.0
        
        # Rolling Sharpe
        rolling_sharpe = self._calculate_reward()
        
        meta_metrics = np.array([
            equity_pct,
            max_equity_pct,
            drawdown,
            position_ratio,
            volatility,
            rolling_sharpe,
        ], dtype=np.float32)
        
        observation = np.concatenate([features, meta_metrics])
        
        return observation
    
    def _get_info(self) -> Dict:
        """Получить дополнительную информацию о состоянии."""
        return {
            "step": self.current_step,
            "equity": self.equity,
            "cash": self.cash,
            "position": self.position,
            "entry_price": self.entry_price,
            "max_equity": self.max_equity,
            "drawdown": (self.equity - self.max_equity) / self.max_equity if self.max_equity > 0 else 0.0,
        }
    
    def render(self):
        """Визуализация состояния (для отладки)."""
        info = self._get_info()
        print(f"Step: {info['step']}, Equity: ${info['equity']:.2f}, Position: {info['position']:.4f}, DD: {info['drawdown']:.2%}")


# Вспомогательная функция для создания окружения из DataFrame
def create_trading_env(
    df: pd.DataFrame,
    initial_capital: float = 1000.0,
    commission_bps: float = 8.0,
    **kwargs
) -> CryptoTradingEnv:
    """
    Создать CryptoTradingEnv из DataFrame.
    
    Args:
        df: DataFrame с ценами и фичами
        initial_capital: Начальный капитал
        commission_bps: Комиссии
        **kwargs: Дополнительные параметры для CryptoTradingEnv
    
    Returns:
        env: Готовый environment
    """
    env = CryptoTradingEnv(
        df=df,
        initial_capital=initial_capital,
        commission_bps=commission_bps,
        **kwargs
    )
    return env

