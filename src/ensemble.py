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
    
    logger.info(f"[Ensemble] {model_type}: Accuracy={acc:.4f}, AUC={auc:.4f if auc else 'N/A'}")
    
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
    
    logger.info(f"[Ensemble] Voting: Accuracy={acc:.4f}, AUC={auc:.4f if auc else 'N/A'}")
    
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
    
    logger.info(f"[Ensemble] Stacking: Accuracy={acc:.4f}, AUC={auc:.4f if auc else 'N/A'}")
    
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

