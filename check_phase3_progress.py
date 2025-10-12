#!/usr/bin/env python3
"""
Проверка прогресса обучения PHASE 3
"""

import json
from pathlib import Path
from datetime import datetime

artifacts_dir = Path("artifacts")

# Поиск файлов CV
cv_models = list(artifacts_dir.glob("ensemble_*_cv_*.pkl"))
cv_metadata = list(artifacts_dir.glob("ensemble_metadata_cv_*.json"))

print("=" * 80)
print(" " * 25 + "PHASE 3 Progress Check")
print("=" * 80)
print()

if not cv_models:
    print("[*] Obuchenie esche ne zaversheno...")
    print()
    print("Faily ozhidayutsya:")
    print("  - artifacts/ensemble_<model>_cv_<timestamp>.pkl")
    print("  - artifacts/ensemble_metadata_cv_<timestamp>.json")
    print()
    print("Prover' cherez 5-10 minut")
else:
    print(f"[OK] Obuchenie zaversheno! Naydeno {len(cv_models)} modeley:")
    print()
    
    for model_file in cv_models:
        print(f"  [+] {model_file.name}")
    print()
    
    # Читаем метаданные
    if cv_metadata:
        latest_metadata = sorted(cv_metadata)[-1]
        print(f"Метаданные: {latest_metadata.name}")
        print()
        
        with open(latest_metadata, "r") as f:
            data = json.load(f)
        
        print("=" * 80)
        print("РЕЗУЛЬТАТЫ PHASE 3")
        print("=" * 80)
        print()
        
        print(f"Лучшая модель: {data['best_model']}")
        print(f"Test AUC:      {data['test_auc']:.4f}")
        print(f"PHASE 2 AUC:   {data['phase2_test_auc']:.4f}")
        print(f"Улучшение:     {data['improvement_pct']:+.1f}%")
        print()
        
        if data['test_auc'] > 0.65:
            print("[SUCCESS] IDEAL'NYY USPEKH! Test AUC >0.65")
        elif data['test_auc'] > 0.60:
            print("[SUCCESS] TSELEVOY USPEKH! Test AUC >0.60")
        elif data['test_auc'] > 0.55:
            print("[SUCCESS] MINIMAL'NYY USPEKH! Test AUC >0.55")
        elif data['test_auc'] > data['phase2_test_auc']:
            print("[WARNING] CHASTICHNYY USPEKH - est' uluchshenie, no tsel' ne dostignut")
        else:
            print("[FAIL] PROVAL - net uluchsheniya")
        print()
        
        print("=" * 80)
        print("ВСЕ МОДЕЛИ")
        print("=" * 80)
        print()
        
        for model_name, metrics in data['all_results'].items():
            print(f"{model_name:12} | AUC: {metrics['test_auc']:.4f} | Accuracy: {metrics['test_accuracy']:.4f}")
        
        print()
        print("=" * 80)
        print("СЛЕДУЮЩИЕ ШАГИ")
        print("=" * 80)
        print()
        
        if data['test_auc'] > 0.55:
            print("1. Запустить backtest с новой моделью")
            print("2. Paper Trading мониторинг (7 дней)")
            print("3. (Опционально) Threshold optimization")
        elif data['test_auc'] > 0.50:
            print("1. Увеличить N_SPLITS (10-fold CV)")
            print("2. Загрузить больше исторических данных")
            print("3. Feature engineering")
        else:
            print("1. Увеличить датасет (>10,000 samples)")
            print("2. Попробовать другие horizon_steps (12h, 24h)")
            print("3. Рассмотреть RL-подход")
        
        print()

print("=" * 80)

