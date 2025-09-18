# src/prices.py
from typing import List
import ccxt
from sqlalchemy.orm import Session
from .db import Price

def _get_exchange(name: str):
    name = name.lower()
    if not hasattr(ccxt, name):
        raise ValueError(f"Unsupported exchange: {name}")
    ex = getattr(ccxt, name)({'enableRateLimit': True})
    return ex

def fetch_and_store_prices(db: Session, exchange: str, symbol: str, timeframe: str, limit: int = 500) -> int:
    ex = _get_exchange(exchange)
    ex.load_markets()
    if symbol not in ex.markets:
        raise ValueError(f"Symbol {symbol} not found on {exchange}. Example symbols: {list(ex.markets.keys())[:5]}")
    if timeframe not in ex.timeframes:
        raise ValueError(f"Timeframe {timeframe} not supported by {exchange}. Options: {list(ex.timeframes.keys())}")

    ohlcv: List[List[float]] = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    added = 0
    for ts, o, h, l, c, v in ohlcv:
        exists = (
            db.query(Price)
            .filter(Price.exchange==exchange, Price.symbol==symbol, Price.timeframe==timeframe, Price.ts==ts)
            .first()
        )
        if exists:
            continue
        row = Price(
            exchange=exchange, symbol=symbol, timeframe=timeframe, ts=ts,
            open=o, high=h, low=l, close=c, volume=v
        )
        db.add(row)
        try:
            db.commit()
            added += 1
        except Exception:
            db.rollback()
    return added
