"""
Hyperparameter Tuning для XGBoost через Optuna

Цель: Улучшить ROC AUC с 0.538 до 0.60-0.65 (+5-10%)
"""
import json
import optuna
from optuna.samplers import TPESampler
from sklearn.model_selection import cross_val_score
import xgboost as xgb
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.features import build_dataset
from src.db import SessionLocal
from src.modeling import time_split


def objective(trial, X, y):
    """
    Optuna objective function для оптимизации XGBoost
    
    Оптимизируемые параметры:
    - learning_rate (eta): скорость обучения
    - max_depth: максимальная глубина дерева
    - n_estimators: количество деревьев
    - subsample: доля строк для каждого дерева
    - colsample_bytree: доля фичей для каждого дерева
    - min_child_weight: минимальная сумма весов в листе
    - gamma: минимальное уменьшение loss для разделения
    """
    params = {
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'n_estimators': trial.suggest_int('n_estimators', 50, 500, step=50),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'gamma': trial.suggest_float('gamma', 0.0, 0.5),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),  # L1 regularization
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 1.0),  # L2 regularization
        'random_state': 42,
        'n_jobs': -1,
        'tree_method': 'hist',  # Faster training
    }
    
    # XGBoost Classifier
    model = xgb.XGBClassifier(**params)
    
    # 5-fold Cross-validation на train set
    # Используем ROC AUC как метрику (важнее accuracy для несбалансированных классов)
    scores = cross_val_score(
        model, X, y, 
        cv=5, 
        scoring='roc_auc',
        n_jobs=-1
    )
    
    # Возвращаем среднее значение CV score
    return scores.mean()


def main():
    print("\n" + "="*70)
    print("[OPTUNA] HYPERPARAMETER TUNING ДЛЯ XGBOOST")
    print("="*70 + "\n")
    
    # Параметры
    EXCHANGE = "bybit"
    SYMBOL = "BTC/USDT"
    TIMEFRAME = "1h"
    HORIZON_STEPS = 6
    N_TRIALS = 50  # Количество попыток оптимизации (больше = лучше, но медленнее)
    
    print(f"[PARAMS] Параметры:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Horizon: {HORIZON_STEPS} steps")
    print(f"   Trials: {N_TRIALS} iterations\n")
    
    # Загрузка данных
    print("[LOADING] Загрузка данных из БД...")
    db = SessionLocal()
    
    try:
        df, feature_cols = build_dataset(db, EXCHANGE, SYMBOL, TIMEFRAME, HORIZON_STEPS)
        print(f"[OK] Датасет: {len(df)} строк x {len(feature_cols)} фичей\n")
        
        # Разделение на train/test
        train_df, test_df = time_split(df, test_ratio=0.2)
        
        X_train = train_df[feature_cols].values
        y_train = train_df["y"].values
        X_test = test_df[feature_cols].values
        y_test = test_df["y"].values
        
        print(f"[SPLIT] Train: {len(X_train)} rows, Test: {len(X_test)} rows\n")
        
        # Создаём Optuna study
        print(f"[OPTUNA] Запуск оптимизации ({N_TRIALS} trials)...")
        print("   (это займёт 10-30 минут в зависимости от CPU)\n")
        
        study = optuna.create_study(
            direction='maximize',  # Maximize ROC AUC
            sampler=TPESampler(seed=42),
            study_name='xgboost_trading'
        )
        
        # Запуск оптимизации
        study.optimize(
            lambda trial: objective(trial, X_train, y_train),
            n_trials=N_TRIALS,
            show_progress_bar=True,
            n_jobs=1  # Parallel trials (осторожно с памятью!)
        )
        
        # Лучшие параметры
        print("\n" + "="*70)
        print("[RESULTS] ЛУЧШИЕ ПАРАМЕТРЫ:")
        print("="*70 + "\n")
        
        best_params = study.best_params
        best_score = study.best_value
        
        print(f"[BEST SCORE] ROC AUC (CV): {best_score:.4f}")
        print(f"\n[BEST PARAMS]:")
        for param, value in best_params.items():
            print(f"   - {param}: {value}")
        
        # Сохраняем лучшие параметры
        output_dir = Path("artifacts/config")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = output_dir / "best_xgboost_params.json"
        with open(config_path, "w") as f:
            json.dump({
                "best_params": best_params,
                "best_cv_score": best_score,
                "n_trials": N_TRIALS,
                "symbol": SYMBOL,
                "timeframe": TIMEFRAME,
            }, f, indent=2)
        
        print(f"\n[SAVED] Конфигурация сохранена: {config_path}")
        
        # Обучение финальной модели с лучшими параметрами
        print("\n" + "="*70)
        print("[TRAINING] ОБУЧЕНИЕ ФИНАЛЬНОЙ МОДЕЛИ С ОПТИМАЛЬНЫМИ ПАРАМЕТРАМИ")
        print("="*70 + "\n")
        
        final_params = {
            **best_params,
            'random_state': 42,
            'n_jobs': -1,
            'tree_method': 'hist',
        }
        
        final_model = xgb.XGBClassifier(**final_params)
        final_model.fit(X_train, y_train)
        
        # Оценка на test set
        from sklearn.metrics import roc_auc_score, accuracy_score
        
        y_pred_proba = final_model.predict_proba(X_test)[:, 1]
        y_pred = final_model.predict(X_test)
        
        test_roc_auc = roc_auc_score(y_test, y_pred_proba)
        test_accuracy = accuracy_score(y_test, y_pred)
        
        print(f"[TEST METRICS]:")
        print(f"   - ROC AUC: {test_roc_auc:.4f}")
        print(f"   - Accuracy: {test_accuracy:.4f}")
        
        # Сравнение с baseline
        baseline_path = Path("artifacts/metrics_baseline.json")
        if baseline_path.exists():
            with open(baseline_path, "r") as f:
                baseline = json.load(f)
            
            baseline_auc = baseline.get("roc_auc", 0)
            improvement = ((test_roc_auc - baseline_auc) / baseline_auc) * 100
            
            print(f"\n[COMPARISON] vs Baseline:")
            print(f"   - Baseline ROC AUC: {baseline_auc:.4f}")
            print(f"   - New ROC AUC: {test_roc_auc:.4f}")
            print(f"   - Improvement: {improvement:+.2f}%")
            
            if improvement > 0:
                print(f"   - Verdict: [SUCCESS] Улучшение!")
            else:
                print(f"   - Verdict: [WARNING] Ухудшение")
        
        print("\n" + "="*70)
        print("[SUCCESS] ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
        print("="*70)
        print("\nСледующие шаги:")
        print("1. Запустите переобучение с оптимальными параметрами:")
        print("   python scripts/train_with_best_params.py")
        print("2. Проверьте бэктест: POST /backtest/run")
        print("3. Изучите Optuna dashboard: optuna-dashboard sqlite:///optuna.db\n")
        
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

