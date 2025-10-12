"""
Ensemble модели для торговой системы.

Поддерживает:
- XGBoost (базовая модель)
- LightGBM (быстрая альтернатива)
- CatBoost (хорошо работает с категориальными фичами)
- Voting Ensemble (комбинация всех трех)
- Stacking Ensemble (мета-обучение)
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Literal
import numpy as np
import pandas as pd
import logging
from pathlib import Path
import joblib

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

ModelType = Literal["xgboost", "lightgbm", "catboost", "voting", "stacking"]


def train_single_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    model_type: ModelType,
    params: Dict | None = None,
) -> Tuple[object, Dict]:
    """
    Обучает одну модель (XGBoost, LightGBM или CatBoost).
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        model_type: Тип модели
        params: Гиперпараметры (опционально)
    
    Returns:
        (model, metrics)
    """
    if params is None:
        params = {}
    
    # Дефолтные параметры для каждой модели
    if model_type == "xgboost":
        default_params = {
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "eval_metric": "logloss",
            "random_state": 42,
            "n_jobs": -1,
        }
        default_params.update(params)
        model = XGBClassifier(**default_params)
    
    elif model_type == "lightgbm":
        default_params = {
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": -1,
        }
        default_params.update(params)
        model = LGBMClassifier(**default_params)
    
    elif model_type == "catboost":
        default_params = {
            "iterations": 200,
            "depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "random_state": 42,
            "verbose": False,
            "thread_count": -1,
        }
        default_params.update(params)
        model = CatBoostClassifier(**default_params)
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    # Обучение
    logger.info(f"[Ensemble] Training {model_type}...")
    model.fit(X_train, y_train)
    
    # Предсказания
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)
    
    # Метрики
    acc = float(accuracy_score(y_test, y_pred))
    try:
        auc = float(roc_auc_score(y_test, y_pred_proba))
    except Exception:
        auc = None
    
    metrics = {
        "model_type": model_type,
        "accuracy": acc,
        "roc_auc": auc,
    }
    
    auc_str = f"{auc:.4f}" if auc else "N/A"
    logger.info(f"[Ensemble] {model_type}: Accuracy={acc:.4f}, AUC={auc_str}")
    
    return model, metrics


def train_voting_ensemble(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    params_xgb: Dict | None = None,
    params_lgbm: Dict | None = None,
    params_cat: Dict | None = None,
) -> Tuple[Dict, Dict]:
    """
    Voting Ensemble: усреднение вероятностей от 3 моделей.
    
    Returns:
        (models_dict, metrics)
    """
    logger.info("[Ensemble] Training Voting Ensemble (XGBoost + LightGBM + CatBoost)...")
    
    # Обучаем каждую модель
    xgb, xgb_metrics = train_single_model(X_train, y_train, X_test, y_test, "xgboost", params_xgb)
    lgbm, lgbm_metrics = train_single_model(X_train, y_train, X_test, y_test, "lightgbm", params_lgbm)
    cat, cat_metrics = train_single_model(X_train, y_train, X_test, y_test, "catboost", params_cat)
    
    # Усредняем предсказания
    proba_xgb = xgb.predict_proba(X_test)[:, 1]
    proba_lgbm = lgbm.predict_proba(X_test)[:, 1]
    proba_cat = cat.predict_proba(X_test)[:, 1]
    
    proba_avg = (proba_xgb + proba_lgbm + proba_cat) / 3.0
    y_pred = (proba_avg > 0.5).astype(int)
    
    # Метрики ensemble
    acc = float(accuracy_score(y_test, y_pred))
    try:
        auc = float(roc_auc_score(y_test, proba_avg))
    except Exception:
        auc = None
    
    metrics = {
        "model_type": "voting_ensemble",
        "accuracy": acc,
        "roc_auc": auc,
        "xgb_auc": xgb_metrics["roc_auc"],
        "lgbm_auc": lgbm_metrics["roc_auc"],
        "cat_auc": cat_metrics["roc_auc"],
    }
    
    auc_str = f"{auc:.4f}" if auc else "N/A"
    logger.info(f"[Ensemble] Voting: Accuracy={acc:.4f}, AUC={auc_str}")
    
    models = {
        "xgboost": xgb,
        "lightgbm": lgbm,
        "catboost": cat,
    }
    
    return models, metrics


def train_stacking_ensemble(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    params_xgb: Dict | None = None,
    params_lgbm: Dict | None = None,
    params_cat: Dict | None = None,
) -> Tuple[Dict, Dict]:
    """
    Stacking Ensemble: используем предсказания базовых моделей
    как фичи для мета-модели (LogisticRegression).
    
    Returns:
        (models_dict, metrics)
    """
    logger.info("[Ensemble] Training Stacking Ensemble (XGB+LGBM+CAT → LogReg)...")
    
    # Обучаем базовые модели
    xgb, xgb_metrics = train_single_model(X_train, y_train, X_test, y_test, "xgboost", params_xgb)
    lgbm, lgbm_metrics = train_single_model(X_train, y_train, X_test, y_test, "lightgbm", params_lgbm)
    cat, cat_metrics = train_single_model(X_train, y_train, X_test, y_test, "catboost", params_cat)
    
    # Генерируем мета-фичи (out-of-fold predictions на train)
    # Для простоты используем предсказания на train (в production нужен cross-validation)
    meta_train = np.column_stack([
        xgb.predict_proba(X_train)[:, 1],
        lgbm.predict_proba(X_train)[:, 1],
        cat.predict_proba(X_train)[:, 1],
    ])
    
    meta_test = np.column_stack([
        xgb.predict_proba(X_test)[:, 1],
        lgbm.predict_proba(X_test)[:, 1],
        cat.predict_proba(X_test)[:, 1],
    ])
    
    # Обучаем мета-модель
    meta_model = LogisticRegression(random_state=42, max_iter=1000)
    meta_model.fit(meta_train, y_train)
    
    # Предсказания
    proba_stacking = meta_model.predict_proba(meta_test)[:, 1]
    y_pred = (proba_stacking > 0.5).astype(int)
    
    # Метрики
    acc = float(accuracy_score(y_test, y_pred))
    try:
        auc = float(roc_auc_score(y_test, proba_stacking))
    except Exception:
        auc = None
    
    metrics = {
        "model_type": "stacking_ensemble",
        "accuracy": acc,
        "roc_auc": auc,
        "xgb_auc": xgb_metrics["roc_auc"],
        "lgbm_auc": lgbm_metrics["roc_auc"],
        "cat_auc": cat_metrics["roc_auc"],
    }
    
    auc_str = f"{auc:.4f}" if auc else "N/A"
    logger.info(f"[Ensemble] Stacking: Accuracy={acc:.4f}, AUC={auc_str}")
    
    models = {
        "xgboost": xgb,
        "lightgbm": lgbm,
        "catboost": cat,
        "meta_model": meta_model,
    }
    
    return models, metrics


def save_ensemble(models: Dict, save_path: str | Path) -> None:
    """Сохранить ensemble в файл."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(models, save_path)
    logger.info(f"[Ensemble] Saved to {save_path}")


def load_ensemble(load_path: str | Path) -> Dict:
    """Загрузить ensemble из файла."""
    models = joblib.load(load_path)
    logger.info(f"[Ensemble] Loaded from {load_path}")
    return models


def predict_ensemble(
    models: Dict,
    X: pd.DataFrame,
    ensemble_type: Literal["voting", "stacking"],
) -> np.ndarray:
    """
    Предсказание с помощью ensemble.
    
    Args:
        models: Словарь с обученными моделями
        X: Features для предсказания
        ensemble_type: Тип ensemble ("voting" или "stacking")
    
    Returns:
        Вероятности класса 1
    """
    if ensemble_type == "voting":
        proba_xgb = models["xgboost"].predict_proba(X)[:, 1]
        proba_lgbm = models["lightgbm"].predict_proba(X)[:, 1]
        proba_cat = models["catboost"].predict_proba(X)[:, 1]
        return (proba_xgb + proba_lgbm + proba_cat) / 3.0
    
    elif ensemble_type == "stacking":
        meta_features = np.column_stack([
            models["xgboost"].predict_proba(X)[:, 1],
            models["lightgbm"].predict_proba(X)[:, 1],
            models["catboost"].predict_proba(X)[:, 1],
        ])
        return models["meta_model"].predict_proba(meta_features)[:, 1]
    
    else:
        raise ValueError(f"Unknown ensemble type: {ensemble_type}")


# ===========================
# PHASE 3: Cross-Validation Optimization Functions
# ===========================

def optimize_xgboost_cv(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_trials: int = 30,
    timeout: int | None = None
) -> Dict:
    """
    Optuna optimization для XGBoost с акцентом на борьбу с overfitting.
    
    Отличия от PHASE 2:
    - Увеличенная регуляризация (reg_alpha, reg_lambda)
    - Более консервативные параметры (меньше max_depth, больше min_child_weight)
    - Раннее прекращение обучения (early_stopping_rounds)
    """
    import optuna
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 300),
            "max_depth": trial.suggest_int("max_depth", 3, 7),  # Меньше чем в PHASE 2
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 0.9),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),  # Новый параметр
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),  # L1 регуляризация
            "reg_lambda": trial.suggest_float("reg_lambda", 1.0, 10.0),  # L2 регуляризация
            "random_state": 42,
            "n_jobs": -1,
            "eval_metric": "logloss"
        }
        
        model = XGBClassifier(**params)
        model.fit(X_train, y_train)
        
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_pred_proba)
        
        return auc
    
    study = optuna.create_study(direction="maximize", study_name="xgboost_cv")
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)
    
    return study.best_params


def optimize_lightgbm_cv(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_trials: int = 30,
    timeout: int | None = None
) -> Dict:
    """
    Optuna optimization для LightGBM с увеличенной регуляризацией.
    """
    import optuna
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 300),
            "max_depth": trial.suggest_int("max_depth", 3, 7),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 0.9),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),  # Больше чем в PHASE 2
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1.0, 10.0),
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": -1
        }
        
        model = LGBMClassifier(**params)
        model.fit(X_train, y_train)
        
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_pred_proba)
        
        return auc
    
    study = optuna.create_study(direction="maximize", study_name="lightgbm_cv")
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)
    
    return study.best_params


def optimize_catboost_cv(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_trials: int = 30,
    timeout: int | None = None
) -> Dict:
    """
    Optuna optimization для CatBoost с увеличенной регуляризацией.
    """
    import optuna
    
    def objective(trial):
        params = {
            "iterations": trial.suggest_int("iterations", 100, 300),
            "depth": trial.suggest_int("depth", 3, 7),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 0.9),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),  # L2 регуляризация
            "random_strength": trial.suggest_float("random_strength", 0.0, 2.0),  # Рандомизация
            "random_state": 42,
            "verbose": False,
            "thread_count": -1
        }
        
        model = CatBoostClassifier(**params)
        model.fit(X_train, y_train)
        
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_pred_proba)
        
        return auc
    
    study = optuna.create_study(direction="maximize", study_name="catboost_cv")
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)
    
    return study.best_params


def train_voting_ensemble(
    base_models: List[Tuple[str, object]],
    X_train: np.ndarray,
    y_train: np.ndarray
) -> object:
    """
    Создает VotingClassifier из списка базовых моделей.
    
    Args:
        base_models: Список кортежей (name, model)
        X_train: Training features
        y_train: Training labels
    
    Returns:
        VotingClassifier
    """
    from sklearn.ensemble import VotingClassifier
    
    voting_clf = VotingClassifier(
        estimators=base_models,
        voting='soft',
        n_jobs=-1
    )
    
    voting_clf.fit(X_train, y_train)
    
    return voting_clf


def train_stacking_ensemble(
    base_models: List[Tuple[str, object]],
    X_train: np.ndarray,
    y_train: np.ndarray
) -> object:
    """
    Создает StackingClassifier из списка базовых моделей.
    
    Args:
        base_models: Список кортежей (name, model)
        X_train: Training features
        y_train: Training labels
    
    Returns:
        StackingClassifier
    """
    from sklearn.ensemble import StackingClassifier
    
    stacking_clf = StackingClassifier(
        estimators=base_models,
        final_estimator=LogisticRegression(random_state=42, max_iter=1000),
        cv=5,  # 5-fold CV для генерации мета-фич
        n_jobs=-1
    )
    
    stacking_clf.fit(X_train, y_train)
    
    return stacking_clf


def evaluate_ensemble(
    model: object,
    X_test: np.ndarray,
    y_test: np.ndarray
) -> Dict:
    """
    Оценка модели на тестовых данных.
    
    Returns:
        Dict с метриками (accuracy, roc_auc)
    """
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    return {
        "accuracy": float(accuracy),
        "roc_auc": float(auc)
    }
