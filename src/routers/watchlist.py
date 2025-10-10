"""
Роутер для работы с watchlist (список отслеживаемых пар)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.dependencies import require_api_key
from src.watchlist import (
    list_watchlist,
    set_watchlist,
    add_pair as wl_add_pair,
    remove_pair as wl_remove_pair,
    discover_pairs,
)


router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


@router.get("")
def watchlist_get(_=Depends(require_api_key)):
    """Получить текущий watchlist"""
    return {"pairs": list_watchlist()}


class WatchlistSet(BaseModel):
    """Запрос на установку watchlist"""

    pairs: list[dict]


@router.post("")
def watchlist_set_api(req: WatchlistSet, _=Depends(require_api_key)):
    """Установить watchlist (перезаписать)"""
    set_watchlist(req.pairs or [])
    return {"status": "ok", "pairs": list_watchlist()}


class WatchlistItem(BaseModel):
    """Элемент watchlist"""

    exchange: str
    symbol: str
    timeframe: str
    limit: int = 500


@router.post("/add")
def watchlist_add(item: WatchlistItem, _=Depends(require_api_key)):
    """Добавить пару в watchlist"""
    wl_add_pair(item.exchange, item.symbol, item.timeframe, item.limit)
    return {"status": "ok", "pairs": list_watchlist()}


@router.post("/remove")
def watchlist_remove(item: WatchlistItem, _=Depends(require_api_key)):
    """Удалить пару из watchlist"""
    wl_remove_pair(item.exchange, item.symbol, item.timeframe)
    return {"status": "ok", "pairs": list_watchlist()}


class DiscoverParams(BaseModel):
    """Параметры для auto-discovery пар по объёму"""

    min_volume_usd: float = 2_000_000
    top_n_per_exchange: int = 25
    quotes: list[str] = ["USDT"]
    timeframes: list[str] = ["15m"]
    limit: int = 1000
    exchanges: list[str] = ["bybit"]


@router.post("/discover")
def watchlist_discover(req: DiscoverParams, _=Depends(require_api_key)):
    """Auto-discovery топ-ликвидных пар"""
    res = discover_pairs(
        min_volume_usd=req.min_volume_usd,
        top_n_per_exchange=req.top_n_per_exchange,
        quotes=tuple(req.quotes),
        timeframes=tuple(req.timeframes),
        limit=req.limit,
        exchanges=tuple(req.exchanges),
    )
    return {"status": "ok", **res}


@router.post("/purge_exchange")
def watchlist_purge_exchange(exchange: str, _=Depends(require_api_key)):
    """Удалить все пары с указанной биржи из watchlist"""
    exchange = exchange.lower().strip()
    cur = list_watchlist()
    kept = [p for p in cur if p.get("exchange", "").lower() != exchange]
    set_watchlist(kept)
    return {"status": "ok", "removed_exchange": exchange, "pairs": kept}

