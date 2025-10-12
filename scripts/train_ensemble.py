"""
Ensemble Model: XGBoost + LightGBM + CatBoost

Stacking approach:
1. Train 3 base models (XGBoost, LightGBM, CatBoost)
2. Use their predictions as features for meta-model (Logistic Regression)
3. Expected improvement: ROC AUC +2-5%
"""
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.features import build_dataset
from src.db import SessionLocal
from src.modeling import time_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostClassifier


def train_ensemble(df: pd.DataFrame, feature_cols: list):
    """
    Обучение Ensemble модели через Stacking
    """
    print("\n" + "="*70)
    print("[ENSEMBLE] STACKING: XGBoost + LightGBM + CatBoost")
    print("="*70 + "\n")
    
    # Разделение данных
    train_df, test_df = time_split(df, test_ratio=0.2)
    
    X_train = train_df[feature_cols].values
    y_train = train_df["y"].values
    X_test = test_df[feature_cols].values
    y_test = test_df["y"].values
    
    print(f"[DATA]:")
    print(f"   - Train: {len(X_train)} rows")
    print(f"   - Test: {len(X_test)} rows")
    print(f"   - Features: {len(feature_cols)}\n")
    
    # ============================================================
    # LEVEL 0: Train base models
    # ============================================================
    
    print("[LEVEL 0] Обучение базовых моделей...\n")
    
    # 1. XGBoost
    print("  [1/3] XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1,
        tree_method='hist',
    )
    xgb_model.fit(X_train, y_train, verbose=False)
    xgb_pred_train = xgb_model.predict_proba(X_train)[:, 1]
    xgb_pred_test = xgb_model.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_pred_test)
    print(f"        ROC AUC: {xgb_auc:.4f}")
    
    # 2. LightGBM
    print("  [2/3] LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    lgb_model.fit(X_train, y_train)
    lgb_pred_train = lgb_model.predict_proba(X_train)[:, 1]
    lgb_pred_test = lgb_model.predict_proba(X_test)[:, 1]
    lgb_auc = roc_auc_score(y_test, lgb_pred_test)
    print(f"        ROC AUC: {lgb_auc:.4f}")
    
    # 3. CatBoost
    print("  [3/3] CatBoost...")
    cat_model = CatBoostClassifier(
        iterations=200,
        depth=6,
        learning_rate=0.1,
        random_state=42,
        verbose=False,
    )
    cat_model.fit(X_train, y_train)
    cat_pred_train = cat_model.predict_proba(X_train)[:, 1]
    cat_pred_test = cat_model.predict_proba(X_test)[:, 1]
    cat_auc = roc_auc_score(y_test, cat_pred_test)
    print(f"        ROC AUC: {cat_auc:.4f}\n")
    
    # ============================================================
    # LEVEL 1: Train meta-model (Logistic Regression)
    # ============================================================
    
    print("[LEVEL 1] Обучение мета-модели (Logistic Regression)...\n")
    
    # Создаём новые фичи из предсказаний базовых моделей
    X_meta_train = np.column_stack([xgb_pred_train, lgb_pred_train, cat_pred_train])
    X_meta_test = np.column_stack([xgb_pred_test, lgb_pred_test, cat_pred_test])
    
    # Обучаем мета-модель
    meta_model = LogisticRegression(random_state=42, max_iter=1000)
    meta_model.fit(X_meta_train, y_train)
    
    # ============================================================
    # Evaluation
    # ============================================================
    
    print("[EVALUATION] Оценка производительности...\n")
    
    # Предсказания мета-модели
    ensemble_pred_proba = meta_model.predict_proba(X_meta_test)[:, 1]
    ensemble_pred = meta_model.predict(X_meta_test)
    
    # Метрики
    ensemble_auc = roc_auc_score(y_test, ensemble_pred_proba)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    
    print("="*70)
    print("[RESULTS] СРАВНЕНИЕ МОДЕЛЕЙ")
    print("="*70 + "\n")
    
    print(f"{'Model':<20} {'ROC AUC':<12} {'Accuracy':<12}")
    print("-" * 70)
    print(f"{'XGBoost':<20} {xgb_auc:<12.4f} {accuracy_score(y_test, (xgb_pred_test >= 0.5).astype(int)):<12.4f}")
    print(f"{'LightGBM':<20} {lgb_auc:<12.4f} {accuracy_score(y_test, (lgb_pred_test >= 0.5).astype(int)):<12.4f}")
    print(f"{'CatBoost':<20} {cat_auc:<12.4f} {accuracy_score(y_test, (cat_pred_test >= 0.5).astype(int)):<12.4f}")
    print(f"{'ENSEMBLE (Stacking)':<20} {ensemble_auc:<12.4f} {ensemble_acc:<12.4f}")
    print("-" * 70)
    
    # Находим лучшую модель
    best_single = max(xgb_auc, lgb_auc, cat_auc)
    improvement = ((ensemble_auc - best_single) / best_single) * 100
    
    print(f"\n[IMPROVEMENT]:")
    print(f"   - Best single model: {best_single:.4f}")
    print(f"   - Ensemble: {ensemble_auc:.4f}")
    print(f"   - Improvement: {improvement:+.2f}%")
    
    if improvement > 0:
        print(f"   - Verdict: [SUCCESS] Ensemble лучше!\n")
    else:
        print(f"   - Verdict: [INFO] Single model лучше\n")
    
    # ============================================================
    # Сохранение
    # ============================================================
    
    output_dir = Path("artifacts/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем все модели
    ensemble_dict = {
        "xgboost": xgb_model,
        "lightgbm": lgb_model,
        "catboost": cat_model,
        "meta_model": meta_model,
        "feature_cols": feature_cols,
        "metrics": {
            "xgb_auc": float(xgb_auc),
            "lgb_auc": float(lgb_auc),
            "cat_auc": float(cat_auc),
            "ensemble_auc": float(ensemble_auc),
            "ensemble_accuracy": float(ensemble_acc),
        }
    }
    
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    ensemble_path = output_dir / f"ensemble_{timestamp}.pkl"
    joblib.dump(ensemble_dict, ensemble_path)
    
    print(f"[SAVED] Ensemble модель: {ensemble_path}\n")
    
    return ensemble_dict, ensemble_auc


def main():
    print("\n" + "="*70)
    print("[ENSEMBLE TRAINING] STACKING МОДЕЛЬ")
    print("="*70 + "\n")
    
    EXCHANGE = "bybit"
    SYMBOL = "BTC/USDT"
    TIMEFRAME = "1h"
    HORIZON_STEPS = 6
    
    print(f"[PARAMS]:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Strategy: XGBoost + LightGBM + CatBoost -> LogisticRegression\n")
    
    # Загрузка данных
    print("[LOADING] Загрузка данных...")
    db = SessionLocal()
    
    try:
        df, all_features = build_dataset(db, EXCHANGE, SYMBOL, TIMEFRAME, HORIZON_STEPS)
        print(f"[OK] Датасет: {len(df)} строк x {len(all_features)} фичей\n")
        
        # Feature selection (удаляем статичные)
        print("[FEATURE SELECTION] Удаление статичных фичей...")
        dynamic_features = []
        
        for feat in all_features:
            if feat in df.columns and df[feat].nunique() > 1:
                dynamic_features.append(feat)
        
        print(f"[OK] Динамичных фичей: {len(dynamic_features)} (было {len(all_features)})\n")
        
        # Обучение Ensemble
        ensemble_dict, ensemble_auc = train_ensemble(df, dynamic_features)
        
        # Сравнение с текущей best моделью
        baseline_path = Path("artifacts/metrics.json")
        if baseline_path.exists():
            with open(baseline_path) as f:
                baseline = json.load(f)
            
            baseline_auc = baseline.get("roc_auc", 0)
            improvement = ((ensemble_auc - baseline_auc) / baseline_auc) * 100
            
            print("="*70)
            print("[COMPARISON] vs Current Best Model")
            print("="*70 + "\n")
            print(f"   - Current Best ROC AUC: {baseline_auc:.4f}")
            print(f"   - Ensemble ROC AUC: {ensemble_auc:.4f}")
            print(f"   - Improvement: {improvement:+.2f}%\n")
            
            if improvement > 2:
                print("[EXCELLENT] Ensemble значительно лучше! Используйте его для production.")
            elif improvement > 0:
                print("[SUCCESS] Ensemble немного лучше.")
            else:
                print("[INFO] Текущая модель всё ещё лучше.")
        
        print("\n" + "="*70)
        print("[SUCCESS] ENSEMBLE ОБУЧЕН И ГОТОВ К ИСПОЛЬЗОВАНИЮ!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

