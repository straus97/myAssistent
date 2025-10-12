"""
Простые торговые стратегии без ML

Включает:
1. RSI Mean-Reversion (перепроданность/перекупленность)
2. EMA Crossover (momentum/trend following)
3. Bollinger Bands (volatility breakout/mean-reversion)
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Расчет RSI (Relative Strength Index)
    
    Args:
        prices: Series цен
        period: Период RSI (обычно 14)
    
    Returns:
        Series RSI значений (0-100)
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def rsi_mean_reversion_strategy(
    df: pd.DataFrame,
    rsi_period: int = 14,
    oversold: int = 30,
    overbought: int = 70
) -> pd.Series:
    """
    RSI Mean-Reversion Strategy
    
    Логика:
    - BUY: RSI < 30 (перепроданность)
    - SELL: RSI > 70 (перекупленность)
    - HOLD: 30 <= RSI <= 70
    
    Args:
        df: DataFrame с колонкой 'close'
        rsi_period: Период RSI
        oversold: Порог перепроданности
        overbought: Порог перекупленности
    
    Returns:
        Series сигналов (1 = BUY, 0 = HOLD, -1 = SELL)
    """
    rsi = calculate_rsi(df['close'], period=rsi_period)
    
    signals = pd.Series(0, index=df.index)  # Default: HOLD
    signals[rsi < oversold] = 1   # BUY
    signals[rsi > overbought] = -1  # SELL
    
    logger.info(f"[RSI Strategy] Generated {(signals == 1).sum()} BUY, {(signals == -1).sum()} SELL signals")
    
    return signals


def ema_crossover_strategy(
    df: pd.DataFrame,
    fast_period: int = 9,
    slow_period: int = 21
) -> pd.Series:
    """
    EMA Crossover Strategy (Momentum/Trend Following)
    
    Логика:
    - BUY: Fast EMA crosses ABOVE Slow EMA (восходящий тренд)
    - SELL: Fast EMA crosses BELOW Slow EMA (нисходящий тренд)
    
    Args:
        df: DataFrame с колонкой 'close'
        fast_period: Быстрая EMA (обычно 9-12)
        slow_period: Медленная EMA (обычно 21-26)
    
    Returns:
        Series сигналов (1 = BUY, -1 = SELL, 0 = HOLD)
    """
    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    # Crossover detection
    signals = pd.Series(0, index=df.index)
    
    # BUY: Fast crosses above Slow
    signals[(ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))] = 1
    
    # SELL: Fast crosses below Slow
    signals[(ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))] = -1
    
    logger.info(f"[EMA Crossover] Generated {(signals == 1).sum()} BUY, {(signals == -1).sum()} SELL signals")
    
    return signals


def bollinger_bands_strategy(
    df: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0
) -> pd.Series:
    """
    Bollinger Bands Strategy
    
    Логика:
    - BUY: Price touches LOWER band (oversold)
    - SELL: Price touches UPPER band (overbought)
    
    Args:
        df: DataFrame с колонкой 'close'
        period: Период для SMA
        num_std: Количество стандартных отклонений
    
    Returns:
        Series сигналов (1 = BUY, -1 = SELL, 0 = HOLD)
    """
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    
    signals = pd.Series(0, index=df.index)
    
    # BUY: Price at or below lower band
    signals[df['close'] <= lower_band] = 1
    
    # SELL: Price at or above upper band
    signals[df['close'] >= upper_band] = -1
    
    logger.info(f"[Bollinger Bands] Generated {(signals == 1).sum()} BUY, {(signals == -1).sum()} SELL signals")
    
    return signals


def backtest_strategy(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0,
    commission_bps: float = 8.0,
    slippage_bps: float = 5.0
) -> Dict[str, Any]:
    """
    Универсальный backtest для любой стратегии
    
    Args:
        df: DataFrame с колонкой 'close'
        signals: Series сигналов (1 = BUY, -1 = SELL, 0 = HOLD)
        initial_capital: Начальный капитал
        commission_bps: Комиссия (basis points)
        slippage_bps: Проскальзывание (basis points)
    
    Returns:
        Dict с метриками
    """
    prices = df['close'].values
    signals_array = signals.values
    
    capital = initial_capital
    position = 0.0
    position_size = 0.0
    equity_curve = []
    trades_history = []
    
    entry_price = 0.0
    entry_idx = 0
    
    for i in range(len(prices)):
        price = prices[i]
        signal = signals_array[i]
        
        # Entry (BUY signal)
        if signal == 1 and position == 0:
            commission = (commission_bps + slippage_bps) / 10000
            position_size = capital * (1 - commission)
            position = position_size / price
            entry_price = price
            entry_idx = i
            
            trades_history.append({
                "entry_idx": i,
                "entry_price": price,
                "exit_idx": None,
                "exit_price": None,
                "pnl": None,
                "pnl_pct": None
            })
        
        # Exit (SELL signal or end)
        elif position > 0 and (signal == -1 or i == len(prices) - 1):
            commission = (commission_bps + slippage_bps) / 10000
            capital = position * price * (1 - commission)
            
            pnl = capital - position_size
            pnl_pct = pnl / position_size
            
            trades_history[-1]["exit_idx"] = i
            trades_history[-1]["exit_price"] = price
            trades_history[-1]["pnl"] = pnl
            trades_history[-1]["pnl_pct"] = pnl_pct
            trades_history[-1]["duration_bars"] = i - entry_idx
            
            position = 0.0
            position_size = 0.0
        
        # Track equity
        if position > 0:
            current_equity = position * price
        else:
            current_equity = capital
        
        equity_curve.append(current_equity)
    
    # Calculate metrics
    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()
    
    total_return = (equity_series.iloc[-1] / initial_capital) - 1
    final_capital = equity_series.iloc[-1]
    
    sharpe_ratio = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252 * 24)
    
    downside_returns = returns[returns < 0]
    sortino_ratio = (returns.mean() / (downside_returns.std() + 1e-9)) * np.sqrt(252 * 24) if len(downside_returns) > 0 else 0.0
    
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_drawdown = drawdown.min()
    
    calmar_ratio = (total_return / (abs(max_drawdown) + 1e-9)) if max_drawdown < 0 else 0.0
    
    completed_trades = [t for t in trades_history if t["exit_price"] is not None]
    winning_trades = [t for t in completed_trades if t["pnl"] > 0]
    losing_trades = [t for t in completed_trades if t["pnl"] <= 0]
    
    win_rate = len(winning_trades) / max(len(completed_trades), 1) if completed_trades else 0.0
    
    avg_win = np.mean([t["pnl_pct"] for t in winning_trades]) if winning_trades else 0.0
    avg_loss = np.mean([t["pnl_pct"] for t in losing_trades]) if losing_trades else 0.0
    
    total_wins = sum([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
    total_losses = abs(sum([t["pnl"] for t in losing_trades])) if losing_trades else 1e-9
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
    
    return {
        "total_return": total_return,
        "final_capital": final_capital,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "total_trades": len(completed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "equity_curve": equity_curve,
        "trades_history": completed_trades
    }

