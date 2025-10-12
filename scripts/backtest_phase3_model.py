#!/usr/bin/env python3
"""
Backtest PHASE 3 модели (LightGBM CV)

Модель: ensemble_lightgbm_cv_20251012_211339.pkl
Test AUC: 0.5129
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
print(" " * 20 + "BACKTEST PHASE 3 МОДЕЛИ")
print("=" * 80)
print()

# ===========================
# CONFIGURATION
# ===========================

EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"

# PHASE 3 модель (LightGBM)
MODEL_PATH = Path("artifacts/ensemble_lightgbm_cv_20251012_211339.pkl")

INITIAL_CAPITAL = 10000.0
COMMISSION_BPS = 8.0  # 0.08% Bybit taker
SLIPPAGE_BPS = 5.0    # 0.05%
THRESHOLD = 0.5       # Buy if prob > 0.5

print(f"Конфигурация:")
print(f"  Exchange:     {EXCHANGE}")
print(f"  Symbol:       {SYMBOL}")
print(f"  Timeframe:    {TIMEFRAME}")
print(f"  Модель:       {MODEL_PATH.name}")
print(f"  Капитал:      ${INITIAL_CAPITAL:,.2f}")
print(f"  Комиссия:     {COMMISSION_BPS} bps")
print(f"  Проскальз.:   {SLIPPAGE_BPS} bps")
print(f"  Threshold:    {THRESHOLD}")
print()

# ===========================
# LOAD MODEL
# ===========================

print("=" * 80)
print("Шаг 1: Загрузка модели")
print("=" * 80)
print()

if not MODEL_PATH.exists():
    print(f"[!] Модель не найдена: {MODEL_PATH}")
    print("    Запусти обучение PHASE 3:")
    print("    python scripts\\train_ensemble_cross_validation.py")
    sys.exit(1)

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

print(f"[OK] Модель загружена: {MODEL_PATH.name}")
print(f"     Размер: {MODEL_PATH.stat().st_size / 1024:.1f} KB")
print()

# ===========================
# LOAD DATASET
# ===========================

print("=" * 80)
print("Шаг 2: Загрузка данных")
print("=" * 80)
print()

db = SessionLocal()

try:
    df, feature_cols = build_dataset(
        db=db,
        exchange=EXCHANGE,
        symbol=SYMBOL,
        timeframe=TIMEFRAME
    )
except Exception as e:
    print(f"[!] Ошибка загрузки данных: {e}")
    sys.exit(1)
finally:
    db.close()

print(f"[OK] Datset zagruzhen: {len(df)} rows x {len(feature_cols)} features")
print(f"     Period: {df.index.min()} - {df.index.max()}")
print()

# Split для backtest (используем последние 20% как test)
split_idx = int(len(df) * 0.8)
backtest_df = df.iloc[split_idx:].copy()

print(f"[OK] Backtest period: {len(backtest_df)} rows")
print(f"     Dates: {backtest_df.index.min()} - {backtest_df.index.max()}")
print()

# ===========================
# GENERATE SIGNALS
# ===========================

print("=" * 80)
print("Шаг 3: Генерация сигналов")
print("=" * 80)
print()

X_backtest = backtest_df[feature_cols]

try:
    signal_proba = model.predict_proba(X_backtest)[:, 1]
    print(f"[OK] Сигналы сгенерированы: {len(signal_proba)} predictions")
except Exception as e:
    print(f"[!] Ошибка предсказания: {e}")
    sys.exit(1)

backtest_df["signal_prob"] = signal_proba
backtest_df["signal"] = (signal_proba > THRESHOLD).astype(int)

print(f"     Сигналов BUY: {(backtest_df['signal'] == 1).sum()}")
print(f"     Сигналов HOLD: {(backtest_df['signal'] == 0).sum()}")
print()

# ===========================
# RUN BACKTEST
# ===========================

print("=" * 80)
print("Шаг 4: Запуск симуляции")
print("=" * 80)
print()

# Простая векторизованная симуляция
prices = backtest_df["close"].values
signals = backtest_df["signal"].values

capital = INITIAL_CAPITAL
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
        # Calculate position size (full capital)
        commission = (COMMISSION_BPS + SLIPPAGE_BPS) / 10000
        position_size = capital * (1 - commission)  # После комиссий
        position = position_size / price  # Количество монет
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
    
    # Exit (на следующем сигнале или в конце)
    elif position > 0 and (signal == 0 or i == len(prices) - 1):
        # Выход из позиции
        commission = (COMMISSION_BPS + SLIPPAGE_BPS) / 10000
        capital = position * price * (1 - commission)
        
        # Записываем результат сделки
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

# ===========================
# CALCULATE METRICS
# ===========================

print("=" * 80)
print("Шаг 5: Расчет метрик")
print("=" * 80)
print()

equity_series = pd.Series(equity_curve)
returns = equity_series.pct_change().dropna()

# Performance
total_return = (equity_series.iloc[-1] / INITIAL_CAPITAL) - 1
final_capital = equity_series.iloc[-1]

# Risk-adjusted
sharpe_ratio = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252 * 24)  # annualized

downside_returns = returns[returns < 0]
sortino_ratio = (returns.mean() / (downside_returns.std() + 1e-9)) * np.sqrt(252 * 24) if len(downside_returns) > 0 else 0.0

# Drawdown
cummax = equity_series.cummax()
drawdown = (equity_series - cummax) / cummax
max_drawdown = drawdown.min()

calmar_ratio = (total_return / (abs(max_drawdown) + 1e-9)) if max_drawdown < 0 else 0.0

# Trade stats
completed_trades = [t for t in trades_history if t["exit_price"] is not None]
winning_trades = [t for t in completed_trades if t["pnl"] > 0]
losing_trades = [t for t in completed_trades if t["pnl"] <= 0]

win_rate = len(winning_trades) / max(len(completed_trades), 1)

avg_win = np.mean([t["pnl_pct"] for t in winning_trades]) if winning_trades else 0.0
avg_loss = np.mean([t["pnl_pct"] for t in losing_trades]) if losing_trades else 0.0

total_wins = sum([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
total_losses = abs(sum([t["pnl"] for t in losing_trades])) if losing_trades else 1e-9
profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

# Buy & Hold benchmark
buy_hold_return = (prices[-1] / prices[0]) - 1

print("[OK] Метрики рассчитаны")
print()

# ===========================
# DISPLAY RESULTS
# ===========================

print("=" * 80)
print("РЕЗУЛЬТАТЫ BACKTEST")
print("=" * 80)
print()

print("DOKHODNOST':")
print(f"   Total Return:       {total_return*100:>8.2f}%")
print(f"   Final Capital:      ${final_capital:>11,.2f}")
print(f"   Profit/Loss:        ${(final_capital - INITIAL_CAPITAL):>11,.2f}")
print()

print("SRAVNENIE S RYNKOM:")
print(f"   Buy & Hold Return:  {buy_hold_return*100:>8.2f}%")
print(f"   Outperformance:     {(total_return - buy_hold_return)*100:>8.2f}%")
if total_return > buy_hold_return:
    print(f"   Status:             [OK] Prevoskhodit rynok!")
else:
    print(f"   Status:             [WARNING] Ustupaet rynku")
print()

print("RISK-METRIKI:")
print(f"   Sharpe Ratio:       {sharpe_ratio:>11.4f}")
print(f"   Sortino Ratio:      {sortino_ratio:>11.4f}")
print(f"   Calmar Ratio:       {calmar_ratio:>11.4f}")
print(f"   Max Drawdown:       {max_drawdown*100:>8.2f}%")
print()

print("TORGOVAYA STATISTIKA:")
print(f"   Total Trades:       {len(completed_trades):>11}")
print(f"   Winning Trades:     {len(winning_trades):>11}")
print(f"   Losing Trades:      {len(losing_trades):>11}")
print(f"   Win Rate:           {win_rate*100:>8.2f}%")
print(f"   Avg Win:            {avg_win*100:>8.2f}%")
print(f"   Avg Loss:           {avg_loss*100:>8.2f}%")
print(f"   Profit Factor:      {profit_factor:>11.2f}")
print()

# ===========================
# GOAL CHECK
# ===========================

print("=" * 80)
print("ПРОВЕРКА ЦЕЛЕЙ")
print("=" * 80)
print()

sharpe_goal = 1.0
return_goal = 0.03

print(f"Sharpe Ratio: {sharpe_ratio:.4f} (tsel': >{sharpe_goal})")
if sharpe_ratio > sharpe_goal:
    print("  [SUCCESS] TSEL' DOSTIGNUT!")
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {sharpe_goal - sharpe_ratio:.4f})")

print()

print(f"Total Return: {total_return*100:.2f}% (tsel': >{return_goal*100:.0f}%)")
if total_return > return_goal:
    print("  [SUCCESS] TSEL' DOSTIGNUT!")
else:
    print(f"  [WARNING] Ne dostignut (ne khvataet {(return_goal - total_return)*100:.1f}%)")

print()

# ===========================
# FINAL VERDICT
# ===========================

print("=" * 80)
print("ITOGOVAYA OTSENKA")
print("=" * 80)
print()

if sharpe_ratio > 1.5 and total_return > 0.05:
    print("[OTLICHNO] OTLICHNYY REZUL'TAT!")
    print("     Model' prevoskhodit vse ozhidaniya")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Deploy v paper trading")
    print("  2. Monitor 7 dney")
    print("  3. Zapusk na production!")

elif sharpe_ratio > 1.0 and total_return > 0.03:
    print("[SUCCESS] KHOROSHIY REZUL'TAT!")
    print("     Model' dostigla tseley")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Deploy v paper trading")
    print("  2. Monitor 7 dney")
    print("  3. Fine-tune esli nuzhno")

elif sharpe_ratio > 0.5 or total_return > 0:
    print("[WARNING] PRIEMLEMYY REZUL'TAT")
    print("     Model' rabotaet, no nizhe tseli")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Mozhno ispol'zovat' v paper trading")
    print("  2. Threshold optimization (0.45-0.65)")
    print("  3. Zagruzit' bol'she dannykh (6-12 mesyatsev)")

else:
    print("[FAIL] NEDOSTATOCHNYY REZUL'TAT")
    print("     Model' ubytochna na backtest")
    print()
    print("SLEDUYUSHCHIE SHAGI:")
    print("  1. Zagruzit' bol'she istoricheskikh dannykh")
    print("  2. Poprobovat' drugie horizon_steps (12h, 24h)")
    print("  3. Feature engineering (novye fichi)")

print()

# ===========================
# SAVE RESULTS
# ===========================

results = {
    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "model": MODEL_PATH.name,
    "exchange": EXCHANGE,
    "symbol": SYMBOL,
    "timeframe": TIMEFRAME,
    "backtest_samples": len(backtest_df),
    "period": {
        "start": str(backtest_df.index.min()),
        "end": str(backtest_df.index.max())
    },
    "config": {
        "initial_capital": INITIAL_CAPITAL,
        "commission_bps": COMMISSION_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "threshold": THRESHOLD
    },
    "performance": {
        "total_return": float(total_return),
        "final_capital": float(final_capital),
        "buy_hold_return": float(buy_hold_return),
        "outperformance": float(total_return - buy_hold_return),
        "beats_benchmark": bool(total_return > buy_hold_return)
    },
    "risk_metrics": {
        "sharpe_ratio": float(sharpe_ratio),
        "sortino_ratio": float(sortino_ratio),
        "calmar_ratio": float(calmar_ratio),
        "max_drawdown": float(max_drawdown)
    },
    "trade_stats": {
        "total_trades": len(completed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": float(win_rate),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "profit_factor": float(profit_factor)
    }
}

# Сохранение
artifacts_dir = Path("artifacts/backtest")
artifacts_dir.mkdir(parents=True, exist_ok=True)

results_path = artifacts_dir / f"phase3_backtest_{results['timestamp']}.json"

with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("=" * 80)
print(f"[OK] Результаты сохранены: {results_path}")
print("=" * 80)
print()

