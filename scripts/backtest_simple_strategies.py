#!/usr/bin/env python3
"""
Backtest простых стратегий (без ML)

Тестируем 3 стратегии:
1. RSI Mean-Reversion
2. EMA Crossover (Momentum)
3. Bollinger Bands

Сравниваем с Buy & Hold бенчмарком
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pandas as pd
from datetime import datetime

from src.db import SessionLocal
from src.db import Price
from src.simple_strategies import (
    rsi_mean_reversion_strategy,
    ema_crossover_strategy,
    bollinger_bands_strategy,
    backtest_strategy
)

print("=" * 80)
print(" " * 20 + "BACKTEST SIMPLE STRATEGIES")
print("=" * 80)
print()

# ===========================
# CONFIGURATION
# ===========================

EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
INITIAL_CAPITAL = 10000.0
COMMISSION_BPS = 8.0
SLIPPAGE_BPS = 5.0

print(f"Configuration:")
print(f"  Exchange:   {EXCHANGE}")
print(f"  Symbol:     {SYMBOL}")
print(f"  Timeframe:  {TIMEFRAME}")
print(f"  Capital:    ${INITIAL_CAPITAL:,.2f}")
print()

# ===========================
# LOAD DATA
# ===========================

print("=" * 80)
print("Step 1: Loading historical prices")
print("=" * 80)
print()

db = SessionLocal()

try:
    prices_query = db.query(Price).filter(
        Price.exchange == EXCHANGE,
        Price.symbol == SYMBOL,
        Price.timeframe == TIMEFRAME
    ).order_by(Price.ts.asc()).all()
    
    if not prices_query:
        print("[!] No prices found in DB")
        print("    Run: POST /prices/fetch")
        sys.exit(1)
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {
            "timestamp": pd.Timestamp(p.ts, unit='ms', tz='UTC'),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume
        }
        for p in prices_query
    ])
    
    df = df.set_index("timestamp")
    
finally:
    db.close()

print(f"[OK] Prices loaded: {len(df)} rows")
print(f"     Period: {df.index.min()} - {df.index.max()}")
print()

# Use last 20% for backtest (same as PHASE 3)
split_idx = int(len(df) * 0.8)
backtest_df = df.iloc[split_idx:].copy()

print(f"[OK] Backtest period: {len(backtest_df)} rows")
print(f"     Dates: {backtest_df.index.min()} - {backtest_df.index.max()}")
print()

# ===========================
# STRATEGY 1: RSI MEAN-REVERSION
# ===========================

print("=" * 80)
print("Step 2: RSI Mean-Reversion Strategy")
print("=" * 80)
print()

print("[*] Generating RSI signals (period=14, oversold=30, overbought=70)...")
signals_rsi = rsi_mean_reversion_strategy(backtest_df, rsi_period=14, oversold=30, overbought=70)

print("[*] Running backtest...")
results_rsi = backtest_strategy(
    df=backtest_df,
    signals=signals_rsi,
    initial_capital=INITIAL_CAPITAL,
    commission_bps=COMMISSION_BPS,
    slippage_bps=SLIPPAGE_BPS
)

print(f"[OK] RSI Strategy completed")
print(f"     Return: {results_rsi['total_return']*100:>7.2f}%")
print(f"     Sharpe: {results_rsi['sharpe_ratio']:>7.2f}")
print(f"     Trades: {results_rsi['total_trades']:>7}")
print()

# ===========================
# STRATEGY 2: EMA CROSSOVER
# ===========================

print("=" * 80)
print("Step 3: EMA Crossover Strategy")
print("=" * 80)
print()

print("[*] Generating EMA crossover signals (fast=9, slow=21)...")
signals_ema = ema_crossover_strategy(backtest_df, fast_period=9, slow_period=21)

print("[*] Running backtest...")
results_ema = backtest_strategy(
    df=backtest_df,
    signals=signals_ema,
    initial_capital=INITIAL_CAPITAL,
    commission_bps=COMMISSION_BPS,
    slippage_bps=SLIPPAGE_BPS
)

print(f"[OK] EMA Crossover completed")
print(f"     Return: {results_ema['total_return']*100:>7.2f}%")
print(f"     Sharpe: {results_ema['sharpe_ratio']:>7.2f}")
print(f"     Trades: {results_ema['total_trades']:>7}")
print()

# ===========================
# STRATEGY 3: BOLLINGER BANDS
# ===========================

print("=" * 80)
print("Step 4: Bollinger Bands Strategy")
print("=" * 80)
print()

print("[*] Generating Bollinger Bands signals (period=20, std=2.0)...")
signals_bb = bollinger_bands_strategy(backtest_df, period=20, num_std=2.0)

print("[*] Running backtest...")
results_bb = backtest_strategy(
    df=backtest_df,
    signals=signals_bb,
    initial_capital=INITIAL_CAPITAL,
    commission_bps=COMMISSION_BPS,
    slippage_bps=SLIPPAGE_BPS
)

print(f"[OK] Bollinger Bands completed")
print(f"     Return: {results_bb['total_return']*100:>7.2f}%")
print(f"     Sharpe: {results_bb['sharpe_ratio']:>7.2f}")
print(f"     Trades: {results_bb['total_trades']:>7}")
print()

# ===========================
# BUY & HOLD BENCHMARK
# ===========================

print("=" * 80)
print("Step 5: Buy & Hold Benchmark")
print("=" * 80)
print()

buy_hold_return = (backtest_df['close'].iloc[-1] / backtest_df['close'].iloc[0]) - 1

print(f"[OK] Buy & Hold Return: {buy_hold_return*100:.2f}%")
print()

# ===========================
# COMPARISON TABLE
# ===========================

print("=" * 80)
print("SRAVNENIE VSEKH STRATEGIY")
print("=" * 80)
print()

strategies = [
    ("RSI Mean-Reversion", results_rsi),
    ("EMA Crossover", results_ema),
    ("Bollinger Bands", results_bb),
]

# Sort by Sharpe Ratio
strategies_sorted = sorted(strategies, key=lambda x: x[1]['sharpe_ratio'], reverse=True)

print(f"{'Strategy':<25} {'Sharpe':>8} {'Return':>8} {'Max DD':>8} {'Trades':>8} {'Win Rate':>10}")
print("-" * 95)

for name, result in strategies_sorted:
    sharpe = result['sharpe_ratio']
    ret = result['total_return'] * 100
    max_dd = result['max_drawdown'] * 100
    trades = result['total_trades']
    win_rate = result['win_rate'] * 100
    
    print(f"{name:<25} {sharpe:>8.2f} {ret:>7.2f}% {max_dd:>7.2f}% {trades:>8} {win_rate:>9.1f}%")

print(f"{'Buy & Hold (benchmark)':<25} {'N/A':>8} {buy_hold_return*100:>7.2f}% {'N/A':>8} {'1':>8} {'N/A':>10}")
print()

# ===========================
# BEST STRATEGY
# ===========================

best_name, best_result = strategies_sorted[0]

print("=" * 80)
print(f"LUCHSHAYA STRATEGIYA: {best_name}")
print("=" * 80)
print()

print("DOKHODNOST':")
print(f"   Total Return:       {best_result['total_return']*100:>8.2f}%")
print(f"   Final Capital:      ${best_result['final_capital']:>11,.2f}")
print(f"   Profit/Loss:        ${(best_result['final_capital'] - INITIAL_CAPITAL):>11,.2f}")
print()

print("SRAVNENIE S RYNKOM:")
print(f"   Buy & Hold:         {buy_hold_return*100:>8.2f}%")
print(f"   Outperformance:     {(best_result['total_return'] - buy_hold_return)*100:>8.2f}%")
if best_result['total_return'] > buy_hold_return:
    print(f"   Status:             [OK] Beats benchmark!")
else:
    print(f"   Status:             [WARNING] Underperforms")
print()

print("RISK-METRIKI:")
print(f"   Sharpe Ratio:       {best_result['sharpe_ratio']:>11.4f}")
print(f"   Sortino Ratio:      {best_result['sortino_ratio']:>11.4f}")
print(f"   Calmar Ratio:       {best_result['calmar_ratio']:>11.4f}")
print(f"   Max Drawdown:       {best_result['max_drawdown']*100:>8.2f}%")
print()

print("TORGOVAYA STATISTIKA:")
print(f"   Total Trades:       {best_result['total_trades']:>11}")
print(f"   Winning Trades:     {best_result['winning_trades']:>11}")
print(f"   Losing Trades:      {best_result['losing_trades']:>11}")
print(f"   Win Rate:           {best_result['win_rate']*100:>8.2f}%")
print(f"   Avg Win:            {best_result['avg_win']*100:>8.2f}%")
print(f"   Avg Loss:           {best_result['avg_loss']*100:>8.2f}%")
print(f"   Profit Factor:      {best_result['profit_factor']:>11.2f}")
print()

# ===========================
# GOAL CHECK
# ===========================

print("=" * 80)
print("PROVERKA TSELEY")
print("=" * 80)
print()

sharpe_goal = 1.0
return_goal = 0.03

print(f"Sharpe Ratio: {best_result['sharpe_ratio']:.4f} (tsel': >{sharpe_goal})")
if best_result['sharpe_ratio'] > sharpe_goal:
    print("  [SUCCESS] TSEL' DOSTIGNUT!")
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {sharpe_goal - best_result['sharpe_ratio']:.4f})")

print()

print(f"Total Return: {best_result['total_return']*100:.2f}% (tsel': >{return_goal*100:.0f}%)")
if best_result['total_return'] > return_goal:
    print("  [SUCCESS] TSEL' DOSTIGNUT!")
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {(return_goal - best_result['total_return'])*100:.1f}%)")

print()

# ===========================
# FINAL VERDICT
# ===========================

print("=" * 80)
print("ITOGOVAYA OTSENKA")
print("=" * 80)
print()

if best_result['sharpe_ratio'] > 1.0 and best_result['total_return'] > 0.03:
    print("[SUCCESS] STRATEGIYA RABOTAET!")
    print(f"     Ispol'zuy: {best_name}")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Deploy v paper trading")
    print("  2. Monitor 7 dney")
    print("  3. Profit!")

elif best_result['sharpe_ratio'] > 0.5 or best_result['total_return'] > 0:
    print("[PARTIAL SUCCESS] STRATEGIYA RABOTAET, NO SLABO")
    print(f"     Luchshaya: {best_name}")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Mozhno ispol'zovat' v paper trading")
    print("  2. Ili poprobovat' Variant A (12 mesyatsev dannykh)")
    print("  3. Ili nastroit' parametry strategiy")

else:
    print("[FAIL] VSE STRATEGII UBYTOCHNY")
    print()
    print("VYVOD:")
    print("  - Rynok byl v downtrende (Buy & Hold: {:.2f}%)".format(buy_hold_return*100))
    print("  - Period 89 dney nedostatochno")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Variant A: Zagruzit' 12 mesyatsev dannykh")
    print("  2. Testirov at' na drugom periode")
    print("  3. Ili ispol'zovat' dlya long-only v bull market")

print()

# ===========================
# SAVE RESULTS
# ===========================

results_data = {
    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "exchange": EXCHANGE,
    "symbol": SYMBOL,
    "timeframe": TIMEFRAME,
    "backtest_samples": len(backtest_df),
    "period": {
        "start": str(backtest_df.index.min()),
        "end": str(backtest_df.index.max())
    },
    "buy_hold_return": float(buy_hold_return),
    "strategies": {
        name: {
            "sharpe_ratio": float(result['sharpe_ratio']),
            "total_return": float(result['total_return']),
            "max_drawdown": float(result['max_drawdown']),
            "win_rate": float(result['win_rate']),
            "profit_factor": float(result['profit_factor']),
            "total_trades": result['total_trades']
        }
        for name, result in strategies
    },
    "best_strategy": best_name,
    "best_metrics": {
        "sharpe_ratio": float(best_result['sharpe_ratio']),
        "total_return": float(best_result['total_return']),
        "max_drawdown": float(best_result['max_drawdown']),
        "win_rate": float(best_result['win_rate']),
        "profit_factor": float(best_result['profit_factor']),
        "total_trades": best_result['total_trades']
    }
}

artifacts_dir = Path("artifacts/backtest")
artifacts_dir.mkdir(parents=True, exist_ok=True)

results_path = artifacts_dir / f"simple_strategies_{results_data['timestamp']}.json"

with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2, ensure_ascii=False)

print("=" * 80)
print(f"[OK] Rezul'taty sokhraneny: {results_path.name}")
print("=" * 80)
print()

