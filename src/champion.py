from __future__ import annotations
import json
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import roc_auc_score
from sqlalchemy.orm import Session
from src.db import ModelRun
from src.features import build_dataset
from src.model_registry import get_active_model_path, set_active_model
from src.notify import send_telegram


def _load_model_from_run(run: ModelRun):
    obj = joblib.load(run.model_path)
    try:
        fj = json.loads(run.features_json or "{}")
    except Exception:
        fj = {}
    features = (fj.get("features") or [])[:]
    thr = float(run.threshold or 0.5)

    model = obj
    if isinstance(obj, dict):
        model = obj.get("model") or obj.get("estimator") or obj.get("clf") or obj.get("pipeline")
        if obj.get("features"):
            features = list(obj["features"])
        if obj.get("feature_cols"):
            features = list(obj["feature_cols"])
        if obj.get("threshold") is not None:
            thr = float(obj["threshold"])

    if model is None:
        raise ValueError(f"Bad model artifact at {run.model_path}: no model inside")

    return model, features, thr


def _predict_proba_safe(model, X: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = np.asarray(model.predict_proba(X))
        if p.ndim == 2 and p.shape[1] >= 2:
            p = p[:, 1]
        return p.astype(float)
    try:
        import xgboost as xgb

        if isinstance(model, xgb.Booster):
            dm = xgb.DMatrix(X)
            p = model.predict(dm)
            return p.astype(float)
    except Exception:
        pass
    if hasattr(model, "decision_function"):
        z = np.asarray(model.decision_function(X), dtype=float)
        return (1.0 / (1.0 + np.exp(-z))).astype(float)
    if hasattr(model, "predict"):
        y = np.asarray(model.predict(X), dtype=float)
        y_min, y_max = float(y.min()), float(y.max())
        return ((y - y_min) / (y_max - y_min + 1e-12)).astype(float)
    raise AttributeError(f"{type(model)} has no predict_proba/predict/decision_function")


def _equity_curve(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + returns)


def _sharpe_like(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    mu, sd = float(np.mean(returns)), float(np.std(returns) + 1e-12)
    return mu / sd


def _max_drawdown(equity: np.ndarray) -> float:
    if equity.size == 0:
        return 0.0
    peak = -1e9
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    return float(mdd)


def _build_oos_frame(
    db: Session, ex: str, sym: str, tf: str, hz: int, tail_rows: int
) -> Tuple[pd.DataFrame, List[str]]:
    df, feats = build_dataset(db, ex, sym, tf, hz)
    if tail_rows and tail_rows > 0:
        # оставляем хвост + запас под сдвиг future_ret
        df = df.tail(int(tail_rows + hz + 2))
    return df, feats


def _evaluate_strategy(y_true: np.ndarray, proba: np.ndarray, fut_ret: np.ndarray, thr: float) -> Dict[str, Any]:
    pred_buy = (proba > thr).astype(int)
    # доходности только когда покупаем
    strat_ret = pred_buy * fut_ret

    # классика
    try:
        auc = float(roc_auc_score(y_true, proba))
    except Exception:
        auc = None

    buys = pred_buy.sum()
    wins = int(((fut_ret > 0) & (pred_buy == 1)).sum())
    hit_rate = (wins / buys) if buys > 0 else None
    avg_ret_h = float(np.mean(fut_ret[pred_buy == 1])) if buys > 0 else None

    eq = _equity_curve(strat_ret)
    mdd = _max_drawdown(eq)
    total_return = float(eq[-1] - 1.0) if eq.size else 0.0
    sharpe_like = _sharpe_like(strat_ret)

    return {
        "roc_auc": auc,
        "hit_rate": (float(hit_rate) if hit_rate is not None else None),
        "ret_h_mean": (float(avg_ret_h) if avg_ret_h is not None else None),
        "total_return": total_return,
        "sharpe_like": float(sharpe_like),
        "mdd": float(mdd),
        "n_buys": int(buys),
        "n_obs": int(len(y_true)),
    }


def eval_model_oos(db: Session, run: ModelRun, horizon_steps: int, tail_rows: int = 1800) -> Dict[str, Any]:
    """Оценка модели на роллинговом OOS (хвост датасета)."""
    model, feats, thr_saved = _load_model_from_run(run)
    df, feats_ds = _build_oos_frame(db, run.exchange, run.symbol, run.timeframe, horizon_steps, tail_rows)

    # согласуем признаки
    features = feats if feats else feats_ds
    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValueError(f"missing features: {missing[:6]} ...")

    X = df[features].values
    proba = _predict_proba_safe(model, X)

    # с учётом того, что future_ret уже сдвинут, берём валидные срезы
    y = df["y"].values
    fut = df["future_ret"].values
    mask = np.isfinite(fut) & np.isfinite(y) & np.isfinite(proba)
    y, fut, proba = y[mask].astype(int), fut[mask].astype(float), proba[mask].astype(float)

    metrics = _evaluate_strategy(y, proba, fut, float(thr_saved))

    return {
        "status": "ok",
        "exchange": run.exchange,
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "horizon_steps": horizon_steps,
        "model_path": run.model_path,
        "threshold": float(thr_saved),
        "oos": metrics,
        "tail_rows_used": int(len(y)),
    }


def _pick_runs(db: Session, ex: str, sym: str, tf: str, hz: int) -> Tuple[Optional[ModelRun], Optional[ModelRun]]:
    """Возвращает (champion_run, challenger_run). Champion — активная модель; Challenger — последний прогон."""
    # последний прогон как challenger
    runs = (
        db.query(ModelRun)
        .filter(ModelRun.exchange == ex, ModelRun.symbol == sym, ModelRun.timeframe == tf, ModelRun.horizon_steps == hz)
        .order_by(ModelRun.id.desc())
        .limit(5)
        .all()
    )
    if not runs:
        return None, None
    challenger = runs[0]

    # champion — активный путь, если он среди прогонов; иначе предыдущий прогон
    active = get_active_model_path(ex, sym, tf, hz)
    champion = None
    if active:
        for r in runs:
            if r.model_path == active:
                champion = r
                break
    if champion is None and len(runs) >= 2:
        champion = runs[1]
    if champion is None:
        champion = challenger
    return champion, challenger


def compare_and_maybe_promote(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    horizon_steps: int,
    min_auc_gain: float = 0.005,
    prefer_sharpe: bool = True,
    tail_rows: int = 1800,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Сравнивает champion/challenger на одном OOS и, при превосходстве, промоутит challenger."""
    champ, chall = _pick_runs(db, exchange, symbol, timeframe, horizon_steps)
    if chall is None:
        return {"status": "error", "detail": "no runs"}
    if champ is None:
        champ = chall

    eval_champ = eval_model_oos(db, champ, horizon_steps, tail_rows)["oos"]
    eval_chall = eval_model_oos(db, chall, horizon_steps, tail_rows)["oos"]

    auc_c = float(eval_champ.get("roc_auc") or 0.0)
    auc_n = float(eval_chall.get("roc_auc") or 0.0)
    sh_c = float(eval_champ.get("sharpe_like") or 0.0)
    sh_n = float(eval_chall.get("sharpe_like") or 0.0)

    better_by_auc = auc_n >= auc_c + float(min_auc_gain)
    better_by_sharpe = sh_n > sh_c + 1e-9

    should_promote = False
    reason = ""
    if prefer_sharpe:
        if better_by_sharpe and (auc_n >= max(auc_c - 1e-3, 0.0)):
            should_promote = True
            reason = f"sharpe {sh_c:.3f} → {sh_n:.3f} (AUC {auc_c:.3f} → {auc_n:.3f})"
    if not should_promote and better_by_auc:
        should_promote = True
        reason = f"auc {auc_c:.3f} → {auc_n:.3f} (Δ≥{min_auc_gain:.3f})"

    promoted = False
    if should_promote and not dry_run:
        set_active_model(exchange, symbol, timeframe, horizon_steps, chall.model_path)
        promoted = True
        try:
            send_telegram(
                "🏆 PROMOTE\n"
                f"{exchange.upper()} {symbol} {timeframe} (hz={horizon_steps})\n"
                f"{reason}\n"
                f"📦 {chall.model_path}"
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "pair": {"exchange": exchange, "symbol": symbol, "timeframe": timeframe, "horizon_steps": horizon_steps},
        "champion": {"run_id": champ.id, "model_path": champ.model_path, "oos": eval_champ},
        "challenger": {"run_id": chall.id, "model_path": chall.model_path, "oos": eval_chall},
        "decision": {
            "should_promote": bool(should_promote),
            "promoted": bool(promoted),
            "reason": reason if should_promote else "no_improvement",
        },
        "prefer_sharpe": bool(prefer_sharpe),
        "min_auc_gain": float(min_auc_gain),
        "tail_rows": int(tail_rows),
        "dry_run": bool(dry_run),
    }
