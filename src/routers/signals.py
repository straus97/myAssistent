"""
Роутер для генерации торговых сигналов
"""
from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import pandas as pd

from src.dependencies import get_db, require_api_key
from src.db import SignalEvent, SignalOutcome, Price
from src.features import build_dataset
from src.modeling import load_latest_model, load_model_from_path
from src.model_registry import load_model_for
from src.risk import load_policy, evaluate_filters
from src.notify import maybe_send_signal_notification
from src.utils import _volatility_guard


router = APIRouter(prefix="/signals", tags=["Signals"])


# ===== Вспомогательные функции =====


def _last_close(db: Session, exchange: str, symbol: str, timeframe: str) -> Optional[float]:
    """Получить последнюю цену закрытия"""
    r = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .first()
    )
    return float(r.close) if r else None


def _compute_signal_for_last_bar(db: Session, ex: str, sym: str, tf: str, hz: int, model_path: Optional[str]):
    """Вычисляет сигнал для последнего бара датасета (без сохранения в БД)"""
    df, _ = build_dataset(db, ex, sym, tf, hz)
    if df.empty:
        return {"status": "error", "detail": "Данных нет."}

    row = df.iloc[-1]
    bar_dt = row.name.to_pydatetime()
    close = float(row["close"])

    if model_path:
        model, feature_cols, threshold, model_path = load_model_from_path(model_path)
    else:
        try:
            model, feature_cols, threshold, model_path = load_model_for(db, ex, sym, tf, hz)
        except FileNotFoundError:
            model, feature_cols, threshold, model_path = load_latest_model()

    missing = [c for c in feature_cols if c not in row.index]
    if missing:
        return {"status": "error", "detail": f"В датасете отсутствуют признаки: {missing[:6]} ..."}

    X = row[feature_cols].values.reshape(1, -1)
    proba = float(model.predict_proba(X)[0, 1])
    base_signal = "buy" if proba > threshold else "flat"
    delta = proba - threshold

    policy = load_policy()
    min_gap = float((policy or {}).get("min_prob_gap", 0.02))
    last_evt = (
        db.query(SignalEvent)
        .filter(SignalEvent.exchange == ex, SignalEvent.symbol == sym, SignalEvent.timeframe == tf)
        .order_by(SignalEvent.bar_dt.desc())
        .first()
    )
    last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
    allow, reasons, metrics = evaluate_filters(row, df, policy, tf, last_bar_ts)
    allow_vol, r2, m2 = _volatility_guard(row, df, tf, policy)
    allow = allow and allow_vol
    reasons += r2
    metrics.update(m2)

    if base_signal == "buy" and delta < min_gap:
        reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
        allow = False

    final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

    return {
        "status": "ok",
        "exchange": ex,
        "symbol": sym,
        "timeframe": tf,
        "bar_dt": bar_dt,
        "close": close,
        "prob_up": proba,
        "threshold": threshold,
        "prob_gap": delta,
        "signal": final_signal,
        "reasons": reasons,
        "metrics": metrics,
        "model_path": model_path,
    }


# ===== Эндпоинты =====


class SignalRequest(BaseModel):
    """Запрос на генерацию сигнала"""

    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 12
    model_path: Optional[str] = Field(default=None)


@router.post("/latest")
def signal_latest(req: SignalRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Генерация сигнала для последнего бара с сохранением в БД и отправкой в Telegram"""
    try:
        df, _ = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if df.empty:
            return {"status": "error", "detail": "Данных нет. Сначала загрузите цены/новости."}

        row = df.iloc[-1]
        bar_dt = row.name.to_pydatetime()
        close = float(row["close"])

        if req.model_path:
            model, feature_cols, threshold, model_path = load_model_from_path(req.model_path)
        else:
            try:
                model, feature_cols, threshold, model_path = load_model_for(
                    db, req.exchange, req.symbol, req.timeframe, req.horizon_steps
                )
            except FileNotFoundError:
                model, feature_cols, threshold, model_path = load_latest_model()

        missing = [c for c in feature_cols if c not in row.index]
        if missing:
            return {"status": "error", "detail": f"В датасете отсутствуют признаки: {missing[:6]} ..."}
        X = row[feature_cols].values.reshape(1, -1)
        proba = float(model.predict_proba(X)[0, 1])
        base_signal = "buy" if proba > threshold else "flat"
        delta = proba - threshold

        policy = load_policy()
        last_evt = (
            db.query(SignalEvent)
            .filter(
                SignalEvent.exchange == req.exchange,
                SignalEvent.symbol == req.symbol,
                SignalEvent.timeframe == req.timeframe,
            )
            .order_by(SignalEvent.bar_dt.desc())
            .first()
        )
        last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
        allow, reasons, metrics = evaluate_filters(row, df, policy, req.timeframe, last_bar_ts)
        allow_vol, r2, m2 = _volatility_guard(row, df, req.timeframe, policy)
        allow = allow and allow_vol
        reasons += r2
        metrics.update(m2)

        min_gap = float((policy or {}).get("min_prob_gap", 0.02))
        if base_signal == "buy" and delta < min_gap:
            reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
            allow = False

        final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

        evt = SignalEvent(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            horizon_steps=req.horizon_steps,
            bar_dt=bar_dt,
            close=close,
            prob_up=proba,
            threshold=threshold,
            signal=final_signal,
            model_path=model_path,
            note=json.dumps(
                {
                    "base_signal": base_signal,
                    "prob": proba,
                    "threshold": threshold,
                    "prob_gap": delta,
                    "policy": policy,
                    "metrics": metrics,
                    "reasons": reasons,
                },
                ensure_ascii=False,
            ),
        )
        db.add(evt)
        try:
            db.commit()
            db.refresh(evt)
        except Exception:
            db.rollback()

        if evt.id:
            maybe_send_signal_notification(
                final_signal,
                proba,
                threshold,
                delta,
                reasons,
                model_path,
                req.exchange,
                req.symbol,
                req.timeframe,
                bar_dt,
                close,
                source="endpoint",
            )

        return {
            "status": "ok",
            "exchange": req.exchange,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "bar_dt": bar_dt,
            "close": close,
            "prob_up": proba,
            "threshold": threshold,
            "prob_gap": delta,
            "filters_metrics": metrics,
            "reasons": reasons,
            "signal": final_signal,
            "model_path": model_path,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/preview")
def signal_preview(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    horizon_steps: int = 12,
    model_path: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Предпросмотр сигнала без сохранения в БД"""
    return _compute_signal_for_last_bar(db, exchange, symbol, timeframe, horizon_steps, model_path)


@router.get("/recent")
def signals_recent(limit: int = 50, db: Session = Depends(get_db)):
    """Получить последние сгенерированные сигналы"""
    rows = db.query(SignalEvent).order_by(SignalEvent.bar_dt.desc(), SignalEvent.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        try:
            note = json.loads(r.note or "{}")
        except Exception:
            note = {}
        out.append(
            {
                "created_at": r.created_at,
                "bar_dt": r.bar_dt,
                "exchange": r.exchange,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "horizon_steps": r.horizon_steps,
                "close": r.close,
                "prob_up": r.prob_up,
                "threshold": r.threshold,
                "signal": r.signal,
                "model_path": r.model_path,
                "prob_gap": note.get("prob_gap"),
                "base_signal": note.get("base_signal"),
                "reasons": note.get("reasons"),
            }
        )
    return out


@router.get("/outcomes/recent")
def outcomes_recent(limit: int = 50, db: Session = Depends(get_db)):
    """Получить последние исходы сигналов"""
    rows = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for o, e in rows:
        out.append(
            {
                "id": o.id,
                "event_id": e.id,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "bar_dt": o.bar_dt,
                "signal": e.signal,
                "entry_close": o.entry_close,
                "exit_close": o.exit_close,
                "ret_h": o.ret_h,
                "mdd": o.mdd,
                "correct": o.correct,
            }
        )
    return out

