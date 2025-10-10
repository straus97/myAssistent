"""
Роутер для экспорта журнала сделок
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok
from src.db import SignalEvent, SignalOutcome, PaperOrder
from src.trade import paper_get_orders


router = APIRouter(prefix="/journal", tags=["Journal"])


@router.get("/export")
def journal_export(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Экспорт журнала сделок в CSV"""
    rows = []

    # Сигналы
    sigs = db.query(SignalEvent).order_by(SignalEvent.bar_dt.asc(), SignalEvent.id.asc()).all()
    for s in sigs:
        try:
            note = json.loads(s.note or "{}")
        except Exception:
            note = {}
        rows.append(
            {
                "type": "signal",
                "dt": s.bar_dt.isoformat() if s.bar_dt else None,
                "exchange": s.exchange,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "prob_up": s.prob_up,
                "threshold": s.threshold,
                "prob_gap": note.get("prob_gap"),
                "signal": s.signal,
                "reasons": ",".join(note.get("reasons") or []),
                "model_path": s.model_path,
            }
        )

    # Ордеры из БД
    try:
        db_orders = db.query(PaperOrder).order_by(PaperOrder.id.asc()).all()
    except Exception:
        db_orders = []
    for o in db_orders:
        rows.append(
            {
                "type": "order_db",
                "dt": (o.created_at.isoformat() if o.created_at else None),
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": None,
                "side": o.side,
                "qty": float(o.qty or 0.0),
                "price": float(o.price or 0.0),
                "fee": float(o.fee or 0.0),
                "status": o.status,
                "note": o.note,
            }
        )

    # Ордеры из JSON
    try:
        for j in paper_get_orders():
            rows.append(
                {
                    "type": "order_json",
                    "dt": j.get("ts"),
                    "exchange": j.get("exchange"),
                    "symbol": j.get("symbol"),
                    "timeframe": j.get("timeframe"),
                    "side": j.get("side"),
                    "qty": float(j.get("qty", 0.0)),
                    "price": float(j.get("price", 0.0)),
                    "fee": None,
                    "status": "filled",
                    "note": None,
                    "pnl": j.get("pnl"),
                }
            )
    except Exception:
        pass

    # Исходы сигналов
    outs = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.asc())
        .all()
    )
    for o, e in outs:
        rows.append(
            {
                "type": "outcome",
                "dt": (o.resolved_at.isoformat() if o.resolved_at else None),
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "max_drawdown": o.max_drawdown,
                "signal_dt": (e.bar_dt.isoformat() if e and e.bar_dt else None),
                "signal_id": e.id if e else None,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["dt"], kind="stable", na_position="last")
    Path("artifacts").mkdir(exist_ok=True)
    out_path = Path("artifacts") / "journal.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return ok(rows=int(len(df)), path=str(out_path.resolve()))


@router.get("/export_pretty")
def journal_export_pretty(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Экспорт журнала сделок в красиво отформатированный Excel"""
    # Сигналы
    signals = db.query(SignalEvent).order_by(SignalEvent.bar_dt.asc(), SignalEvent.id.asc()).all()
    rows_sig = []
    for s in signals:
        try:
            note = json.loads(s.note or "{}")
        except Exception:
            note = {}
        rows_sig.append(
            {
                "dt": s.bar_dt,
                "exchange": s.exchange,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "prob_up": s.prob_up,
                "threshold": s.threshold,
                "prob_gap": note.get("prob_gap"),
                "signal": s.signal,
                "reasons": "; ".join(note.get("reasons") or []),
                "model_path": s.model_path,
            }
        )
    df_sig = pd.DataFrame(rows_sig)

    # Ордеры из БД
    try:
        db_orders = db.query(PaperOrder).order_by(PaperOrder.id.asc()).all()
    except Exception:
        db_orders = []
    df_od = pd.DataFrame(
        [
            {
                "dt": o.created_at,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "side": o.side,
                "qty": float(o.qty or 0.0),
                "price": float(o.price or 0.0),
                "fee": float(o.fee or 0.0),
                "status": o.status,
                "note": o.note,
            }
            for o in db_orders
        ]
    )

    # Ордеры из JSON
    j_orders = []
    try:
        for j in paper_get_orders():
            j_orders.append(
                {
                    "dt": j.get("ts"),
                    "exchange": j.get("exchange"),
                    "symbol": j.get("symbol"),
                    "timeframe": j.get("timeframe"),
                    "side": j.get("side"),
                    "qty": float(j.get("qty", 0.0)),
                    "price": float(j.get("price", 0.0)),
                    "pnl": j.get("pnl"),
                }
            )
    except Exception:
        pass
    df_oj = pd.DataFrame(j_orders)

    # Исходы сигналов
    outs = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.asc())
        .all()
    )
    rows_out = []
    for o, e in outs:
        rows_out.append(
            {
                "resolved_at": o.resolved_at,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "max_drawdown": o.max_drawdown,
                "signal_dt": (e.bar_dt if e else None),
                "signal_id": (e.id if e else None),
            }
        )
    df_out = pd.DataFrame(rows_out)

    # Создание Excel с форматированием
    Path("artifacts").mkdir(exist_ok=True)
    xlsx_path = Path("artifacts") / "journal.xlsx"

    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm") as w:

        def _write(df, name):
            if df is None or df.empty:
                pd.DataFrame({"info": ["no data"]}).to_excel(w, index=False, sheet_name=name)
                return
            df.to_excel(w, index=False, sheet_name=name)
            ws = w.sheets[name]
            ws.freeze_panes(1, 0)
            for i, col in enumerate(df.columns):
                width = max(12, min(48, int(df[col].astype(str).str.len().quantile(0.95)) + 2))
                ws.set_column(i, i, width)

        _write(df_sig, "signals")
        _write(df_od, "orders_db")
        _write(df_oj, "orders_json")
        _write(df_out, "outcomes")

    return ok(path=str(xlsx_path.resolve()))
