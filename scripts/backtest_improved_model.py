"""
Бэктестинг улучшенной модели с новыми фичами.
Цель: Sharpe >1.5, Return >5%
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from xgboost import XGBClassifier

from dotenv import load_dotenv
load_dotenv()

from src.db import SessionLocal
from src.features import build_dataset
from src.modeling import time_split
from src.backtest import run_vectorized_backtest

ARTIFACTS_DIR = Path("artifacts") / "backtest"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("BACKTEST: IMPROVED MODEL WITH NEW FEATURES")
    print("=" * 80)
    print("Target: Sharpe >1.5, Return >5%")
    print()
    
    # 1. Загрузка датасета
    print("[1/4] Loading dataset...")
    db = SessionLocal()
    try:
        df, feature_cols = build_dataset(
            db=db,
            exchange="bybit",
            symbol="BTC/USDT",
            timeframe="1h",
            horizon_steps=4,
        )
    finally:
        db.close()
    
    print(f"Dataset: {len(df)} rows x {len(feature_cols)} features")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print()
    
    # 2. Обучение модели (на первых 80% данных)
    print("[2/4] Training model on 80% of data...")
    train_df, test_df = time_split(df, test_ratio=0.2)
    
    X_train = train_df[feature_cols]
    y_train = train_df["y"].values
    X_test = test_df[feature_cols]
    y_test = test_df["y"].values
    
    # Обучаем XGBoost с улучшенными параметрами
    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    
    # Генерируем предсказания на test set
    proba = model.predict_proba(X_test)[:, 1]
    
    print(f"Train samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    print()
    
    # 3. Простой бэктест
    print("[3/4] Running simple backtest on test set...")
    
    # Подготовка
    backtest_df = test_df[["close", "future_ret"]].copy()
    backtest_df["signal_prob"] = proba
    backtest_df["signal"] = (proba > 0.5).astype(int)
    
    # Ручной простой бэктест
    initial_capital = 10000
    capital = initial_capital
    position = 0
    equity = []
    trades = []
    
    for idx, row in backtest_df.iterrows():
        # BUY signal
        if row["signal"] == 1 and position == 0:
            position = capital / row["close"]
            entry_price = row["close"]
            trades.append({"entry": entry_price, "exit": None})
        
        # Exit (sell after future_ret period)
        elif position > 0:
            exit_price = row["close"]
            pnl = (exit_price - trades[-1]["entry"]) / trades[-1]["entry"]
            trades[-1]["exit"] = exit_price
            trades[-1]["pnl"] = pnl
            capital = position * exit_price
            position = 0
        
        # Track equity
        current_equity = capital if position == 0 else position * row["close"]
        equity.append(current_equity)
    
    # Calculate returns
    equity_series = pd.Series(equity)
    returns = equity_series.pct_change().dropna()
    
    # Metrics
    total_return = (equity_series.iloc[-1] / initial_capital) - 1
    sharpe = returns.mean() / (returns.std() + 1e-9) * np.sqrt(252 * 24)  # annualized
    
    # Sortino (только downside vol)
    downside_returns = returns[returns < 0]
    sortino = returns.mean() / (downside_returns.std() + 1e-9) * np.sqrt(252 * 24)
    
    # Max Drawdown
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_dd = drawdown.min()
    
    # Calmar
    calmar = (total_return / (abs(max_dd) + 1e-9)) if max_dd < 0 else 0
    
    # Trade stats
    completed_trades = [t for t in trades if t["exit"] is not None]
    wins = [t for t in completed_trades if t["pnl"] > 0]
    losses = [t for t in completed_trades if t["pnl"] <= 0]
    win_rate = len(wins) / max(len(completed_trades), 1)
    
    total_wins = sum([t["pnl"] for t in wins]) if wins else 0
    total_losses = abs(sum([t["pnl"] for t in losses])) if losses else 1e-9
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    results = {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": len(completed_trades),
    }
    
    # 4. Вывод результатов
    print("\n[4/4] Results:")
    print("-" * 80)
    print(f"{'Metric':<30} {'Value':<20}")
    print("-" * 80)
    print(f"{'Total Return':<30} {results['total_return']*100:>18.2f}%")
    print(f"{'Sharpe Ratio':<30} {results['sharpe_ratio']:>20.4f}")
    print(f"{'Sortino Ratio':<30} {results['sortino_ratio']:>20.4f}")
    print(f"{'Calmar Ratio':<30} {results['calmar_ratio']:>20.4f}")
    print(f"{'Max Drawdown':<30} {results['max_drawdown']*100:>18.2f}%")
    print(f"{'Win Rate':<30} {results['win_rate']*100:>18.2f}%")
    print(f"{'Profit Factor':<30} {results['profit_factor']:>20.2f}")
    print(f"{'Total Trades':<30} {results['total_trades']:>20}")
    print("-" * 80)
    
    # Проверка целей
    print("\nGoal Check:")
    sharpe_ok = results['sharpe_ratio'] >= 1.5
    return_ok = results['total_return'] >= 0.05
    
    print(f"  Sharpe >1.5: {'✓' if sharpe_ok else '✗'} ({results['sharpe_ratio']:.2f})")
    print(f"  Return >5%:  {'✓' if return_ok else '✗'} ({results['total_return']*100:.2f}%)")
    
    if sharpe_ok and return_ok:
        print("\n🎉 SUCCESS! Model meets both goals!")
    else:
        print("\n⚠ Model needs further improvement.")
    
    # Сохранение результатов
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_path = ARTIFACTS_DIR / f"backtest_improved_{timestamp}.json"
    
    # Prepare results for JSON
    results_json = {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v 
                    for k, v in results.items()}
    results_json["timestamp"] = timestamp
    results_json["n_features"] = len(feature_cols)
    results_json["train_samples"] = len(X_train)
    results_json["test_samples"] = len(X_test)
    
    with open(results_path, "w") as f:
        json.dump(results_json, f, indent=2)
    
    print(f"\n✅ Results saved: {results_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

