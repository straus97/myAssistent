"""
Быстрый тест новых фичей (без Optuna, базовые параметры).
Сравнивает старую и новую модель.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

from dotenv import load_dotenv
load_dotenv()

from src.db import SessionLocal
from src.features import build_dataset
from src.modeling import time_split

ARTIFACTS_DIR = Path("artifacts")

def main():
    print("=" * 80)
    print("QUICK TEST: NEW FEATURES")
    print("=" * 80)
    
    # Загружаем датасет
    print("[1/3] Loading dataset with NEW features...")
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
    
    # Старые фичи (для сравнения)
    old_features = [
        "ret_1", "ret_3", "ret_6", "ret_12", "ret_24", "vol_norm",
        "rsi_14", "bb_pct_20_2", "bb_width_20_2",
        "macd", "macd_signal", "macd_hist",
        "atr_14", "atr_pct", "adx_14",
        "stoch_k", "stoch_d", "williams_r", "cci_20",
        "ema_9", "ema_21", "ema_50", "ema_cross_9_21", "ema_cross_21_50",
        "news_cnt_6", "news_cnt_24", "sent_mean_6", "sent_mean_24",
    ]
    
    # Новые фичи (лаги + time + дополнительные технические)
    new_features = [col for col in feature_cols if col not in old_features]
    
    print(f"Old features: {len(old_features)}")
    print(f"New features: {len(new_features)}")
    print(f"New features: {', '.join(new_features[:20])}...")
    print()
    
    # Split
    train_df, test_df = time_split(df, test_ratio=0.2)
    
    print("[2/3] Training models...")
    
    # Модель на СТАРЫХ фичах
    print("\n--- Model with OLD features ---")
    X_train_old = train_df[old_features]
    y_train = train_df["y"].values
    X_test_old = test_df[old_features]
    y_test = test_df["y"].values
    
    model_old = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model_old.fit(X_train_old, y_train)
    
    proba_old = model_old.predict_proba(X_test_old)[:, 1]
    pred_old = (proba_old > 0.5).astype(int)
    
    acc_old = accuracy_score(y_test, pred_old)
    auc_old = roc_auc_score(y_test, proba_old)
    
    print(f"Accuracy: {acc_old:.4f}")
    print(f"ROC AUC:  {auc_old:.4f}")
    
    # Модель на НОВЫХ фичах (все фичи)
    print("\n--- Model with ALL features (OLD + NEW) ---")
    X_train_new = train_df[feature_cols]
    X_test_new = test_df[feature_cols]
    
    model_new = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model_new.fit(X_train_new, y_train)
    
    proba_new = model_new.predict_proba(X_test_new)[:, 1]
    pred_new = (proba_new > 0.5).astype(int)
    
    acc_new = accuracy_score(y_test, pred_new)
    auc_new = roc_auc_score(y_test, proba_new)
    
    print(f"Accuracy: {acc_new:.4f}")
    print(f"ROC AUC:  {auc_new:.4f}")
    
    # Сравнение
    print("\n[3/3] Comparison:")
    print("-" * 80)
    print(f"{'Metric':<20} {'Old':<15} {'New':<15} {'Improvement':<15}")
    print("-" * 80)
    print(f"{'Accuracy':<20} {acc_old:<15.4f} {acc_new:<15.4f} {(acc_new-acc_old)*100:+.2f}%")
    print(f"{'ROC AUC':<20} {auc_old:<15.4f} {auc_new:<15.4f} {(auc_new-auc_old)*100:+.2f}%")
    print("-" * 80)
    
    if auc_new > auc_old:
        print(f"\n✅ NEW features IMPROVED the model by {(auc_new-auc_old)*100:.2f}% AUC!")
    else:
        print(f"\n⚠️ NEW features did not improve the model.")
    
    # Сохраняем результаты
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "rows": len(df),
            "features_old": len(old_features),
            "features_new": len(feature_cols),
            "train_samples": len(train_df),
            "test_samples": len(test_df),
        },
        "old_model": {
            "accuracy": float(acc_old),
            "roc_auc": float(auc_old),
        },
        "new_model": {
            "accuracy": float(acc_new),
            "roc_auc": float(auc_new),
        },
        "improvement": {
            "accuracy_delta": float(acc_new - acc_old),
            "auc_delta": float(auc_new - auc_old),
        },
    }
    
    results_path = ARTIFACTS_DIR / "feature_comparison.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

