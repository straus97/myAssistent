from pathlib import Path
import json
import glob
import os
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
import joblib
import logging

# Загрузка переменных окружения из .env
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# MLflow tracking (опционально)
try:
    import mlflow
    import mlflow.sklearn
    MLFLOW_ENABLED = os.getenv("MLFLOW_TRACKING_URI") is not None
    if MLFLOW_ENABLED:
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        logger.info(f"[mlflow] Tracking enabled: {mlflow.get_tracking_uri()}")
except ImportError:
    MLFLOW_ENABLED = False
    logger.info("[mlflow] MLflow not installed, tracking disabled")


def time_split(df: pd.DataFrame, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(df)
    if n < 2:
        raise ValueError("dataset too small (<2 rows)")
    split = max(1, min(n - 1, int(n * (1 - test_ratio))))
    return df.iloc[:split], df.iloc[split:]


def _evaluate_with_threshold(y_true: np.ndarray, proba: np.ndarray, future_ret: np.ndarray, thr: float) -> Dict:
    pred = (proba > thr).astype(int)
    acc = float(accuracy_score(y_true, pred))
    try:
        auc = float(roc_auc_score(y_true, proba))
    except Exception:
        auc = None
    strat_ret = pred * future_ret
    total_return = float(np.prod(1.0 + strat_ret) - 1.0)
    sharpe_like = (
        float(np.mean(strat_ret) / (np.std(strat_ret) + 1e-9) * np.sqrt(len(strat_ret))) if len(strat_ret) > 1 else None
    )
    return {"accuracy": acc, "roc_auc": auc, "total_return": total_return, "sharpe_like": sharpe_like}


def _select_threshold_grid(
    y_true: np.ndarray, proba: np.ndarray, future_ret: np.ndarray, grid: np.ndarray | None = None
) -> tuple[float, Dict]:
    """
    Подбирает порог по сетке с приоритетом: Sharpe -> total_return -> AUC.
    Возвращает (best_thr, best_metrics).
    """
    if grid is None:
        grid = np.arange(0.50, 0.71, 0.01)
    best_thr = float(grid[0])
    best = None
    for thr in grid:
        m = _evaluate_with_threshold(y_true, proba, future_ret, float(thr))
        if best is None:
            best, best_thr = m, float(thr)
            continue

        def score(d):
            return (
                (d["sharpe_like"] if d["sharpe_like"] is not None else -1e9),
                d["total_return"],
                (d["roc_auc"] if d["roc_auc"] is not None else -1e9),
            )

        if score(m) > score(best):
            best, best_thr = m, float(thr)
    return best_thr, best


def walk_forward_cv(
    df: pd.DataFrame,
    feature_cols: List[str],
    *,
    window_train: int = 1200,
    window_test: int = 200,
    step: int = 100,
    inner_valid_ratio: float = 0.2,
    threshold_grid: np.ndarray | None = None,
) -> Dict:
    """
    Скользящее окно: на каждом шаге:
      - делим train на inner_train/inner_valid,
      - подбираем порог на inner_valid,
      - дообучаем на полном train,
      - считаем метрики на test,
      - копим стратегию для общей equity-кривой.
    Возвращает словарь с folds и агрегатами + усечённую equity-кривую.
    """
    if df is None or df.empty:
        return {"folds": [], "summary": {"n_folds": 0}}

    df = df.dropna().copy()
    # безопасные колонки
    use_cols = [c for c in feature_cols if c in df.columns]
    if not use_cols:
        raise ValueError("walk_forward_cv: no usable feature columns found")

    n = len(df)
    folds = []
    all_strat_rets: list[float] = []
    all_time_idx: list[pd.Timestamp] = []

    i = window_train
    while i + window_test <= n:
        tr = df.iloc[i - window_train : i]
        te = df.iloc[i : i + window_test]

        # внутренний split для подбора порога
        tr_inner, va_inner = time_split(tr, test_ratio=inner_valid_ratio)

        X_tr = tr_inner[use_cols].values
        y_tr = tr_inner["y"].values
        X_va = va_inner[use_cols].values
        y_va = va_inner["y"].values
        fut_va = va_inner["future_ret"].values

        # базовая модель
        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            objective="binary:logistic",
            eval_metric="logloss",
            n_jobs=4,
            random_state=42,
            tree_method="hist",
        )
        model.fit(X_tr, y_tr)
        proba_va = model.predict_proba(X_va)[:, 1]
        best_thr, _best_on_valid = _select_threshold_grid(y_va, proba_va, fut_va, threshold_grid)

        # дообучаем на всём train-окне
        model.fit(tr[use_cols].values, tr["y"].values)

        # тест
        proba_te = model.predict_proba(te[use_cols].values)[:, 1]
        fut_te = te["future_ret"].values
        y_te = te["y"].values
        m_te = _evaluate_with_threshold(y_te, proba_te, fut_te, best_thr)

        # накапливаем стратегию и тайм-индекс для кривой
        strat = ((proba_te > best_thr).astype(int) * fut_te).tolist()
        all_strat_rets.extend(strat)
        all_time_idx.extend(te.index.to_list())

        folds.append(
            {
                "start": tr.index[0].isoformat(),
                "end": te.index[-1].isoformat(),
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
                "threshold": float(best_thr),
                "accuracy": float(m_te["accuracy"]),
                "roc_auc": (float(m_te["roc_auc"]) if m_te["roc_auc"] is not None else None),
                "total_return": float(m_te["total_return"]),
                "sharpe_like": (float(m_te["sharpe_like"]) if m_te["sharpe_like"] is not None else None),
            }
        )

        i += max(1, int(step))

    if not folds:
        return {"folds": [], "summary": {"n_folds": 0}}

    # агрегаты по фолдам
    aucs = [f["roc_auc"] for f in folds if f["roc_auc"] is not None]
    sharpes = [f["sharpe_like"] for f in folds if f["sharpe_like"] is not None]
    auc_mean = float(np.mean(aucs)) if aucs else None
    sharpe_mean = float(np.mean(sharpes)) if sharpes else None

    # общая equity-кривая на тестовых отрезках
    eq = []
    s = 1.0
    for r in all_strat_rets:
        s *= 1.0 + float(r)
        eq.append(s)

    total_return_cum = float(s - 1.0)

    # уменьшим размер для metrics.json (до 400 точек)
    max_pts = 400
    if len(eq) > max_pts:
        step_idx = int(np.ceil(len(eq) / max_pts))
    else:
        step_idx = 1
    eq_ds = eq[::step_idx]
    ts_ds = [t.isoformat() for t in all_time_idx[::step_idx]]

    return {
        "params": {
            "window_train": int(window_train),
            "window_test": int(window_test),
            "step": int(step),
            "inner_valid_ratio": float(inner_valid_ratio),
        },
        "folds": folds,
        "summary": {
            "n_folds": int(len(folds)),
            "auc_mean": auc_mean,
            "sharpe_mean": sharpe_mean,
            "total_return_cum": total_return_cum,
        },
        "curve": {"timestamps": ts_ds, "equity": eq_ds},
    }


def train_xgb_and_save(
    df: pd.DataFrame,
    feature_cols: List[str],
    artifacts_dir: str = "artifacts",
    test_ratio: float = 0.2,
    mlflow_experiment: str = "myassistent-trading",
    mlflow_run_name: str | None = None,
) -> Tuple[Dict, str]:
    """Тренируем XGB, подбираем threshold по сетке, сохраняем .pkl и метрики."""
    Path(artifacts_dir).mkdir(exist_ok=True)
    models_dir = Path(artifacts_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    df = df.dropna().copy()
    if df.empty:
        raise ValueError("empty dataframe passed to train_xgb_and_save")
    if not feature_cols:
        raise ValueError("feature_cols is empty")

    # безопасный сабсет — только реально существующие колонки
    use_cols = [c for c in feature_cols if c in df.columns]
    missing_cols = sorted(set(feature_cols) - set(use_cols))
    if missing_cols:
        print(f"[modeling] Missing features skipped: {missing_cols[:8]}{'...' if len(missing_cols) > 8 else ''}")

    df_train, df_test = time_split(df, test_ratio=test_ratio)
    if df_test.empty:
        raise ValueError("test split is empty")

    X_train = df_train[use_cols].values
    y_train = df_train["y"].values
    X_test = df_test[use_cols].values
    y_test = df_test["y"].values
    fut = df_test["future_ret"].values

    # ============ MLflow Tracking Start ============
    if MLFLOW_ENABLED:
        try:
            mlflow.set_experiment(mlflow_experiment)
            mlflow.start_run(run_name=mlflow_run_name)
            
            # Log hyperparameters
            mlflow.log_params({
                "n_estimators": 300,
                "max_depth": 4,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_lambda": 1.0,
                "n_train": len(df_train),
                "n_test": len(df_test),
                "n_features": len(use_cols),
                "test_ratio": test_ratio,
            })
        except Exception as e:
            logger.warning(f"[mlflow] Failed to start run: {e}")

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=4,
        random_state=42,
    )
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]

    # поиск порога (Sharpe -> total_return -> AUC)
    candidates = np.arange(0.50, 0.71, 0.01)
    best = None
    best_thr = 0.55
    for thr in candidates:
        m = _evaluate_with_threshold(y_test, proba, fut, thr)
        if best is None:
            best, best_thr = m, float(thr)
            continue

        def score(d):
            return (
                (d["sharpe_like"] if d["sharpe_like"] is not None else -1e9),
                d["total_return"],
                (d["roc_auc"] if d["roc_auc"] is not None else -1e9),
            )

        if score(m) > score(best):
            best, best_thr = m, float(thr)

    # собираем метрики и сохраняем артефакты
    metrics = {"n_train": int(len(df_train)), "n_test": int(len(df_test)), "threshold": float(best_thr), **best}

    ts = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    model_path = models_dir / f"xgb_{ts}.pkl"  # ← единый формат .pkl
    joblib.dump(
        {"model": model, "feature_cols": use_cols, "threshold": float(best_thr), "metrics": metrics}, model_path
    )

    # файлы для UI
    with open(Path(artifacts_dir) / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    with open(Path(artifacts_dir) / "features.json", "w", encoding="utf-8") as f:
        json.dump({"features": use_cols}, f, ensure_ascii=False, indent=2)

    # ============ MLflow Tracking End ============
    if MLFLOW_ENABLED:
        try:
            # Log metrics
            mlflow.log_metrics({
                "accuracy": metrics["accuracy"],
                "roc_auc": metrics.get("roc_auc") or 0,
                "threshold": metrics["threshold"],
                "total_return": metrics["total_return"],
                "sharpe_like": metrics.get("sharpe_like") or 0,
            })
            
            # Log model to MLflow with signature
            mlflow.sklearn.log_model(
                model, 
                "model",
                registered_model_name="xgboost_trading_model"
            )
            
            # Log artifacts
            mlflow.log_artifact(str(model_path), "model_artifacts")
            mlflow.log_artifact(str(Path(artifacts_dir) / "metrics.json"), "metrics")
            mlflow.log_artifact(str(Path(artifacts_dir) / "features.json"), "features")
            
            # Log feature importance
            if hasattr(model, "feature_importances_"):
                importance_dict = dict(zip(use_cols, model.feature_importances_.tolist()))
                mlflow.log_dict(importance_dict, "feature_importance.json")
            
            # Log tags for easy filtering
            mlflow.set_tags({
                "stage": "challenger",
                "n_features": len(use_cols),
                "model_type": "XGBoost",
            })
            
            run_id = mlflow.active_run().info.run_id
            logger.info(f"[mlflow] Run logged successfully (run_id: {run_id})")
            
            mlflow.end_run()
            
            logger.info("[mlflow] Model logged to registry as 'xgboost_trading_model'")
            logger.info("[mlflow] Use MLflow UI to promote model to 'Staging' or 'Production'")
            
        except Exception as e:
            logger.warning(f"[mlflow] Failed to log run: {e}")
            try:
                mlflow.end_run()
            except:
                pass

    return metrics, str(model_path.resolve())


def load_latest_model(artifacts_dir: str = "artifacts", model_path: str | None = None):
    """
    Возвращает (model, feature_cols, threshold, path).
    Поддерживает и .pkl, и .joblib; приоритет — самый свежий.
    """
    if model_path is None:
        models_dir = Path(artifacts_dir) / "models"
        candidates = sorted(glob.glob(str(models_dir / "*.pkl")) + glob.glob(str(models_dir / "*.joblib")))
        if not candidates:
            raise FileNotFoundError("Модель не найдена: нет файлов в artifacts/models")
        model_path = candidates[-1]

    obj = joblib.load(model_path)
    if isinstance(obj, dict):
        model = obj.get("model") or obj.get("estimator") or obj
        feature_cols = obj.get("feature_cols") or obj.get("features") or []
        threshold = float(obj.get("threshold", 0.55))
    else:
        model = obj
        feature_cols, threshold = [], 0.55
    return model, [str(c) for c in feature_cols], threshold, str(Path(model_path).resolve())


def load_model_from_path(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"model file not found: {p}")
    obj = joblib.load(p)
    if isinstance(obj, dict):
        model = obj.get("model") or obj.get("estimator") or obj
        feature_cols = obj.get("feature_cols") or obj.get("features") or []
        threshold = float(obj.get("threshold", 0.55))
    else:
        model = obj
        feature_cols, threshold = [], 0.55
    return model, [str(c) for c in feature_cols], threshold, str(p)
