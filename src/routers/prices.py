"""
Роутер для работы с ценами (OHLCV данные из Binance/Bybit)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok, ok_data, err
from src.db import Price
from src.prices import fetch_and_store_prices


router = APIRouter(prefix="/prices", tags=["Prices"])


class PriceFetchRequest(BaseModel):
    """Запрос на загрузку OHLCV данных"""

    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    limit: int = 500


@router.post("/fetch")
def prices_fetch(req: PriceFetchRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Загрузка OHLCV данных с биржи"""
    try:
        added = fetch_and_store_prices(db, req.exchange, req.symbol, req.timeframe, req.limit)
        return ok(added=added)
    except Exception as e:
        err("prices.fetch_failed", str(e), 500)


@router.get("/latest")
def prices_latest(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    """Получить последние OHLCV свечи"""
    rows = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return ok_data(
        [{"ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume} for r in rows]
    )

