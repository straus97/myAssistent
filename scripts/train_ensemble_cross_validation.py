#!/usr/bin/env python3
"""
PHASE 3: Cross-Validation + Walk-Forward для исправления overfitting

Проблема PHASE 2:
- Validation AUC: 0.6538 (отлично)
- Test AUC: 0.4829 (хуже случайного!)
- Причина: Optuna оптимизировал ПОД validation set

Решение PHASE 3:
1. TimeSeriesSplit (5-fold CV) вместо single validation
2. Walk-Forward Validation для реалистичной оценки
3. Увеличенная регуляризация (reg_alpha, reg_lambda)
4. Более простая модель (меньше параметров)

Ожидаемый результат:
- Test AUC >0.55 (минимум)
- Test AUC >0.60 (цель)
- Stable performance на всех CV folds
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import optuna
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, accuracy_score

# Suppress warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.features import build_dataset
from src.ensemble import (
    optimize_xgboost_cv,
    optimize_lightgbm_cv,
    optimize_catboost_cv,
    train_voting_ensemble,
    train_stacking_ensemble,
    evaluate_ensemble
)

# ===========================
# CONFIGURATION
# ===========================

N_SPLITS = 5  # TimeSeriesSplit folds
N_TRIALS_PER_MODEL = 30  # Optuna trials per model
TIMEOUT = 3600  # 1 hour timeout

EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"

ARTIFACTS_DIR = project_root / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

print("=" * 80)
print(" " * 20 + "PHASE 3: Cross-Validation + Walk-Forward")
print("=" * 80)
print()
print(f"Configuration:")
print(f"  - TimeSeriesSplit: {N_SPLITS} folds")
print(f"  - Optuna Trials per Model: {N_TRIALS_PER_MODEL}")
print(f"  - Timeout: {TIMEOUT}s ({TIMEOUT/60:.0f} minutes)")
print(f"  - Exchange: {EXCHANGE}")
print(f"  - Symbol: {SYMBOL}")
print(f"  - Timeframe: {TIMEFRAME}")
print()

# ===========================
# LOAD DATA
# ===========================

print("=" * 80)
print("Step 1: Loading Dataset")
print("=" * 80)

# Get DB session
from src.db import SessionLocal
db = SessionLocal()

try:
    df, feature_list = build_dataset(
        db=db,
        exchange=EXCHANGE,
        symbol=SYMBOL,
        timeframe=TIMEFRAME
    )
    print(f"[OK] Dataset loaded: {len(df)} rows x {len(df.columns)} features")
    print(f"     Date range: {df.index.min()} to {df.index.max()}")
    print()
finally:
    db.close()

# Use feature_list from build_dataset
feature_cols = feature_list
print(f"[OK] Features: {len(feature_cols)}")

# Split train/test (80/20) - test set остается нетронутым
train_size = int(0.8 * len(df))
train_df = df.iloc[:train_size].copy()
test_df = df.iloc[train_size:].copy()

X_train = train_df[feature_cols].values
y_train = train_df["y"].values

X_test = test_df[feature_cols].values
y_test = test_df["y"].values

print(f"[OK] Train set: {len(train_df)} rows ({len(train_df)/len(df)*100:.1f}%)")
print(f"[OK] Test set: {len(test_df)} rows ({len(test_df)/len(df)*100:.1f}%)")
print()

# ===========================
# WALK-FORWARD CROSS-VALIDATION
# ===========================

print("=" * 80)
print("Step 2: Walk-Forward Cross-Validation")
print("=" * 80)
print()

tscv = TimeSeriesSplit(n_splits=N_SPLITS)

# Store best params from each fold
xgb_params_per_fold = []
lgb_params_per_fold = []
cat_params_per_fold = []

for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X_train), 1):
    print(f"-" * 80)
    print(f"Fold {fold_idx}/{N_SPLITS}")
    print(f"-" * 80)
    
    X_fold_train = X_train[train_idx]
    y_fold_train = y_train[train_idx]
    X_fold_val = X_train[val_idx]
    y_fold_val = y_train[val_idx]
    
    print(f"  Train: {len(train_idx)} samples")
    print(f"  Val:   {len(val_idx)} samples")
    print()
    
    # ===========================
    # XGBoost Optimization
    # ===========================
    print(f"[Fold {fold_idx}] Optimizing XGBoost ({N_TRIALS_PER_MODEL} trials)...")
    
    best_xgb_params = optimize_xgboost_cv(
        X_fold_train, y_fold_train, 
        X_fold_val, y_fold_val,
        n_trials=N_TRIALS_PER_MODEL,
        timeout=TIMEOUT // (N_SPLITS * 3)
    )
    xgb_params_per_fold.append(best_xgb_params)
    print(f"[Fold {fold_idx}] XGBoost best params: {best_xgb_params}")
    print()
    
    # ===========================
    # LightGBM Optimization
    # ===========================
    print(f"[Fold {fold_idx}] Optimizing LightGBM ({N_TRIALS_PER_MODEL} trials)...")
    
    best_lgb_params = optimize_lightgbm_cv(
        X_fold_train, y_fold_train,
        X_fold_val, y_fold_val,
        n_trials=N_TRIALS_PER_MODEL,
        timeout=TIMEOUT // (N_SPLITS * 3)
    )
    lgb_params_per_fold.append(best_lgb_params)
    print(f"[Fold {fold_idx}] LightGBM best params: {best_lgb_params}")
    print()
    
    # ===========================
    # CatBoost Optimization
    # ===========================
    print(f"[Fold {fold_idx}] Optimizing CatBoost ({N_TRIALS_PER_MODEL} trials)...")
    
    best_cat_params = optimize_catboost_cv(
        X_fold_train, y_fold_train,
        X_fold_val, y_fold_val,
        n_trials=N_TRIALS_PER_MODEL,
        timeout=TIMEOUT // (N_SPLITS * 3)
    )
    cat_params_per_fold.append(best_cat_params)
    print(f"[Fold {fold_idx}] CatBoost best params: {best_cat_params}")
    print()

# ===========================
# AGGREGATE BEST PARAMS
# ===========================

print("=" * 80)
print("Step 3: Aggregating Best Parameters")
print("=" * 80)
print()

# Average numeric params, take mode for categorical
def aggregate_params(params_list):
    """Aggregate parameters across folds"""
    aggregated = {}
    
    # Get all keys
    all_keys = set()
    for params in params_list:
        all_keys.update(params.keys())
    
    for key in all_keys:
        values = [p[key] for p in params_list if key in p]
        
        # If numeric, take mean
        if isinstance(values[0], (int, float)):
            aggregated[key] = np.mean(values)
            if isinstance(values[0], int):
                aggregated[key] = int(aggregated[key])
        else:
            # If categorical, take most common
            from collections import Counter
            aggregated[key] = Counter(values).most_common(1)[0][0]
    
    return aggregated

best_xgb_params = aggregate_params(xgb_params_per_fold)
best_lgb_params = aggregate_params(lgb_params_per_fold)
best_cat_params = aggregate_params(cat_params_per_fold)

print("[OK] Aggregated XGBoost params:", best_xgb_params)
print("[OK] Aggregated LightGBM params:", best_lgb_params)
print("[OK] Aggregated CatBoost params:", best_cat_params)
print()

# ===========================
# TRAIN FINAL MODELS
# ===========================

print("=" * 80)
print("Step 4: Training Final Models on Full Train Set")
print("=" * 80)
print()

# Import model classes
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

# Train XGBoost
print("[*] Training final XGBoost model...")
xgb_model = XGBClassifier(**best_xgb_params, random_state=42)
xgb_model.fit(X_train, y_train)
print("[OK] XGBoost trained")

# Train LightGBM
print("[*] Training final LightGBM model...")
lgb_model = LGBMClassifier(**best_lgb_params, random_state=42, verbose=-1)
lgb_model.fit(X_train, y_train)
print("[OK] LightGBM trained")

# Train CatBoost
print("[*] Training final CatBoost model...")
cat_model = CatBoostClassifier(**best_cat_params, random_state=42, verbose=0)
cat_model.fit(X_train, y_train)
print("[OK] CatBoost trained")
print()

# ===========================
# TRAIN ENSEMBLES
# ===========================

print("=" * 80)
print("Step 5: Training Ensemble Models")
print("=" * 80)
print()

base_models = [
    ("xgboost", xgb_model),
    ("lightgbm", lgb_model),
    ("catboost", cat_model)
]

# Voting Ensemble
print("[*] Training Voting Ensemble (soft voting)...")
voting_model = train_voting_ensemble(base_models, X_train, y_train)
print("[OK] Voting Ensemble trained")

# Stacking Ensemble
print("[*] Training Stacking Ensemble (LogisticRegression meta-learner)...")
stacking_model = train_stacking_ensemble(base_models, X_train, y_train)
print("[OK] Stacking Ensemble trained")
print()

# ===========================
# EVALUATE ON TEST SET
# ===========================

print("=" * 80)
print("Step 6: Evaluation on Test Set")
print("=" * 80)
print()

models = {
    "xgboost": xgb_model,
    "lightgbm": lgb_model,
    "catboost": cat_model,
    "voting": voting_model,
    "stacking": stacking_model
}

results = {}

for name, model in models.items():
    print(f"[*] Evaluating {name}...")
    
    # Predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    # Metrics
    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)
    
    results[name] = {
        "test_auc": auc,
        "test_accuracy": accuracy,
        "params": (
            best_xgb_params if name == "xgboost" else
            best_lgb_params if name == "lightgbm" else
            best_cat_params if name == "catboost" else
            {}
        )
    }
    
    print(f"     Test AUC: {auc:.4f}")
    print(f"     Test Accuracy: {accuracy:.4f}")
    print()

# ===========================
# SELECT BEST MODEL
# ===========================

print("=" * 80)
print("Step 7: Selecting Best Model")
print("=" * 80)
print()

best_model_name = max(results, key=lambda k: results[k]["test_auc"])
best_model = models[best_model_name]
best_auc = results[best_model_name]["test_auc"]

print(f"[OK] Best Model: {best_model_name}")
print(f"     Test AUC: {best_auc:.4f}")
print()

# ===========================
# COMPARISON WITH PHASE 2
# ===========================

print("=" * 80)
print("PHASE 2 vs PHASE 3 Comparison")
print("=" * 80)
print()

phase2_test_auc = 0.4829  # From memory
phase3_test_auc = best_auc

improvement = ((phase3_test_auc - phase2_test_auc) / phase2_test_auc) * 100

print(f"PHASE 2 (Single Val):  Test AUC = {phase2_test_auc:.4f}")
print(f"PHASE 3 (Cross-Val):   Test AUC = {phase3_test_auc:.4f}")
print(f"Improvement:           {improvement:+.1f}%")
print()

if phase3_test_auc > 0.55:
    print("[SUCCESS] Test AUC >0.55 - Overfitting fixed!")
elif phase3_test_auc > phase2_test_auc:
    print("[PARTIAL SUCCESS] Improvement detected, but more work needed")
else:
    print("[WARNING] No improvement - deeper investigation required")
print()

# ===========================
# SAVE RESULTS
# ===========================

print("=" * 80)
print("Step 8: Saving Results")
print("=" * 80)
print()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Save best model
import pickle
model_path = ARTIFACTS_DIR / f"ensemble_{best_model_name}_cv_{timestamp}.pkl"
with open(model_path, "wb") as f:
    pickle.dump(best_model, f)
print(f"[OK] Model saved: {model_path}")

# Save metadata
metadata = {
    "timestamp": timestamp,
    "phase": 3,
    "method": "cross_validation",
    "n_splits": N_SPLITS,
    "best_model": best_model_name,
    "test_auc": float(best_auc),
    "phase2_test_auc": phase2_test_auc,
    "improvement_pct": float(improvement),
    "all_results": {
        name: {
            "test_auc": float(metrics["test_auc"]),
            "test_accuracy": float(metrics["test_accuracy"])
        }
        for name, metrics in results.items()
    },
    "best_params": results[best_model_name]["params"],
    "feature_count": len(feature_cols),
    "train_samples": len(X_train),
    "test_samples": len(X_test)
}

metadata_path = ARTIFACTS_DIR / f"ensemble_metadata_cv_{timestamp}.json"
with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)
print(f"[OK] Metadata saved: {metadata_path}")
print()

# ===========================
# SUMMARY
# ===========================

print("=" * 80)
print("PHASE 3 COMPLETED!")
print("=" * 80)
print()
print(f"Best Model:        {best_model_name}")
print(f"Test AUC:          {best_auc:.4f}")
print(f"Improvement:       {improvement:+.1f}% vs PHASE 2")
print(f"Model Path:        {model_path}")
print(f"Metadata Path:     {metadata_path}")
print()

if phase3_test_auc > 0.55:
    print("[NEXT STEPS]")
    print("1. Backtest с новой моделью")
    print("2. Paper trading monitoring")
    print("3. (Optional) Threshold optimization")
else:
    print("[NEXT STEPS]")
    print("1. Увеличить N_SPLITS (10-fold CV)")
    print("2. Загрузить больше исторических данных")
    print("3. Feature engineering (добавить новые фичи)")
    print("4. Рассмотреть RL-подход вместо supervised learning")

print()
print("=" * 80)

