"""
Обучение Ensemble модели с Optuna hyperparameter tuning.

Процесс:
1. Загружаем датасет (с новыми 38 фичами)
2. Optuna optimization для каждой модели (XGBoost, LightGBM, CatBoost)
3. Обучаем Voting и Stacking ensemble
4. Сравниваем все модели
5. Выбираем лучшую и сохраняем
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
import optuna
from optuna.samplers import TPESampler

# Загружаем .env
from dotenv import load_dotenv
load_dotenv()

from src.db import SessionLocal
from src.features import build_dataset
from src.modeling import time_split
from src.ensemble import (
    train_single_model,
    train_voting_ensemble,
    train_stacking_ensemble,
    save_ensemble,
)

ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Параметры
EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
N_TRIALS = 30  # Количество попыток для Optuna (по 10 на модель для быстрого теста)
TIMEOUT = 1800  # 30 минут максимум на оптимизацию


def optimize_xgboost(X_train, y_train, X_val, y_val, n_trials=50):
    """Optuna optimization для XGBoost."""
    print(f"\n[Optuna] Optimizing XGBoost ({n_trials} trials)...")
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 0.0, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 1.0),
            "random_state": 42,
            "n_jobs": -1,
            "eval_metric": "logloss",
        }
        
        model, metrics = train_single_model(X_train, y_train, X_val, y_val, "xgboost", params)
        return metrics["roc_auc"] if metrics["roc_auc"] else 0.5
    
    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, timeout=TIMEOUT, show_progress_bar=True)
    
    print(f"[Optuna] XGBoost best AUC: {study.best_value:.4f}")
    print(f"[Optuna] XGBoost best params: {study.best_params}")
    
    return study.best_params


def optimize_lightgbm(X_train, y_train, X_val, y_val, n_trials=50):
    """Optuna optimization для LightGBM."""
    print(f"\n[Optuna] Optimizing LightGBM ({n_trials} trials)...")
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "num_leaves": trial.suggest_int("num_leaves", 20, 200),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 1.0),
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": -1,
        }
        
        model, metrics = train_single_model(X_train, y_train, X_val, y_val, "lightgbm", params)
        return metrics["roc_auc"] if metrics["roc_auc"] else 0.5
    
    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, timeout=TIMEOUT, show_progress_bar=True)
    
    print(f"[Optuna] LightGBM best AUC: {study.best_value:.4f}")
    print(f"[Optuna] LightGBM best params: {study.best_params}")
    
    return study.best_params


def optimize_catboost(X_train, y_train, X_val, y_val, n_trials=50):
    """Optuna optimization для CatBoost."""
    print(f"\n[Optuna] Optimizing CatBoost ({n_trials} trials)...")
    
    def objective(trial):
        params = {
            "iterations": trial.suggest_int("iterations", 100, 500),
            "depth": trial.suggest_int("depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 0.0, 10.0),
            "random_state": 42,
            "verbose": False,
            "thread_count": -1,
        }
        
        model, metrics = train_single_model(X_train, y_train, X_val, y_val, "catboost", params)
        return metrics["roc_auc"] if metrics["roc_auc"] else 0.5
    
    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, timeout=TIMEOUT, show_progress_bar=True)
    
    print(f"[Optuna] CatBoost best AUC: {study.best_value:.4f}")
    print(f"[Optuna] CatBoost best params: {study.best_params}")
    
    return study.best_params


def main():
    print("=" * 80)
    print("ENSEMBLE MODEL TRAINING WITH HYPERPARAMETER OPTIMIZATION")
    print("=" * 80)
    print(f"Exchange: {EXCHANGE}")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Optuna trials per model: {N_TRIALS // 3}")
    print()
    
    # 1. Загружаем датасет
    print("[1/6] Loading dataset...")
    db = SessionLocal()
    try:
        df, feature_cols = build_dataset(
            db=db,
            exchange=EXCHANGE,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            horizon_steps=4,
        )
    finally:
        db.close()
    
    print(f"Dataset: {len(df)} rows x {len(feature_cols)} features")
    print(f"Date range: {df.index.min()} → {df.index.max()}")
    print()
    
    # 2. Split на train/validation/test (60/20/20)
    print("[2/6] Splitting data (60% train, 20% val, 20% test)...")
    n = len(df)
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    
    df_train = df.iloc[:train_end]
    df_val = df.iloc[train_end:val_end]
    df_test = df.iloc[val_end:]
    
    X_train = df_train[feature_cols]
    y_train = df_train["y"].values
    X_val = df_val[feature_cols]
    y_val = df_val["y"].values
    X_test = df_test[feature_cols]
    y_test = df_test["y"].values
    
    print(f"Train: {len(X_train)} samples")
    print(f"Validation: {len(X_val)} samples")
    print(f"Test: {len(X_test)} samples")
    print()
    
    # 3. Hyperparameter optimization
    print("[3/6] Hyperparameter optimization with Optuna...")
    trials_per_model = max(10, N_TRIALS // 3)
    
    best_params_xgb = optimize_xgboost(X_train, y_train, X_val, y_val, n_trials=trials_per_model)
    best_params_lgbm = optimize_lightgbm(X_train, y_train, X_val, y_val, n_trials=trials_per_model)
    best_params_cat = optimize_catboost(X_train, y_train, X_val, y_val, n_trials=trials_per_model)
    print()
    
    # 4. Обучение финальных моделей на train+val
    print("[4/6] Training final models on train+val...")
    X_trainval = pd.concat([X_train, X_val])
    y_trainval = np.concatenate([y_train, y_val])
    
    # Одиночные модели
    xgb_model, xgb_metrics = train_single_model(
        X_trainval, y_trainval, X_test, y_test, "xgboost", best_params_xgb
    )
    lgbm_model, lgbm_metrics = train_single_model(
        X_trainval, y_trainval, X_test, y_test, "lightgbm", best_params_lgbm
    )
    cat_model, cat_metrics = train_single_model(
        X_trainval, y_trainval, X_test, y_test, "catboost", best_params_cat
    )
    print()
    
    # 5. Ensemble модели
    print("[5/6] Training ensemble models...")
    voting_models, voting_metrics = train_voting_ensemble(
        X_trainval, y_trainval, X_test, y_test,
        params_xgb=best_params_xgb,
        params_lgbm=best_params_lgbm,
        params_cat=best_params_cat,
    )
    
    stacking_models, stacking_metrics = train_stacking_ensemble(
        X_trainval, y_trainval, X_test, y_test,
        params_xgb=best_params_xgb,
        params_lgbm=best_params_lgbm,
        params_cat=best_params_cat,
    )
    print()
    
    # 6. Сравнение и выбор лучшей модели
    print("[6/6] Model comparison...")
    print("-" * 80)
    print(f"{'Model':<20} {'Accuracy':<12} {'ROC AUC':<12}")
    print("-" * 80)
    print(f"{'XGBoost':<20} {xgb_metrics['accuracy']:<12.4f} {xgb_metrics['roc_auc']:<12.4f}")
    print(f"{'LightGBM':<20} {lgbm_metrics['accuracy']:<12.4f} {lgbm_metrics['roc_auc']:<12.4f}")
    print(f"{'CatBoost':<20} {cat_metrics['accuracy']:<12.4f} {cat_metrics['roc_auc']:<12.4f}")
    print(f"{'Voting Ensemble':<20} {voting_metrics['accuracy']:<12.4f} {voting_metrics['roc_auc']:<12.4f}")
    print(f"{'Stacking Ensemble':<20} {stacking_metrics['accuracy']:<12.4f} {stacking_metrics['roc_auc']:<12.4f}")
    print("-" * 80)
    print()
    
    # Выбираем лучшую по AUC
    all_results = [
        ("xgboost", xgb_metrics, {"xgboost": xgb_model}),
        ("lightgbm", lgbm_metrics, {"lightgbm": lgbm_model}),
        ("catboost", cat_metrics, {"catboost": cat_model}),
        ("voting", voting_metrics, voting_models),
        ("stacking", stacking_metrics, stacking_models),
    ]
    
    best_name, best_metrics, best_models = max(
        all_results, key=lambda x: x[1]["roc_auc"] if x[1]["roc_auc"] else 0.0
    )
    
    print(f"🏆 BEST MODEL: {best_name.upper()}")
    print(f"   Accuracy: {best_metrics['accuracy']:.4f}")
    print(f"   ROC AUC: {best_metrics['roc_auc']:.4f}")
    print()
    
    # Сохраняем лучшую модель
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = ARTIFACTS_DIR / f"ensemble_{best_name}_{timestamp}.pkl"
    save_ensemble(best_models, model_path)
    
    # Сохраняем метаданные
    metadata = {
        "timestamp": timestamp,
        "exchange": EXCHANGE,
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "n_features": len(feature_cols),
        "feature_cols": feature_cols,
        "train_samples": len(X_trainval),
        "test_samples": len(X_test),
        "best_model": best_name,
        "metrics": {
            "xgboost": xgb_metrics,
            "lightgbm": lgbm_metrics,
            "catboost": cat_metrics,
            "voting": voting_metrics,
            "stacking": stacking_metrics,
        },
        "best_params": {
            "xgboost": best_params_xgb,
            "lightgbm": best_params_lgbm,
            "catboost": best_params_cat,
        },
    }
    
    metadata_path = ARTIFACTS_DIR / f"ensemble_metadata_{timestamp}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Model saved: {model_path}")
    print(f"✅ Metadata saved: {metadata_path}")
    print()
    print("=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()

