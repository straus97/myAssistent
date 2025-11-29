"""
Backtest для улучшенной EMA Crossover стратегии

ЦЕЛЬ: Проверить стратегию на последних 30 днях данных

МЕТРИКИ:
- Sharpe Ratio (> 1.0 для real trading)
- Max Drawdown (< 10%)
- Win Rate (> 50%)
- Profit Factor (> 1.5)
- Total Return (положительный!)

USAGE:
    python scripts/backtest_ema_advanced.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Any
import json

from src.prices import fetch_ohlcv
from src.simple_strategies import ema_crossover_advanced_strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def backtest_strategy_with_atr_stops(
    df: pd.DataFrame,
    signals: pd.Series,
    indicators: pd.DataFrame,
    initial_capital: float = 10000.0,
    commission_bps: float = 8.0,
    slippage_bps: float = 5.0
) -> Dict[str, Any]:
    """
    Backtest с адаптивными Stop-Loss/Take-Profit на основе ATR
    
    Логика:
    1. BUY signal → открываем позицию
    2. Exit по одному из условий:
       - SELL signal (EMA bearish cross)
       - Stop-Loss (цена упала на ATR * 1.5)
       - Take-Profit (цена выросла на ATR * 3.0)
    """
    prices = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    signals_array = signals.values
    
    capital = initial_capital
    position = 0.0
    position_size = 0.0
    entry_price = 0.0
    equity_curve = []
    trades_history = []
    
    for i in range(len(prices)):
        price = prices[i]
        signal = signals_array[i]
        
        # Entry (BUY signal)
        if signal == 1 and position == 0:
            commission = (commission_bps + slippage_bps) / 10000
            position_size = capital * 0.95  # 95% от капитала (5% reserve)
            cost = position_size / (1 - commission)
            
            if cost > capital:
                # Недостаточно капитала
                equity_curve.append(capital)
                continue
            
            entry_price = price
            position = position_size / price
            capital -= cost
            
            # Получаем адаптивные уровни Stop-Loss/Take-Profit
            stop_loss_pct = indicators['stop_loss_pct'].iloc[i] if i < len(indicators) else 2.0
            take_profit_pct = indicators['take_profit_pct'].iloc[i] if i < len(indicators) else 5.0
            
            trades_history.append({
                "entry_idx": i,
                "entry_price": entry_price,
                "entry_time": df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                "stop_loss_price": entry_price * (1 - stop_loss_pct / 100),
                "take_profit_price": entry_price * (1 + take_profit_pct / 100),
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
                "exit_idx": None,
                "exit_price": None,
                "exit_reason": None,
                "pnl": None,
                "pnl_pct": None
            })
        
        # Check Stop-Loss/Take-Profit (если есть позиция)
        elif position > 0:
            trade = trades_history[-1]
            stop_loss_hit = lows[i] <= trade["stop_loss_price"]
            take_profit_hit = highs[i] >= trade["take_profit_price"]
            sell_signal = signal == -1
            
            exit_triggered = False
            exit_price_actual = price
            exit_reason = "HOLD"
            
            if stop_loss_hit:
                exit_triggered = True
                exit_price_actual = trade["stop_loss_price"]
                exit_reason = "STOP_LOSS"
            elif take_profit_hit:
                exit_triggered = True
                exit_price_actual = trade["take_profit_price"]
                exit_reason = "TAKE_PROFIT"
            elif sell_signal:
                exit_triggered = True
                exit_price_actual = price
                exit_reason = "SELL_SIGNAL"
            
            # Exit позиции
            if exit_triggered:
                commission = (commission_bps + slippage_bps) / 10000
                proceeds = position * exit_price_actual * (1 - commission)
                capital += proceeds
                
                pnl = proceeds - position_size
                pnl_pct = pnl / position_size
                
                trade["exit_idx"] = i
                trade["exit_price"] = exit_price_actual
                trade["exit_time"] = df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i])
                trade["exit_reason"] = exit_reason
                trade["pnl"] = pnl
                trade["pnl_pct"] = pnl_pct
                trade["duration_bars"] = i - trade["entry_idx"]
                
                position = 0.0
                position_size = 0.0
                entry_price = 0.0
        
        # Track equity
        if position > 0:
            current_equity = capital + (position * price)
        else:
            current_equity = capital
        
        equity_curve.append(current_equity)
    
    # Force close открытых позиций в конце
    if position > 0:
        commission = (commission_bps + slippage_bps) / 10000
        exit_price_actual = prices[-1]
        proceeds = position * exit_price_actual * (1 - commission)
        capital += proceeds
        
        pnl = proceeds - position_size
        pnl_pct = pnl / position_size
        
        trades_history[-1]["exit_idx"] = len(prices) - 1
        trades_history[-1]["exit_price"] = exit_price_actual
        trades_history[-1]["exit_time"] = df.index[-1].isoformat() if hasattr(df.index[-1], 'isoformat') else str(df.index[-1])
        trades_history[-1]["exit_reason"] = "END_OF_DATA"
        trades_history[-1]["pnl"] = pnl
        trades_history[-1]["pnl_pct"] = pnl_pct
        trades_history[-1]["duration_bars"] = len(prices) - 1 - trades_history[-1]["entry_idx"]
    
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
    
    stop_loss_exits = [t for t in completed_trades if t["exit_reason"] == "STOP_LOSS"]
    take_profit_exits = [t for t in completed_trades if t["exit_reason"] == "TAKE_PROFIT"]
    signal_exits = [t for t in completed_trades if t["exit_reason"] == "SELL_SIGNAL"]
    
    win_rate = len(winning_trades) / max(len(completed_trades), 1) if completed_trades else 0.0
    
    avg_win = np.mean([t["pnl_pct"] for t in winning_trades]) if winning_trades else 0.0
    avg_loss = np.mean([t["pnl_pct"] for t in losing_trades]) if losing_trades else 0.0
    
    total_wins = sum([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
    total_losses = abs(sum([t["pnl"] for t in losing_trades])) if losing_trades else 1e-9
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
    
    avg_duration = np.mean([t["duration_bars"] for t in completed_trades]) if completed_trades else 0
    
    return {
        "total_return": total_return,
        "total_return_pct": total_return * 100,
        "final_capital": final_capital,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown * 100,
        "win_rate": win_rate,
        "win_rate_pct": win_rate * 100,
        "avg_win": avg_win,
        "avg_win_pct": avg_win * 100,
        "avg_loss": avg_loss,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": profit_factor,
        "total_trades": len(completed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "stop_loss_exits": len(stop_loss_exits),
        "take_profit_exits": len(take_profit_exits),
        "signal_exits": len(signal_exits),
        "avg_duration_bars": avg_duration,
        "equity_curve": equity_curve,
        "trades_history": completed_trades
    }


def run_backtest_for_symbol(
    exchange: str,
    symbol: str,
    timeframe: str,
    days_back: int = 30,
    initial_capital: float = 10000.0
) -> Dict[str, Any]:
    """Запускает бэктест для одного символа"""
    logger.info(f"\n{'='*60}")
    logger.info(f"BACKTEST: {symbol} ({timeframe}) - Last {days_back} days")
    logger.info(f"{'='*60}\n")
    
    # Загружаем исторические данные
    limit = days_back * 24 if timeframe == "1h" else days_back * 96 if timeframe == "15m" else days_back
    
    try:
        df = fetch_ohlcv(exchange, symbol, timeframe, limit=limit)
        
        if df.empty or len(df) < 100:
            logger.error(f"Not enough data for {symbol} (got {len(df)} rows)")
            return None
        
        logger.info(f"Loaded {len(df)} candles from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        
        # Генерируем сигналы с улучшенной стратегией
        df = df.set_index("timestamp")
        signals, indicators = ema_crossover_advanced_strategy(
            df,
            fast_period=12,
            slow_period=26,
            rsi_period=14,
            rsi_overbought=70,
            rsi_oversold=30,
            volume_threshold=1.2,
            atr_period=14
        )
        
        # Бэктест
        results = backtest_strategy_with_atr_stops(
            df, signals, indicators, 
            initial_capital=initial_capital,
            commission_bps=8.0,
            slippage_bps=5.0
        )
        
        if results is None:
            return None
        
        # Добавляем метаданные
        results["symbol"] = symbol
        results["exchange"] = exchange
        results["timeframe"] = timeframe
        results["days_back"] = days_back
        results["initial_capital"] = initial_capital
        results["start_date"] = str(df.index[0])
        results["end_date"] = str(df.index[-1])
        
        return results
    
    except Exception as e:
        logger.error(f"Error backtesting {symbol}: {e}", exc_info=True)
        return None


def print_results(results: Dict[str, Any]) -> None:
    """Красивый вывод результатов"""
    print("\n" + "="*80)
    print(f"📊 BACKTEST RESULTS: {results['symbol']} ({results['timeframe']})")
    print("="*80)
    
    print(f"\n💰 CAPITAL:")
    print(f"  Initial:  ${results['initial_capital']:,.2f}")
    print(f"  Final:    ${results['final_capital']:,.2f}")
    print(f"  Return:   {results['total_return_pct']:+.2f}%")
    
    print(f"\n📈 RISK METRICS:")
    print(f"  Sharpe Ratio:  {results['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"  Calmar Ratio:  {results['calmar_ratio']:.2f}")
    print(f"  Max Drawdown:  {results['max_drawdown_pct']:.2f}%")
    
    print(f"\n🎯 TRADING STATS:")
    print(f"  Total Trades:    {results['total_trades']}")
    print(f"  Win Rate:        {results['win_rate_pct']:.1f}%")
    print(f"  Winning Trades:  {results['winning_trades']}")
    print(f"  Losing Trades:   {results['losing_trades']}")
    print(f"  Avg Win:         {results['avg_win_pct']:+.2f}%")
    print(f"  Avg Loss:        {results['avg_loss_pct']:+.2f}%")
    print(f"  Profit Factor:   {results['profit_factor']:.2f}")
    print(f"  Avg Duration:    {results['avg_duration_bars']:.0f} bars")
    
    print(f"\n🚪 EXIT BREAKDOWN:")
    print(f"  Stop-Loss:     {results['stop_loss_exits']} ({results['stop_loss_exits']/max(results['total_trades'], 1)*100:.1f}%)")
    print(f"  Take-Profit:   {results['take_profit_exits']} ({results['take_profit_exits']/max(results['total_trades'], 1)*100:.1f}%)")
    print(f"  Sell Signal:   {results['signal_exits']} ({results['signal_exits']/max(results['total_trades'], 1)*100:.1f}%)")
    
    print(f"\n✅ READY FOR REAL TRADING?")
    criteria_passed = 0
    criteria_total = 5
    
    if results['sharpe_ratio'] > 1.0:
        print(f"  ✅ Sharpe > 1.0: {results['sharpe_ratio']:.2f}")
        criteria_passed += 1
    else:
        print(f"  ❌ Sharpe > 1.0: {results['sharpe_ratio']:.2f}")
    
    if results['max_drawdown'] > -0.10:
        print(f"  ✅ Max DD < 10%: {results['max_drawdown_pct']:.2f}%")
        criteria_passed += 1
    else:
        print(f"  ❌ Max DD < 10%: {results['max_drawdown_pct']:.2f}%")
    
    if results['win_rate'] > 0.50:
        print(f"  ✅ Win Rate > 50%: {results['win_rate_pct']:.1f}%")
        criteria_passed += 1
    else:
        print(f"  ❌ Win Rate > 50%: {results['win_rate_pct']:.1f}%")
    
    if results['profit_factor'] > 1.5:
        print(f"  ✅ Profit Factor > 1.5: {results['profit_factor']:.2f}")
        criteria_passed += 1
    else:
        print(f"  ❌ Profit Factor > 1.5: {results['profit_factor']:.2f}")
    
    if results['total_return'] > 0:
        print(f"  ✅ Positive Return: {results['total_return_pct']:+.2f}%")
        criteria_passed += 1
    else:
        print(f"  ❌ Positive Return: {results['total_return_pct']:+.2f}%")
    
    print(f"\n  Score: {criteria_passed}/{criteria_total}")
    
    if criteria_passed == criteria_total:
        print("\n  🎉 ОТЛИЧНО! Стратегия готова к Real Trading!")
    elif criteria_passed >= 3:
        print("\n  ⚠️  Хорошо, но требуется улучшение")
    else:
        print("\n  ❌ Стратегия требует доработки")
    
    print("\n" + "="*80 + "\n")


def main():
    """Основная функция бэктеста"""
    
    # Параметры бэктеста
    EXCHANGE = "bybit"
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    TIMEFRAME = "1h"
    DAYS_BACK = 30
    INITIAL_CAPITAL = 10000.0
    
    logger.info("🚀 Starting Advanced EMA Crossover Backtest")
    logger.info(f"Exchange: {EXCHANGE}")
    logger.info(f"Symbols: {SYMBOLS}")
    logger.info(f"Timeframe: {TIMEFRAME}")
    logger.info(f"Period: Last {DAYS_BACK} days")
    logger.info(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}\n")
    
    all_results = []
    
    for symbol in SYMBOLS:
        results = run_backtest_for_symbol(
            exchange=EXCHANGE,
            symbol=symbol,
            timeframe=TIMEFRAME,
            days_back=DAYS_BACK,
            initial_capital=INITIAL_CAPITAL
        )
        
        if results:
            all_results.append(results)
            print_results(results)
    
    # Сохраняем результаты
    if all_results:
        output_dir = Path("artifacts/backtest_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"ema_advanced_backtest_{timestamp}.json"
        
        # Убираем equity_curve из JSON (слишком большой)
        for r in all_results:
            r.pop("equity_curve", None)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Results saved to: {output_file}")
        
        # Общая статистика
        print("\n" + "="*80)
        print("📊 PORTFOLIO SUMMARY")
        print("="*80)
        
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in all_results])
        avg_return = np.mean([r['total_return_pct'] for r in all_results])
        avg_win_rate = np.mean([r['win_rate_pct'] for r in all_results])
        avg_max_dd = np.mean([r['max_drawdown_pct'] for r in all_results])
        total_trades = sum([r['total_trades'] for r in all_results])
        
        print(f"\nSymbols tested: {len(all_results)}")
        print(f"Average Sharpe: {avg_sharpe:.2f}")
        print(f"Average Return: {avg_return:+.2f}%")
        print(f"Average Win Rate: {avg_win_rate:.1f}%")
        print(f"Average Max DD: {avg_max_dd:.2f}%")
        print(f"Total Trades: {total_trades}")
        
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

