"""
Роутер для работы с ML моделями (train, eval, champion/challenger, health)
"""
from __future__ import annotations
import json
from typing import Any, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key
from src.db import ModelRun
from src.features import build_dataset
from src.modeling import train_xgb_and_save
from src.model_policy import load_model_policy, save_model_policy
from src.model_registry import (
    set_active_model,
    get_active_model_path,
    choose_latest_model_path,
)
from src.champion import eval_model_oos, compare_and_maybe_promote
from src.watchlist import pairs_for_jobs
from src.utils import _now_utc


router = APIRouter(prefix="/model", tags=["Model"])


# ===== Вспомогательные функции =====


def _age_days(dt: Optional[datetime]) -> Optional[float]:
    """Вычисляет возраст модели в днях"""
    if not dt:
        return None
    if dt.tzinfo is None:
        from datetime import timezone as _tz

        dt = dt.replace(tzinfo=_tz.utc)
    delta = _now_utc() - dt
    return max(0.0, delta.total_seconds() / 86400.0)


def _last_run_for(db: Session, ex: str, sym: str, tf: str, hz: int):
    """Находит последний ModelRun для указанных параметров"""
    return (
        db.query(ModelRun)
        .filter(
            ModelRun.exchange == ex,
            ModelRun.symbol == sym,
            ModelRun.timeframe == tf,
            ModelRun.horizon_steps == hz,
        )
        .order_by(ModelRun.id.desc())
        .first()
    )


def _model_needs_retrain(db: Session, ex: str, sym: str, tf: str, hz: int, policy: dict, df_len: Optional[int]):
    """Проверяет, нужно ли переобучать модель по SLA-политике"""
    last = _last_run_for(db, ex, sym, tf, hz)
    age = _age_days(last.created_at) if last else None

    if last is None:
        return True, "no_run", {"age_days": None, "roc_auc": None, "df_len": df_len}

    if age is not None and age > float(policy.get("max_age_days", 7)):
        return True, f"stale_{age:.1f}d", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}

    auc_thr = float(policy.get("retrain_if_auc_below", 0.55))
    if (last.roc_auc is not None) and (last.roc_auc < auc_thr):
        return True, f"low_auc_{last.roc_auc:.3f}", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}

    return False, "fresh", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}


def _train_missing_impl(db: Session) -> dict:
    """Умная дотренировка: проверяет SLA для всех пар и тренирует только устаревшие/плохие модели"""
    policy = load_model_policy()
    pairs = pairs_for_jobs()
    results = []
    for ex, sym, tf, _ in pairs:
        hz = 6 if tf.endswith("h") else 12
        try:
            df, feature_cols = build_dataset(db, ex, sym, tf, hz)
            if len(df) < int(policy.get("min_train_rows", 200)):
                results.append(
                    {"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"skip:not_enough_data({len(df)})"}
                )
                continue

            need, reason, _ = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=len(df))
            if not need:
                results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"skip:{reason}"})
                continue

            metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
            run = ModelRun(
                exchange=ex,
                symbol=sym,
                timeframe=tf,
                horizon_steps=hz,
                n_train=metrics["n_train"],
                n_test=metrics["n_test"],
                accuracy=metrics.get("accuracy"),
                roc_auc=metrics.get("roc_auc"),
                threshold=metrics.get("threshold"),
                total_return=metrics.get("total_return"),
                sharpe_like=metrics.get("sharpe_like"),
                model_path=model_path,
                features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
            )
            db.add(run)
            db.commit()

            if not get_active_model_path(ex, sym, tf, hz):
                set_active_model(ex, sym, tf, hz, model_path)

            results.append(
                {
                    "exchange": ex,
                    "symbol": sym,
                    "timeframe": tf,
                    "status": "trained",
                    "reason": reason,
                    "model_path": model_path,
                    "metrics": metrics,
                }
            )
        except Exception as e:
            results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"error:{e}"})
    return {"status": "ok", "results": results}


# ===== Эндпоинты =====


class ModelTrainRequest(BaseModel):
    """Запрос на обучение модели"""

    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 6


@router.post("/train")
def model_train(req: ModelTrainRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Обучить новую модель для указанной пары"""
    try:
        df, feature_cols = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if len(df) < 200:
            return {"status": "error", "detail": "Данных слишком мало (<200 строк) для тренировки."}
        metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
        run = ModelRun(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            horizon_steps=req.horizon_steps,
            n_train=metrics["n_train"],
            n_test=metrics["n_test"],
            accuracy=metrics.get("accuracy"),
            roc_auc=metrics.get("roc_auc"),
            threshold=metrics.get("threshold"),
            total_return=metrics.get("total_return"),
            sharpe_like=metrics.get("sharpe_like"),
            model_path=model_path,
            features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return {"status": "ok", "metrics": metrics, "run_id": run.id, "model_path": model_path}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/train_missing")
def model_train_missing(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Умная дотренировка: тренирует только устаревшие/плохие модели по SLA"""
    return _train_missing_impl(db)


@router.get("/runs")
def model_runs(
    limit: int = 50,
    exchange: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    horizon_steps: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Получить список ModelRun'ов с фильтрацией"""
    q = db.query(ModelRun)
    if exchange:
        q = q.filter(ModelRun.exchange == exchange)
    if symbol:
        q = q.filter(ModelRun.symbol == symbol)
    if timeframe:
        q = q.filter(ModelRun.timeframe == timeframe)
    if horizon_steps is not None:
        q = q.filter(ModelRun.horizon_steps == horizon_steps)
    rows = q.order_by(ModelRun.id.desc()).limit(limit).all()

    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "created_at": r.created_at,
                "exchange": r.exchange,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "horizon_steps": r.horizon_steps,
                "n_train": r.n_train,
                "n_test": r.n_test,
                "accuracy": r.accuracy,
                "roc_auc": r.roc_auc,
                "threshold": r.threshold,
                "total_return": r.total_return,
                "sharpe_like": r.sharpe_like,
                "model_path": r.model_path,
            }
        )
    return out


# --- Model Policy (SLA) ---


@router.get("/policy")
def model_policy_get():
    """Получить SLA-политику моделей"""
    return load_model_policy()


class ModelPolicyUpdate(BaseModel):
    """Обновление SLA-политики моделей"""

    updates: Dict[str, Any]


@router.post("/policy")
def model_policy_set(req: ModelPolicyUpdate, _=Depends(require_api_key)):
    """Обновить SLA-политику моделей"""
    cur = load_model_policy()
    cur.update(req.updates or {})
    save_model_policy(cur)
    return {"status": "ok", "policy": load_model_policy()}


# --- Model Health (per watchlist) ---


@router.get("/health")
def model_health(db: Session = Depends(get_db)):
    """Проверить свежесть моделей для всех пар в watchlist"""
    policy = load_model_policy()
    pairs = pairs_for_jobs()
    out = []
    for ex, sym, tf, _ in pairs:
        hz = 6 if tf.endswith("h") else 12
        last = _last_run_for(db, ex, sym, tf, hz)
        age = _age_days(last.created_at) if last else None
        need, reason, meta = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=None)
        out.append(
            {
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "horizon_steps": hz,
                "last_run_id": getattr(last, "id", None),
                "last_created_at": getattr(last, "created_at", None),
                "last_roc_auc": getattr(last, "roc_auc", None),
                "age_days": age,
                "need_retrain": need,
                "reason": reason,
            }
        )
    return out


# --- Active Model Management ---


class ActiveModelSet(BaseModel):
    """Запрос на установку активной модели"""

    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    model_path: str


@router.post("/active")
def model_active_set(req: ActiveModelSet, _=Depends(require_api_key)):
    """Установить активную модель для пары (ручной выбор)"""
    set_active_model(req.exchange, req.symbol, req.timeframe, req.horizon_steps, req.model_path)
    return {
        "status": "ok",
        "exchange": req.exchange,
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "horizon_steps": req.horizon_steps,
        "active_model_path": get_active_model_path(req.exchange, req.symbol, req.timeframe, req.horizon_steps),
    }


@router.get("/active")
def model_active_get(exchange: str, symbol: str, timeframe: str, horizon_steps: int, db: Session = Depends(get_db)):
    """Получить активную модель для пары"""
    manual = get_active_model_path(exchange, symbol, timeframe, horizon_steps)
    latest = choose_latest_model_path(db, exchange, symbol, timeframe, horizon_steps)
    source = "manual" if manual else ("latest_from_runs" if latest else None)
    return {
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon_steps": horizon_steps,
        "active_manual": manual,
        "latest_from_runs": latest,
        "source": source,
    }


# --- OOS Evaluation & Champion/Challenger ---


class OOSEvalRequest(BaseModel):
    """Запрос на OOS-оценку модели"""

    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    run_id: Optional[int] = None
    tail_rows: int = 1800


@router.post("/eval_oos")
def model_eval_oos(req: OOSEvalRequest, db: Session = Depends(get_db)):
    """Out-of-sample оценка модели на хвосте датасета"""
    run = None
    if req.run_id is not None:
        run = db.query(ModelRun).filter(ModelRun.id == req.run_id).first()
        if not run:
            return {"status": "error", "detail": "run_id not found"}
    else:
        path = get_active_model_path(req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if path:
            run = db.query(ModelRun).filter(ModelRun.model_path == path).order_by(ModelRun.id.desc()).first()
        if run is None:
            run = (
                db.query(ModelRun)
                .filter(
                    ModelRun.exchange == req.exchange,
                    ModelRun.symbol == req.symbol,
                    ModelRun.timeframe == req.timeframe,
                    ModelRun.horizon_steps == req.horizon_steps,
                )
                .order_by(ModelRun.id.desc())
                .first()
            )
        if run is None:
            return {"status": "error", "detail": "no suitable run found"}
    try:
        return eval_model_oos(db, run, req.horizon_steps, tail_rows=int(req.tail_rows))
    except Exception as e:
        return {"status": "error", "detail": f"oos_eval: {e.__class__.__name__}: {e}"}


class PromoteIfBetterRequest(BaseModel):
    """Запрос на champion/challenger отбор"""

    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    min_auc_gain: float = 0.005
    prefer_sharpe: bool = True
    tail_rows: int = 1800
    dry_run: bool = False


@router.post("/champion/promote_if_better")
def model_promote_if_better(req: PromoteIfBetterRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Champion/Challenger отбор: промоутит лучшую модель (по Sharpe/AUC на OOS)"""
    return compare_and_maybe_promote(
        db,
        req.exchange,
        req.symbol,
        req.timeframe,
        req.horizon_steps,
        min_auc_gain=float(req.min_auc_gain),
        prefer_sharpe=bool(req.prefer_sharpe),
        tail_rows=int(req.tail_rows),
        dry_run=bool(req.dry_run),
    )

