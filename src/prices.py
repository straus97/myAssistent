from __future__ import annotations
import math
from typing import List, Tuple
import requests
from sqlalchemy.orm import Session
from src.db import Price

# --- таймфреймы и утилиты ---
_BINANCE_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


def _binance_symbol(symbol: str) -> str:
    return symbol.replace("/", "")


def _bybit_interval(tf: str) -> str:
    # Bybit v5: для spot/linear разрешены минуты как "1","3","5","15","60","240", "D"
    tf = tf.lower()
    if tf.endswith("m"):
        return str(int(tf[:-1]))
    if tf.endswith("h"):
        return str(int(tf[:-1]) * 60)
    if tf.endswith("d"):
        return "D"
    return "60"


def _ms(ts: float | int) -> int:
    if ts > 1e12:
        return int(ts)
    return int(ts * 1000)


def _insert_prices(
    db: Session, exchange: str, symbol: str, timeframe: str, rows: List[Tuple[int, float, float, float, float, float]]
) -> int:
    """rows: list of (ts_ms, o, h, l, c, v)"""
    added = 0
    batch = 0
    for ts, o, h, low, c, v in rows:
        db.add(
            Price(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                ts=int(ts),
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=float(v),
            )
        )
        added += 1
        batch += 1
        if batch >= 500:
            try:
                db.commit()
            except Exception as e:
                print(f"[ERROR] Failed to commit batch: {e}")
                import traceback
                traceback.print_exc()
                db.rollback()
            batch = 0
    if batch:
        try:
            db.commit()
        except Exception as e:
            print(f"[ERROR] Failed to commit final batch: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
    return added


# --- загрузчики по биржам ---
def _fetch_binance(symbol: str, timeframe: str, limit: int) -> List[Tuple[int, float, float, float, float, float]]:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": _binance_symbol(symbol), "interval": _BINANCE_TF.get(timeframe, "15m"), "limit": int(limit)}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    out = []
    for row in data:
        ts = int(row[0])  # open time (ms)
        o, h, low, c, v = map(float, [row[1], row[2], row[3], row[4], row[5]])
        out.append((ts, o, h, low, c, v))
    return out


def _fetch_bybit(symbol: str, timeframe: str, limit: int) -> List[Tuple[int, float, float, float, float, float]]:
    # Spot категория подходит для BTCUSDT/ETHUSDT и большей части watchlist
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "spot",
        "symbol": _binance_symbol(symbol),
        "interval": _bybit_interval(timeframe),
        "limit": int(limit),
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    result = data.get("result") or {}
    lst = result.get("list") or []
    # Bybit отдаёт строки: [start, open, high, low, close, volume, turnover]
    out = []
    for row in reversed(lst):  # от старых к новым
        ts = _ms(int(row[0]))
        o, h, low, c, v = map(float, [row[1], row[2], row[3], row[4], row[5]])
        out.append((ts, o, h, low, c, v))
    return out[-limit:]


# --- публичное API ---
def fetch_and_store_prices(db: Session, exchange: str, symbol: str, timeframe: str, limit: int = 500) -> int:
    """
    Грузит OHLCV и сохраняет в БД.
    Поддержка: binance, bybit (spot). Возвращает число добавленных строк.
    """
    exchange = (exchange or "").lower()
    symbol = symbol.upper()
    timeframe = timeframe.lower()
    limit = int(limit)

    if exchange == "binance":
        rows = _fetch_binance(symbol, timeframe, limit)
    elif exchange == "bybit":
        rows = _fetch_bybit(symbol, timeframe, limit)
    else:
        raise ValueError(f"unsupported exchange '{exchange}'")

    # отфильтруем NaN/пустые
    rows = [r for r in rows if all(math.isfinite(x) for x in r)]
    return _insert_prices(db, exchange, symbol, timeframe, rows)


def fetch_ohlcv(
    exchange: str,
    symbol: str,
    timeframe: str,
    since: str | None = None,
    limit: int = 500,
) -> "pd.DataFrame":
    """
    Загрузка OHLCV данных с биржи (БЕЗ сохранения в БД).
    
    Args:
        exchange: Биржа (binance, bybit)
        symbol: Символ (BTC/USDT)
        timeframe: Таймфрейм (1h, 4h, 1d)
        since: Дата начала (YYYY-MM-DD), опционально
        limit: Количество свечей
    
    Returns:
        DataFrame с колонками: timestamp, open, high, low, close, volume
    """
    import pandas as pd
    from datetime import datetime
    
    exchange = (exchange or "").lower()
    symbol = symbol.upper()
    timeframe = timeframe.lower()
    limit = int(limit)
    
    if exchange == "binance":
        rows = _fetch_binance(symbol, timeframe, limit)
    elif exchange == "bybit":
        rows = _fetch_bybit(symbol, timeframe, limit)
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")
    
    # Фильтрация NaN
    rows = [r for r in rows if all(math.isfinite(x) for x in r)]
    
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    
    # Конвертация в DataFrame
    df = pd.DataFrame(rows, columns=["ts_ms", "open", "high", "low", "close", "volume"])
    
    # Timestamp в datetime
    df["timestamp"] = pd.to_datetime(df["ts_ms"], unit="ms")
    df = df.drop(columns=["ts_ms"])
    
    # Фильтрация по дате
    if since:
        since_dt = pd.to_datetime(since)
        df = df[df["timestamp"] >= since_dt]
    
    # Сортировка по времени
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    return df