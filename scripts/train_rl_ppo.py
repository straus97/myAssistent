#!/usr/bin/env python3
"""
RL-ПОДХОД: Обучение PPO agent для крипто-трейдинга

ПОЧЕМУ RL МОЖЕТ РАБОТАТЬ ЛУЧШЕ SUPERVISED LEARNING:

1. Не требует предсказания цены
   - Supervised: Предсказать UP/DOWN (сложно на шумных данных)
   - RL: Оптимизировать Sharpe Ratio напрямую

2. Адаптируется к рынку
   - Supervised: Статичная модель
   - RL: Continuous learning

3. Оптимизирует портфельное управление
   - Supervised: Только direction
   - RL: Direction + sizing + timing

ЦЕЛЬ:
- Sharpe Ratio >1.0
- Total Return >5%
- Adaptive position sizing
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db import SessionLocal
from src.features import build_dataset
from src.rl_agent import RLAgent

print("=" * 80)
print(" " * 20 + "RL-ПОДХОД: PPO Agent Training")
print("=" * 80)
print()

# ===========================
# CONFIGURATION
# ===========================

parser = argparse.ArgumentParser()
parser.add_argument("--exchange", default="bybit", help="Exchange (bybit/binance)")
parser.add_argument("--symbol", default="BTC/USDT", help="Trading pair")
parser.add_argument("--timeframe", default="1h", help="Timeframe")
parser.add_argument("--timesteps", type=int, default=500000, help="Total timesteps (500K recommended)")
parser.add_argument("--initial-capital", type=float, default=1000.0, help="Initial capital")
parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate")
args = parser.parse_args()

EXCHANGE = args.exchange
SYMBOL = args.symbol
TIMEFRAME = args.timeframe
TOTAL_TIMESTEPS = args.timesteps
INITIAL_CAPITAL = args.initial_capital
LEARNING_RATE = args.learning_rate

ARTIFACTS_DIR = project_root / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

print(f"Configuration:")
print(f"  - Exchange: {EXCHANGE}")
print(f"  - Symbol: {SYMBOL}")
print(f"  - Timeframe: {TIMEFRAME}")
print(f"  - Total Timesteps: {TOTAL_TIMESTEPS:,}")
print(f"  - Initial Capital: ${INITIAL_CAPITAL:,.2f}")
print(f"  - Learning Rate: {LEARNING_RATE}")
print()

# ===========================
# LOAD DATA
# ===========================

print("=" * 80)
print("Step 1: Loading Dataset")
print("=" * 80)
print()

db = SessionLocal()

try:
    df, feature_list = build_dataset(
        db=db,
        exchange=EXCHANGE,
        symbol=SYMBOL,
        timeframe=TIMEFRAME
    )
    print(f"[OK] Dataset loaded: {len(df)} rows x {len(feature_list)} features")
    print(f"     Date range: {df.index.min()} to {df.index.max()}")
    print()
finally:
    db.close()

# ===========================
# INITIALIZE RL AGENT
# ===========================

print("=" * 80)
print("Step 2: Initializing PPO Agent")
print("=" * 80)
print()

agent = RLAgent(
    model_dir=str(ARTIFACTS_DIR / "rl_models"),
    tensorboard_dir=str(ARTIFACTS_DIR / "tensorboard")
)

print("[OK] RL Agent initialized")
print(f"     Model dir: {agent.model_dir}")
print(f"     Tensorboard dir: {agent.tensorboard_dir}")
print()

# ===========================
# TRAIN AGENT
# ===========================

print("=" * 80)
print("Step 3: Training PPO Agent")
print("=" * 80)
print()

print(f"[*] Starting training ({TOTAL_TIMESTEPS:,} timesteps)...")
print(f"     This will take approximately {TOTAL_TIMESTEPS/1000/60:.0f}-{TOTAL_TIMESTEPS/800/60:.0f} minutes")
print(f"     Watch progress: tensorboard --logdir {agent.tensorboard_dir}")
print()

start_time = datetime.now()

history = agent.train(
    df=df,
    exchange=EXCHANGE,
    symbol=SYMBOL,
    timeframe=TIMEFRAME,
    initial_capital=INITIAL_CAPITAL,
    total_timesteps=TOTAL_TIMESTEPS,
    learning_rate=LEARNING_RATE
)

end_time = datetime.now()
duration = (end_time - start_time).total_seconds()

print()
print(f"[OK] Training completed in {duration/60:.1f} minutes")
print()

# ===========================
# SAVE MODEL
# ===========================

print("=" * 80)
print("Step 4: Saving Model")
print("=" * 80)
print()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
model_name = f"ppo_{SYMBOL.replace('/', '_').lower()}_{TIMEFRAME}_{timestamp}"
model_path = agent.model_dir / f"{model_name}.zip"

agent.save(str(model_path))
print(f"[OK] Model saved: {model_path}")
print()

# ===========================
# EVALUATE AGENT
# ===========================

print("=" * 80)
print("Step 5: Evaluating Agent")
print("=" * 80)
print()

print("[*] Running evaluation on full dataset...")

eval_results = agent.predict(
    df=df,
    initial_capital=INITIAL_CAPITAL,
    deterministic=True
)

backtest_results = eval_results["metrics"]

print()
print("=" * 80)
print("BACKTEST RESULTS")
print("=" * 80)
print()

print(f"Total Return:    {backtest_results['total_return']:.2%}")
print(f"Sharpe Ratio:    {backtest_results['sharpe_ratio']:.4f}")
print(f"Sortino Ratio:   {backtest_results['sortino_ratio']:.4f}")
print(f"Max Drawdown:    {backtest_results['max_drawdown']:.2%}")
print(f"Win Rate:        {backtest_results['win_rate']:.2%}")
print(f"Profit Factor:   {backtest_results['profit_factor']:.2f}")
print(f"Total Trades:    {backtest_results['total_trades']}")
print()

# ===========================
# SUMMARY
# ===========================

print("=" * 80)
print("RL TRAINING COMPLETED!")
print("=" * 80)
print()

print(f"Model Path:       {model_path}")
print(f"Training Time:    {duration/60:.1f} minutes")
print(f"Total Timesteps:  {TOTAL_TIMESTEPS:,}")
print()

print("PERFORMANCE:")
print(f"  Sharpe Ratio:   {backtest_results['sharpe_ratio']:.4f}")
print(f"  Total Return:   {backtest_results['total_return']:.2%}")
print(f"  Max Drawdown:   {backtest_results['max_drawdown']:.2%}")
print()

# Сравнение с целями
print("=" * 80)
print("COMPARISON WITH GOALS")
print("=" * 80)
print()

sharpe_goal = 1.0
return_goal = 0.05

print(f"Sharpe Ratio:  {backtest_results['sharpe_ratio']:.4f} (goal: >{sharpe_goal})")
if backtest_results['sharpe_ratio'] > sharpe_goal:
    print("  ✅ GOAL ACHIEVED!")
else:
    print(f"  ⚠️ Need improvement ({sharpe_goal - backtest_results['sharpe_ratio']:.4f} points)")

print()

print(f"Total Return:  {backtest_results['total_return']:.2%} (goal: >{return_goal:.0%})")
if backtest_results['total_return'] > return_goal:
    print("  ✅ GOAL ACHIEVED!")
else:
    print(f"  ⚠️ Need improvement ({(return_goal - backtest_results['total_return']) * 100:.1f}%)")

print()

# ===========================
# NEXT STEPS
# ===========================

print("=" * 80)
print("NEXT STEPS")
print("=" * 80)
print()

if backtest_results['sharpe_ratio'] > sharpe_goal and backtest_results['total_return'] > return_goal:
    print("[SUCCESS] RL agent performs well!")
    print()
    print("Next steps:")
    print("1. Deploy to paper trading")
    print("2. Monitor performance (7 days)")
    print("3. (Optional) Fine-tune hyperparameters")
elif backtest_results['sharpe_ratio'] > 0.5:
    print("[PARTIAL SUCCESS] Some improvement, but more training needed")
    print()
    print("Next steps:")
    print("1. Increase training timesteps (1M instead of 500K)")
    print("2. Try different reward functions")
    print("3. Adjust hyperparameters (learning_rate, gamma)")
else:
    print("[NEEDS MORE WORK] RL agent needs significant improvement")
    print()
    print("Next steps:")
    print("1. Increase dataset size (load more historical data)")
    print("2. Try different environments (reward shaping)")
    print("3. Experiment with other algorithms (A2C, SAC)")

print()
print("=" * 80)
print()

print("To watch training progress:")
print(f"  tensorboard --logdir {agent.tensorboard_dir}")
print()
print("To use trained model in API:")
print(f"  POST /rl/predict")
print(f"  {{'model_path': '{model_path}', 'features': [...]}}")
print()
print("=" * 80)

