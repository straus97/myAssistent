"""
Роутер для бумажной торговли (paper trading) и trade guard
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Literal, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok, err
from src.db import PaperPosition, PaperOrder, PaperTrade
from src.trade import (
    paper_open_buy_auto,
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
def trade_equity(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить текущий equity (cash + positions)"""
    return ok(equity=paper_get_equity(db))


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


class ManualBuyResponse(BaseModel):
    """Ответ на ручную торговую команду"""
    status: str
    message: str
    data: Optional[Any] = None


@router.post("/manual/buy", response_model=ManualBuyResponse)
def trade_manual_buy(cmd: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Ручная покупка через команду вида '/buy BTC/USDT 0.1'"""
    _trade_guard_enforce("open")
    # TODO: реализация ручной покупки через cmd_parser
    from src.cmd_parser import _parse_trade_cmd
    parsed = _parse_trade_cmd(cmd)
    return ManualBuyResponse(status="ok", message=f"Buy order created (stub): {parsed}")


@router.post("/manual/sell", response_model=ManualBuyResponse)
def trade_manual_sell(cmd: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Ручная продажа через команду вида '/sell BTC/USDT 0.1'"""
    _trade_guard_enforce("reduce")
    # TODO: реализация ручной продажи
    from src.cmd_parser import _parse_trade_cmd
    parsed = _parse_trade_cmd(cmd)
    return ManualBuyResponse(status="ok", message=f"Sell order created (stub): {parsed}")


@router.post("/manual/short", response_model=ManualBuyResponse)
def trade_manual_short(cmd: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Открытие шорта"""
    _trade_guard_enforce("open")
    # TODO: реализация шорта
    return ManualBuyResponse(status="ok", message="Short order created (stub)")


@router.post("/manual/cover", response_model=ManualBuyResponse)
def trade_manual_cover(cmd: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Закрытие шорта"""
    _trade_guard_enforce("reduce")
    # TODO: реализация закрытия шорта
    return ManualBuyResponse(status="ok", message="Cover order created (stub)")


# NOTE: Этот роутер содержит упрощённые версии всех trade эндпоинтов.
# Для полной реализации нужно перенести весь код из main.py (строки 172-3500).
# Основные части уже реализованы (trade guard, positions, equity, close).
# Остальные эндпоинты требуют доработки при следующей итерации декомпозиции.

