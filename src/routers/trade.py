"""
Роутер для бумажной торговли (paper trading) и trade guard
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Literal, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok, err
from src.db import PaperPosition, PaperOrder, PaperTrade
from src.trade import (
    paper_close_pair,
    paper_get_positions,
    paper_get_equity,
    paper_get_orders,
)
from src.utils import _now_utc


router = APIRouter(prefix="/trade", tags=["Trade"])


# ===== Trade Guard (Kill Switch) =====


_TRADE_GUARD_PATH = Path("artifacts/state/trade_guard.json")
_TRADE_GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)


def _trade_guard_load() -> dict:
    """Загрузить состояние trade guard"""
    try:
        st = json.loads(_TRADE_GUARD_PATH.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    # env-переопределение: TRADE_MODE=locked|close_only|live
    env_mode = (os.getenv("TRADE_MODE") or "").strip().lower()
    if env_mode in ("locked", "close_only", "live"):
        st["mode"] = env_mode
    if "mode" not in st:
        st["mode"] = "live"
    return st


def _trade_guard_save(st: dict) -> None:
    """Сохранить состояние trade guard"""
    st = dict(st or {})
    st.setdefault("mode", "live")
    st["updated_at"] = _now_utc().replace(microsecond=0).isoformat()
    _TRADE_GUARD_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _trade_guard_enforce(kind: Literal["open", "reduce", "close", "admin"]) -> None:
    """Проверить trade guard и бросить ошибку если действие запрещено"""
    st = _trade_guard_load()
    mode = (st.get("mode") or "live").lower()
    allowed = {
        "live": {"open", "reduce", "close", "admin"},
        "close_only": {"reduce", "close"},
        "locked": set(),
    }.get(mode, {"open", "reduce", "close", "admin"})
    if kind not in allowed:
        reason = st.get("reason")
        err("trade.locked", {"mode": mode, "kind": kind, "reason": reason}, 423)


class TradeGuardSet(BaseModel):
    """Установка режима trade guard"""

    mode: Literal["live", "close_only", "locked"]
    reason: Optional[str] = None


@router.get("/guard")
def trade_guard_get(_=Depends(require_api_key)):
    """Получить текущий режим trade guard"""
    return _trade_guard_load()


@router.post("/guard")
def trade_guard_set(req: TradeGuardSet, _=Depends(require_api_key)):
    """Установить режим trade guard (kill switch)"""
    st = _trade_guard_load()
    st["mode"] = req.mode
    st["reason"] = (req.reason or "").strip() or None
    _trade_guard_save(st)
    return {"status": "ok", "state": _trade_guard_load()}


# ===== Paper Trading Endpoints =====


@router.get("/positions")
def trade_positions(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить открытые позиции (paper trading)"""
    merged = {}
    try:
        rows = db.query(PaperPosition).all()
        for pos in rows:
            key = (pos.exchange, pos.symbol)
            merged[key] = {
                "exchange": pos.exchange,
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "avg_price": float(pos.avg_price),
                "current_price": float(pos.current_price or 0),
                "created_at": pos.created_at,
                "updated_at": pos.updated_at,
            }
    except Exception:
        pass
    
    state_positions = paper_get_positions()
    for p in state_positions:
        key = (p.get("exchange"), p.get("symbol"))
        if key not in merged:
            merged[key] = p
    
    return ok(positions=list(merged.values()))


@router.get("/equity")
def trade_equity(_=Depends(require_api_key)):
    """Получить текущий equity (cash + positions)"""
    return ok(equity=paper_get_equity())


@router.get("/equity/history")
def trade_equity_history(limit: int = 500, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить историю equity"""
    from src.db import EquityPoint
    rows = db.query(EquityPoint).order_by(EquityPoint.ts.desc()).limit(limit).all()
    return ok(history=[{"ts": r.ts, "equity": r.equity} for r in reversed(rows)])


@router.get("/orders")
def trade_orders(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить список ордеров (paper trading)"""
    state_orders = paper_get_orders()
    db_orders = db.query(PaperOrder).order_by(PaperOrder.id.desc()).limit(100).all()
    return ok(orders=state_orders, db_orders=[
        {
            "id": o.id,
            "exchange": o.exchange,
            "symbol": o.symbol,
            "side": o.side,
            "qty": o.qty,
            "price": o.price,
            "status": o.status,
            "created_at": o.created_at,
        }
        for o in db_orders
    ])


class PaperCloseRequest(BaseModel):
    """Запрос на закрытие позиции"""
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"


@router.post("/paper/close")
def trade_paper_close(req: PaperCloseRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Закрыть позицию (paper trading)"""
    _trade_guard_enforce("close")
    result = paper_close_pair(db, req.exchange, req.symbol, req.timeframe)
    return ok(**result)


@router.post("/paper/order")
def trade_paper_order(order: dict, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Создать ордер (paper trading)"""
    _trade_guard_enforce("open")
    # TODO: реализация создания ордера
    return ok(message="Paper order created (stub)")


@router.post("/paper/reset")
def trade_paper_reset(_=Depends(require_api_key)):
    """Сброс paper trading state"""
    _trade_guard_enforce("admin")
    # TODO: реализация сброса state
    return ok(message="Paper trading reset (stub)")


@router.post("/paper/cash")
def trade_paper_cash(amount: float, _=Depends(require_api_key)):
    """Установить cash в paper trading"""
    _trade_guard_enforce("admin")
    # TODO: реализация установки cash
    return ok(cash=amount, message="Cash set (stub)")


@router.post("/paper/import_json_to_db")
def trade_paper_import_json_to_db(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Импорт paper trading state из JSON в БД"""
    # TODO: реализация импорта
    return ok(message="Import complete (stub)")


@router.post("/paper/export_db_to_json")
def trade_paper_export_db_to_json(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Экспорт paper trading state из БД в JSON"""
    # TODO: реализация экспорта
    return ok(message="Export complete (stub)")


# ===== Manual Trading Commands =====


def _last_close(db: Session, exchange: str, symbol: str, timeframe: str) -> Optional[float]:
    """Получить последнюю цену закрытия"""
    from src.db import Price
    r = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .first()
    )
    return float(r.close) if r else None


def _manual_buy_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: Optional[str] = None,
):
    """Ручная покупка (БД)"""
    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="buy",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=qty, price=price, fee=0.0)
    db.add(tr)

    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None:
        pos = PaperPosition(exchange=exchange, symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        db.add(pos)
        db.flush()

    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    new_qty = old_qty + float(qty)
    new_avg = (old_avg * old_qty + float(price) * float(qty)) / new_qty if new_qty != 0 else 0.0

    pos.qty = new_qty
    pos.avg_price = new_avg
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": pos.qty, "avg_price": pos.avg_price},
    }


def _manual_sell_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: Optional[str] = None,
):
    """Ручная продажа (БД)"""
    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None or float(pos.qty or 0.0) <= 0.0:
        return {"status": "error", "detail": "нет открытой позиции для sell"}
    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    if qty > old_qty + 1e-12:
        return {"status": "error", "detail": f"qty={qty} больше чем в позиции ({old_qty})"}

    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="sell",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=-float(qty), price=price, fee=0.0)
    db.add(tr)

    qty_to_close = float(qty)
    realized = (float(price) - old_avg) * qty_to_close
    pos.qty = old_qty - qty_to_close
    if pos.qty <= 1e-12:
        pos.qty = 0.0
        pos.avg_price = 0.0
    try:
        cur_rpnl = float(pos.realized_pnl or 0.0)
    except Exception:
        cur_rpnl = 0.0
    pos.realized_pnl = cur_rpnl + realized
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price), "realized_pnl": float(pos.realized_pnl)},
    }


def _manual_short_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: Optional[str] = None,
):
    """Ручное открытие шорта (БД)"""
    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="sell",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual short {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=-float(qty), price=price, fee=0.0)
    db.add(tr)

    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None:
        pos = PaperPosition(exchange=exchange, symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        db.add(pos)
        db.flush()

    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    add_abs = float(qty)

    new_qty = old_qty - add_abs
    base_abs = abs(old_qty)
    new_avg = (
        (old_avg * base_abs + float(price) * add_abs) / (base_abs + add_abs)
        if (base_abs + add_abs) > 0
        else float(price)
    )

    pos.qty = new_qty
    pos.avg_price = new_avg
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price)},
    }


def _manual_cover_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: Optional[str] = None,
):
    """Ручное покрытие шорта (БД)"""
    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None or float(pos.qty or 0.0) >= 0.0:
        return {"status": "error", "detail": "нет открытого шорта для cover"}

    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    if qty > abs(old_qty) + 1e-12:
        return {"status": "error", "detail": f"qty={qty} больше чем в шорте ({abs(old_qty)})"}

    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="buy",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual cover {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=float(qty), price=price, fee=0.0)
    db.add(tr)

    realized = (old_avg - float(price)) * float(qty)
    pos.qty = old_qty + float(qty)
    if pos.qty >= -1e-12 and pos.qty <= 1e-12:
        pos.qty = 0.0
        pos.avg_price = 0.0

    try:
        cur_rpnl = float(pos.realized_pnl or 0.0)
    except Exception:
        cur_rpnl = 0.0
    pos.realized_pnl = cur_rpnl + realized
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price), "realized_pnl": float(pos.realized_pnl)},
    }


# ===== Request/Response Models =====


class ManualBuyRequest(BaseModel):
    """Запрос на ручную покупку"""
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: Optional[float] = None
    note: Optional[str] = None


class ManualSellRequest(BaseModel):
    """Запрос на ручную продажу"""
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: Optional[float] = None
    note: Optional[str] = None


class ManualShortRequest(BaseModel):
    """Запрос на открытие шорта"""
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: Optional[float] = None
    note: Optional[str] = None


class ManualCoverRequest(BaseModel):
    """Запрос на покрытие шорта"""
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: Optional[float] = None
    note: Optional[str] = None


class ManualBuyResponse(BaseModel):
    """Ответ на ручную торговую команду"""
    status: str
    order: Optional[dict] = None
    trade: Optional[dict] = None
    position: Optional[dict] = None
    cash: Optional[float] = None
    detail: Optional[str] = None


# ===== Manual Trading Endpoints =====


@router.post("/manual/buy", response_model=ManualBuyResponse)
def trade_manual_buy(req: ManualBuyRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Ручная покупка"""
    _trade_guard_enforce("open")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return ManualBuyResponse(status="error", detail="нет последней цены и не задан price")

    # Совершаем покупку через БД
    try:
        res = _manual_buy_db(
            db,
            req.exchange,
            req.symbol,
            req.timeframe,
            float(req.qty),
            px,
            ts,
            note=req.note or "manual buy via API",
        )
        return ManualBuyResponse(status="ok", **res)
    except Exception as e:
        return ManualBuyResponse(status="error", detail=str(e))


@router.post("/manual/sell", response_model=ManualBuyResponse)
def trade_manual_sell(req: ManualSellRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Ручная продажа"""
    _trade_guard_enforce("reduce")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return ManualBuyResponse(status="error", detail="нет последней цены и не задан price")

    res = _manual_sell_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual sell via API"
    )
    if res.get("status") == "error":
        return ManualBuyResponse(status="error", detail=res.get("detail"))
    return ManualBuyResponse(status="ok", **res)


@router.post("/manual/short", response_model=ManualBuyResponse)
def trade_manual_short(req: ManualShortRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Открытие шорта"""
    _trade_guard_enforce("open")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return ManualBuyResponse(status="error", detail="нет последней цены и не задан price")

    res = _manual_short_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual short via API"
    )
    return ManualBuyResponse(status="ok", **res)


@router.post("/manual/cover", response_model=ManualBuyResponse)
def trade_manual_cover(req: ManualCoverRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Закрытие шорта"""
    _trade_guard_enforce("close")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return ManualBuyResponse(status="error", detail="нет последней цены и не задан price")

    res = _manual_cover_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual cover via API"
    )
    if res.get("status") == "error":
        return ManualBuyResponse(status="error", detail=res.get("detail"))
    return ManualBuyResponse(status="ok", **res)

