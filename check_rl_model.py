#!/usr/bin/env python3
"""
Проверка результатов RL обучения
"""

import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.db import SessionLocal
from src.features import build_dataset
from src.rl_agent import RLAgent

print("=" * 80)
print(" " * 25 + "ПРОВЕРКА RL МОДЕЛИ")
print("=" * 80)
print()

# Поиск последней модели
rl_models_dir = project_root / "artifacts" / "rl_models"
models = list(rl_models_dir.glob("ppo_*.zip"))

if not models:
    print("[!] RL модели не найдены в artifacts/rl_models/")
    print()
    print("Запусти обучение:")
    print("  python scripts\\train_rl_ppo.py --timesteps 100000")
    sys.exit(1)

# Сортировка по дате модификации
latest_model = max(models, key=lambda p: p.stat().st_mtime)

print(f"[OK] Найдена последняя RL модель:")
print(f"     {latest_model.name}")
print(f"     Размер: {latest_model.stat().st_size / 1024:.1f} KB")
print(f"     Дата: {latest_model.stat().st_mtime}")
print()

# Загрузка модели
print("=" * 80)
print("Загрузка модели и оценка...")
print("=" * 80)
print()

agent = RLAgent()

try:
    agent.load(str(latest_model))
    print(f"[OK] Модель загружена: {latest_model.name}")
    print()
    
    # Загрузка датасета
    print("[*] Загрузка датасета для оценки...")
    db = SessionLocal()
    
    try:
        df, feature_list = build_dataset(
            db=db,
            exchange="bybit",
            symbol="BTC/USDT",
            timeframe="1h"
        )
        print(f"[OK] Датасет загружен: {len(df)} rows x {len(feature_list)} features")
        print()
    finally:
        db.close()
    
    # Предсказание
    print("[*] Запуск предсказания...")
    results = agent.predict(
        df=df,
        initial_capital=1000.0,
        deterministic=True
    )
    
    metrics = results["metrics"]
    
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ RL МОДЕЛИ")
    print("=" * 80)
    print()
    
    print(f"Total Return:    {metrics['total_return']:.2%}")
    print(f"Sharpe Ratio:    {metrics['sharpe_ratio']:.4f}")
    print(f"Sortino Ratio:   {metrics['sortino_ratio']:.4f}")
    print(f"Max Drawdown:    {metrics['max_drawdown']:.2%}")
    print(f"Win Rate:        {metrics['win_rate']:.2%}")
    print(f"Profit Factor:   {metrics['profit_factor']:.2f}")
    print(f"Total Trades:    {metrics['total_trades']}")
    print()
    
    # Сравнение с целями
    print("=" * 80)
    print("СРАВНЕНИЕ С ЦЕЛЯМИ")
    print("=" * 80)
    print()
    
    sharpe_goal = 1.0
    return_goal = 0.05
    
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f} (цель: >{sharpe_goal})")
    if metrics['sharpe_ratio'] > sharpe_goal:
        print("  ✅ ЦЕЛЬ ДОСТИГНУТА!")
    else:
        print(f"  ⚠️ Недостаточно (не хватает {sharpe_goal - metrics['sharpe_ratio']:.4f})")
    
    print()
    
    print(f"Total Return: {metrics['total_return']:.2%} (цель: >{return_goal:.0%})")
    if metrics['total_return'] > return_goal:
        print("  ✅ ЦЕЛЬ ДОСТИГНУТА!")
    else:
        print(f"  ⚠️ Недостаточно (не хватает {(return_goal - metrics['total_return']) * 100:.1f}%)")
    
    print()
    
    # Итоговая оценка
    print("=" * 80)
    print("ИТОГОВАЯ ОЦЕНКА")
    print("=" * 80)
    print()
    
    if metrics['sharpe_ratio'] > 1.5 and metrics['total_return'] > 0.10:
        print("[🏆] ОТЛИЧНЫЙ РЕЗУЛЬТАТ!")
        print("     RL agent превосходит ожидания")
        print()
        print("СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Deploy в paper trading")
        print("  2. Monitor 7 дней")
        print("  3. Запуск на production!")
    
    elif metrics['sharpe_ratio'] > 1.0 and metrics['total_return'] > 0.05:
        print("[✅] ХОРОШИЙ РЕЗУЛЬТАТ!")
        print("     RL agent достиг целей")
        print()
        print("СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Deploy в paper trading")
        print("  2. Monitor 7 дней")
        print("  3. Fine-tune если нужно")
    
    elif metrics['sharpe_ratio'] > 0.5:
        print("[⚠️] ЧАСТИЧНЫЙ УСПЕХ")
        print("     RL agent работает, но ниже цели")
        print()
        print("СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Увеличить timesteps (100K → 500K)")
        print("  2. Попробовать разные гиперпараметры")
        print("  3. Или использовать PHASE 3 (LightGBM, AUC 0.5129)")
    
    else:
        print("[❌] НЕДОСТАТОЧНЫЙ РЕЗУЛЬТАТ")
        print("     RL agent не достиг целей")
        print()
        print("СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Использовать PHASE 3 (LightGBM, AUC 0.5129)")
        print("  2. Или загрузить больше данных (6-12 месяцев)")
        print("  3. Попробовать другой алгоритм (A2C, SAC)")
    
    print()
    print("=" * 80)
    
except Exception as e:
    print(f"[!] Ошибка при загрузке модели: {e}")
    print()
    print("Модель может быть повреждена или обучение не завершилось.")

