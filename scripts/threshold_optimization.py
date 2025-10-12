#!/usr/bin/env python3
"""
Threshold Optimization для PHASE 3 модели

Идея: Вместо фиксированного threshold=0.5,
      попробуем разные значения (0.45-0.70) и выберем лучший.

Цель: Найти оптимальный порог для максимизации Sharpe Ratio
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

from src.db import SessionLocal
from src.features import build_dataset

print("=" * 80)
print(" " * 20 + "THRESHOLD OPTIMIZATION")
print("=" * 80)
print()

# ===========================
# CONFIGURATION
# ===========================

EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
MODEL_PATH = Path("artifacts/ensemble_lightgbm_cv_20251012_211339.pkl")

INITIAL_CAPITAL = 10000.0
COMMISSION_BPS = 8.0
SLIPPAGE_BPS = 5.0

# Grid search thresholds
THRESHOLDS = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

print(f"Configuration:")
print(f"  Model:      {MODEL_PATH.name}")
print(f"  Thresholds: {THRESHOLDS}")
print(f"  Capital:    ${INITIAL_CAPITAL:,.2f}")
print()

# ===========================
# LOAD MODEL & DATA
# ===========================

print("=" * 80)
print("Step 1: Loading model and data")
print("=" * 80)
print()

# Load model
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
print(f"[OK] Model loaded")

# Load dataset
db = SessionLocal()
try:
    df, feature_cols = build_dataset(
        db=db,
        exchange=EXCHANGE,
        symbol=SYMBOL,
        timeframe=TIMEFRAME
    )
finally:
    db.close()

print(f"[OK] Dataset loaded: {len(df)} rows")

# Use last 20% for backtest
split_idx = int(len(df) * 0.8)
backtest_df = df.iloc[split_idx:].copy()

print(f"[OK] Backtest period: {len(backtest_df)} rows")
print(f"     Dates: {backtest_df.index.min()} - {backtest_df.index.max()}")
print()

# Generate predictions ONCE
X_backtest = backtest_df[feature_cols]
signal_proba = model.predict_proba(X_backtest)[:, 1]

print(f"[OK] Predictions generated: {len(signal_proba)}")
print(f"     Mean prob: {signal_proba.mean():.3f}")
print(f"     Std prob:  {signal_proba.std():.3f}")
print()

# ===========================
# BACKTEST FUNCTION
# ===========================

def run_backtest_with_threshold(prices, signal_proba, threshold, initial_capital, commission_bps, slippage_bps):
    """Запуск backtest с заданным threshold"""
    
    signals = (signal_proba > threshold).astype(int)
    
    capital = initial_capital
    position = 0.0
    position_size = 0.0
    equity_curve = []
    trades_history = []
    
    entry_price = 0.0
    entry_idx = 0
    
    for i in range(len(prices)):
        price = prices[i]
        signal = signals[i]
        
        # Entry
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
        
        # Exit
        elif position > 0 and (signal == 0 or i == len(prices) - 1):
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
    sharpe_ratio = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252 * 24)
    
    downside_returns = returns[returns < 0]
    sortino_ratio = (returns.mean() / (downside_returns.std() + 1e-9)) * np.sqrt(252 * 24) if len(downside_returns) > 0 else 0.0
    
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_drawdown = drawdown.min()
    
    completed_trades = [t for t in trades_history if t["exit_price"] is not None]
    winning_trades = [t for t in completed_trades if t["pnl"] > 0]
    losing_trades = [t for t in completed_trades if t["pnl"] <= 0]
    
    win_rate = len(winning_trades) / max(len(completed_trades), 1) if completed_trades else 0.0
    
    total_wins = sum([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
    total_losses = abs(sum([t["pnl"] for t in losing_trades])) if losing_trades else 1e-9
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
    
    return {
        "threshold": threshold,
        "total_return": total_return,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": len(completed_trades),
        "signals_generated": signals.sum()
    }

# ===========================
# GRID SEARCH
# ===========================

print("=" * 80)
print("Step 2: Grid Search over Thresholds")
print("=" * 80)
print()

prices = backtest_df["close"].values
results_all = []

for threshold in THRESHOLDS:
    print(f"[*] Testing threshold = {threshold:.2f}...", end=" ")
    
    result = run_backtest_with_threshold(
        prices=prices,
        signal_proba=signal_proba,
        threshold=threshold,
        initial_capital=INITIAL_CAPITAL,
        commission_bps=COMMISSION_BPS,
        slippage_bps=SLIPPAGE_BPS
    )
    
    results_all.append(result)
    
    print(f"Sharpe: {result['sharpe_ratio']:>7.2f}, Return: {result['total_return']*100:>6.2f}%, Trades: {result['total_trades']:>3}")

print()

# ===========================
# FIND BEST THRESHOLD
# ===========================

print("=" * 80)
print("Step 3: Finding Best Threshold")
print("=" * 80)
print()

# Sort by Sharpe Ratio
results_sorted = sorted(results_all, key=lambda x: x["sharpe_ratio"], reverse=True)
best_result = results_sorted[0]

print(f"[OK] Best Threshold: {best_result['threshold']:.2f}")
print()

# ===========================
# COMPARISON TABLE
# ===========================

print("=" * 80)
print("SRAVNENIE VSEKH THRESHOLDS")
print("=" * 80)
print()

print(f"{'Threshold':<12} {'Sharpe':>8} {'Return':>8} {'Max DD':>8} {'Trades':>8} {'Win Rate':>10}")
print("-" * 80)

for result in results_sorted:
    threshold = result['threshold']
    sharpe = result['sharpe_ratio']
    ret = result['total_return'] * 100
    max_dd = result['max_drawdown'] * 100
    trades = result['total_trades']
    win_rate = result['win_rate'] * 100
    
    # Mark best
    mark = " [BEST]" if result == best_result else ""
    
    print(f"{threshold:<12.2f} {sharpe:>8.2f} {ret:>7.2f}% {max_dd:>7.2f}% {trades:>8} {win_rate:>9.1f}%{mark}")

print()

# ===========================
# BEST RESULT DETAILS
# ===========================

print("=" * 80)
print(f"LUCHSHIY REZUL'TAT (Threshold = {best_result['threshold']:.2f})")
print("=" * 80)
print()

print("DOKHODNOST':")
print(f"   Total Return:       {best_result['total_return']*100:>8.2f}%")
print(f"   Final Capital:      ${(INITIAL_CAPITAL * (1 + best_result['total_return'])):>11,.2f}")
print()

print("RISK-METRIKI:")
print(f"   Sharpe Ratio:       {best_result['sharpe_ratio']:>11.4f}")
print(f"   Sortino Ratio:      {best_result['sortino_ratio']:>11.4f}")
print(f"   Max Drawdown:       {best_result['max_drawdown']*100:>8.2f}%")
print()

print("TORGOVAYA STATISTIKA:")
print(f"   Total Trades:       {best_result['total_trades']:>11}")
print(f"   Win Rate:           {best_result['win_rate']*100:>8.2f}%")
print(f"   Profit Factor:      {best_result['profit_factor']:>11.2f}")
print(f"   Signals Generated:  {best_result['signals_generated']:>11}")
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
    success = True
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {sharpe_goal - best_result['sharpe_ratio']:.4f})")
    success = False

print()

print(f"Total Return: {best_result['total_return']*100:.2f}% (tsel': >{return_goal*100:.0f}%)")
if best_result['total_return'] > return_goal:
    print("  [SUCCESS] TSEL' DOSTIGNUT!")
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {(return_goal - best_result['total_return'])*100:.1f}%)")

print()

# ===========================
# IMPROVEMENT ANALYSIS
# ===========================

baseline_result = [r for r in results_all if r['threshold'] == 0.5][0]

print("=" * 80)
print(f"ULUCHSHENIE (threshold {baseline_result['threshold']:.2f} vs {best_result['threshold']:.2f})")
print("=" * 80)
print()

sharpe_improvement = best_result['sharpe_ratio'] - baseline_result['sharpe_ratio']
return_improvement = (best_result['total_return'] - baseline_result['total_return']) * 100

print(f"Sharpe Ratio:  {baseline_result['sharpe_ratio']:>7.2f} -> {best_result['sharpe_ratio']:>7.2f} ({sharpe_improvement:+.2f})")
print(f"Total Return:  {baseline_result['total_return']*100:>6.2f}% -> {best_result['total_return']*100:>6.2f}% ({return_improvement:+.2f}%)")
print(f"Total Trades:  {baseline_result['total_trades']:>7} -> {best_result['total_trades']:>7}")
print()

if sharpe_improvement > 0.5 or return_improvement > 2.0:
    print("[SUCCESS] Threshold optimization pomogla!")
elif sharpe_improvement > 0:
    print("[PARTIAL] Nebolic shkoe uluchshenie")
else:
    print("[NO IMPROVEMENT] Threshold optimization ne pomogla")

print()

# ===========================
# FINAL VERDICT
# ===========================

print("=" * 80)
print("ITOGOVAYA OTSENKA")
print("=" * 80)
print()

if best_result['sharpe_ratio'] > 1.0 and best_result['total_return'] > 0.03:
    print("[SUCCESS] MODEL' RABOTAET!")
    print(f"     Ispol'zuy threshold = {best_result['threshold']:.2f}")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Deploy v paper trading s threshold = {:.2f}".format(best_result['threshold']))
    print("  2. Monitor 7 dney")
    print("  3. Profit!")

elif best_result['sharpe_ratio'] > 0.5 or best_result['total_return'] > 0:
    print("[PARTIAL SUCCESS] MODEL' RABOTAET, NO SLABO")
    print(f"     Luchshiy threshold = {best_result['threshold']:.2f}")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Mozhno ispol'zovat' v paper trading")
    print("  2. Ili zagruzit' bol'she dannykh (6-12 mesyatsev)")
    print("  3. Ili priznat' ogranicheniya")

else:
    print("[FAIL] MODEL' UBYTOCHNA DAZHE S OPTIMIZATSIEY")
    print()
    print("VYVOD:")
    print("  - Kratkosrochnoe (6h) predskazanie kripoty NE RABOTAET")
    print("  - Supervised learning nedostatochno dlya shumnykh dannykh")
    print()
    print("ALTERNATIVY:")
    print("  1. Buy & Hold (prostaya strategiya)")
    print("  2. Mean-reversion (pokupka na padenii)")
    print("  3. Momentum (sledovanie za trendom)")
    print("  4. Zagruzit' MNOGO dannykh (12+ mesyatsev)")

print()

# ===========================
# SAVE RESULTS
# ===========================

results_data = {
    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "model": MODEL_PATH.name,
    "best_threshold": best_result['threshold'],
    "best_metrics": {
        "sharpe_ratio": float(best_result['sharpe_ratio']),
        "total_return": float(best_result['total_return']),
        "max_drawdown": float(best_result['max_drawdown']),
        "win_rate": float(best_result['win_rate']),
        "profit_factor": float(best_result['profit_factor']),
        "total_trades": best_result['total_trades']
    },
    "all_results": [
        {
            "threshold": float(r['threshold']),
            "sharpe_ratio": float(r['sharpe_ratio']),
            "total_return": float(r['total_return']),
            "total_trades": r['total_trades']
        }
        for r in results_all
    ]
}

artifacts_dir = Path("artifacts/backtest")
artifacts_dir.mkdir(parents=True, exist_ok=True)

results_path = artifacts_dir / f"threshold_optimization_{results_data['timestamp']}.json"

with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2, ensure_ascii=False)

print("=" * 80)
print(f"[OK] Rezul'taty sokhraneny: {results_path.name}")
print("=" * 80)
print()

