from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Any
import json

CFG_DIR = Path("artifacts") / "config"
CFG_DIR.mkdir(parents=True, exist_ok=True)
WL_PATH = CFG_DIR / "watchlist.json"

DEFAULT: List[Dict[str, Any]] = [
    {"exchange": "bybit", "symbol": "BTC/USDT", "timeframe": "1h", "limit": 500},
    {"exchange": "bybit", "symbol": "ETH/USDT", "timeframe": "15m", "limit": 500},
    {"exchange": "bybit", "symbol": "SOL/USDT", "timeframe": "1h", "limit": 500},
    {"exchange": "bybit", "symbol": "BNB/USDT", "timeframe": "1h", "limit": 500},
]


def _ensure_file() -> None:
    if not WL_PATH.exists():
        WL_PATH.write_text(json.dumps(DEFAULT, ensure_ascii=False, indent=2), encoding="utf-8")


def list_watchlist() -> List[Dict[str, Any]]:
    _ensure_file()
    try:
        data = json.loads(WL_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return DEFAULT.copy()


def set_watchlist(pairs: List[Dict[str, Any]]) -> None:
    WL_PATH.write_text(json.dumps(pairs or [], ensure_ascii=False, indent=2), encoding="utf-8")


def add_pair(exchange: str, symbol: str, timeframe: str, limit: int = 500) -> None:
    cur = list_watchlist()
    obj = {"exchange": exchange.lower(), "symbol": symbol.upper(), "timeframe": timeframe.lower(), "limit": int(limit)}
    if obj not in cur:
        cur.append(obj)
        set_watchlist(cur)


def remove_pair(exchange: str, symbol: str, timeframe: str) -> None:
    cur = list_watchlist()
    ex, sym, tf = exchange.lower(), symbol.upper(), timeframe.lower()
    new = [p for p in cur if not (p["exchange"] == ex and p["symbol"] == sym and p["timeframe"] == tf)]
    set_watchlist(new)


def pairs_for_jobs() -> List[Tuple[str, str, str, int]]:
    cur = list_watchlist()
    if not cur:
        return [(p["exchange"], p["symbol"], p["timeframe"], p.get("limit", 500)) for p in DEFAULT]
    return [(p["exchange"], p["symbol"], p["timeframe"], p.get("limit", 500)) for p in cur]


def discover_pairs(
    min_volume_usd: float = 2_000_000,
    top_n_per_exchange: int = 25,
    quotes: tuple[str, ...] = ("USDT",),
    timeframes: tuple[str, ...] = ("15m",),
    limit: int = 1000,
    exchanges: tuple[str, ...] = ("binance", "bybit"),
) -> Dict[str, Any]:
    """
    Простой «скаут»: пытаемся расширить watchlist по ликвидности.
    Если нет доступа к рынку — оставляем лист без изменений.
    Возвращает {"added":[...], "total_watchlist": N}
    """
    added: List[Dict[str, Any]] = []
    try:
        import ccxt  # type: ignore
    except Exception:
        # Без ccxt — просто возвращаем текущее состояние
        return {"added": [], "total_watchlist": len(list_watchlist())}

    cur = list_watchlist()
    cur_set = {(p["exchange"], p["symbol"]) for p in cur}

    for ex in exchanges:
        try:
            ex_obj = getattr(ccxt, ex)()
            ex_obj.load_markets()
            # получаем tickers с объёмом за 24ч
            tickers = ex_obj.fetch_tickers()
        except Exception:
            continue

        # отберём пары по quote и объёму
        ranked: List[tuple[str, float]] = []
        for sym, t in tickers.items():
            try:
                q = sym.split("/")[-1]
                if q not in quotes:
                    continue
                # приводим к USD — для USDT ~1:1 достаточно
                vol_usd = float(t.get("quoteVolume") or 0.0)
                if vol_usd >= min_volume_usd:
                    ranked.append((sym, vol_usd))
            except Exception:
                continue
        ranked.sort(key=lambda x: x[1], reverse=True)
        for sym, _ in ranked[:top_n_per_exchange]:
            if (ex, sym) in cur_set:
                continue
            for tf in timeframes:
                obj = {"exchange": ex, "symbol": sym, "timeframe": tf, "limit": limit}
                cur.append(obj)
                added.append(obj)
                cur_set.add((ex, sym))

    if added:
        set_watchlist(cur)
    return {"added": added, "total_watchlist": len(cur)}
