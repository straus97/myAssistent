from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from src.risk import load_policy
from tempfile import NamedTemporaryFile

STATE_PATH = Path("artifacts") / "paper_state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_STATE = {
    "cash": 10_000.0,
    "positions": [],  # [{exchange,symbol,timeframe,qty,avg_price}]
    "orders": [],  # [{ts,exchange,symbol,timeframe,side,qty,price,pnl?}]
}


# --- auto sizing helpers ---
def _auto_sizing_defaults():
    # дефолты, если в policy ключей нет
    return {
        "equity_virtual": 100.0,  # виртуальный капитал в USDT для расчёта
        "buy_fraction": {"dead": 0.00, "normal": 0.05, "hot": 0.03},
        "min_order_usdt": 1.0,
        "max_order_usdt": 10.0,
        "qty_precision": 6,  # округление количества
    }


def _get_auto_sizing_cfg(policy: dict) -> dict:
    p = (policy or {}).get("auto_sizing") or {}
    d = _auto_sizing_defaults()
    return {
        "equity_virtual": float(p.get("equity_virtual", d["equity_virtual"])),
        "buy_fraction": {
            "dead": float((p.get("buy_fraction") or {}).get("dead", d["buy_fraction"]["dead"])),
            "normal": float((p.get("buy_fraction") or {}).get("normal", d["buy_fraction"]["normal"])),
            "hot": float((p.get("buy_fraction") or {}).get("hot", d["buy_fraction"]["hot"])),
        },
        "min_order_usdt": float(p.get("min_order_usdt", d["min_order_usdt"])),
        "max_order_usdt": float(p.get("max_order_usdt", d["max_order_usdt"])),
        "qty_precision": int(p.get("qty_precision", d["qty_precision"])),
    }


def _calc_auto_qty(
    exchange: str, symbol: str, timeframe: str, price: float, vol_state: str | None, policy: dict
) -> tuple[float, float]:
    """
    +    Возвращает (qty, usd_alloc).
    +    Режимы:
    +      1) Если есть policy.sizing — считаем от РЕАЛЬНОГО equity с учётом волатильности.
    +      2) Иначе — старый режим: от виртуального equity (policy.auto_sizing).
    """
    vs = (vol_state or "normal").lower()
    sizing = (policy or {}).get("sizing") or None
    if sizing:
        try:
            equity = float(paper_get_equity().get("equity", 0.0))
        except Exception:
            equity = 0.0
        base_frac = float(sizing.get("base_fraction", 0.10))
        by_vol = sizing.get("by_vol") or {}
        frac = float(by_vol.get(vs, by_vol.get("normal", base_frac)))
        min_order = float(sizing.get("min_order_usd", 0.0))
        qprec = int(((policy.get("auto_sizing") or {}).get("qty_precision", 6)))
        target_usdt = max(min_order, equity * max(0.0, frac))
        qty = 0.0 if price <= 0 else (target_usdt / float(price))
        qty = float(round(qty, max(0, qprec)))
        if qty <= 0.0 and target_usdt > 0:
            qty = float(round(min_order / max(price, 1e-9), max(0, qprec)))
        return qty, target_usdt

    # --- Fallback: старый виртуальный режим ---
    cfg = _get_auto_sizing_cfg(policy)
    frac = cfg["buy_fraction"].get(vs, cfg["buy_fraction"]["normal"])
    target_usdt = cfg["equity_virtual"] * frac
    target_usdt = max(cfg["min_order_usdt"], min(cfg["max_order_usdt"], target_usdt))
    qty = 0.0 if price <= 0 else (target_usdt / float(price))
    qprec = max(0, int(cfg["qty_precision"]))
    qty = float(round(qty, qprec))
    if qty <= 0.0:
        qty = float(round(cfg["min_order_usdt"] / max(price, 1e-9), qprec))
    return qty, target_usdt


# --- state helpers ---
def _load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return {**DEFAULT_STATE, **json.loads(STATE_PATH.read_text(encoding="utf-8"))}
        except Exception:
            pass
    STATE_PATH.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_STATE.copy()


def _save_state(st: Dict[str, Any]) -> None:
    data = json.dumps(st, ensure_ascii=False, indent=2)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=str(STATE_PATH.parent), encoding="utf-8") as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(STATE_PATH)


def paper_get_positions() -> List[Dict[str, Any]]:
    st = _load_state()
    return list(st.get("positions") or [])


def paper_get_orders() -> List[Dict[str, Any]]:
    st = _load_state()
    return list(st.get("orders") or [])


def _count_open_positions(st: Dict[str, Any]) -> int:
    try:
        return sum(1 for p in (st.get("positions") or []) if float(p.get("qty", 0.0)) > 0.0)
    except Exception:
        return 0


def _find_pos(st, exchange, symbol, timeframe=None):
    for p in st["positions"]:
        if (
            p["exchange"] == exchange
            and p["symbol"] == symbol
            and (timeframe is None or p.get("timeframe") == timeframe)
        ):
            return p
    return None


def paper_get_equity(mark_to_market: Dict[str, float] | None = None) -> Dict[str, Any]:
    st = _load_state()
    cash = float(st.get("cash", 0.0))
    mtm = 0.0
    for p in st["positions"]:
        key = f"{p['exchange']}:{p['symbol']}:{p.get('timeframe','15m')}"
        price = (mark_to_market or {}).get(key) or p.get("avg_price", 0.0)
        mtm += float(p.get("qty", 0.0)) * float(price or 0.0)
    equity = cash + mtm
    return {"cash": cash, "positions_value": mtm, "equity": equity}


def paper_has_open_position(exchange, symbol, timeframe=None):
    st = _load_state()
    p = _find_pos(st, exchange, symbol)  # намеренно без TF
    return bool(p and float(p.get("qty", 0.0)) > 0.0)


# --- manual ops (бот-команды используют их напрямую) ---
def paper_open_buy_manual(
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float | None,
    price: float,
    ts_iso: str,
    note: str | None = None,
    vol_state: str | None = None,
) -> Dict[str, Any]:
    # --- auto size, если qty не задано или <= 0 ---
    if qty is None or qty <= 0.0:
        try:
            policy = load_policy()
        except Exception:
            policy = {}
        qty, _usd = _calc_auto_qty(exchange, symbol, timeframe, float(price), vol_state or "normal", policy)

    st = _load_state()
    cash = float(st.get("cash", 0.0))
    cost = float(qty) * float(price)
    st["cash"] = cash - cost

    pos = _find_pos(st, exchange, symbol)
    if pos is None:
        pos = {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "qty": 0.0,
            "avg_price": 0.0,
            "opened_at": ts_iso
        }
        st["positions"].append(pos)
    old_qty = float(pos["qty"])
    old_avg = float(pos["avg_price"])
    new_qty = old_qty + float(qty)
    new_avg = (old_qty * old_avg + float(qty) * float(price)) / new_qty if new_qty > 0 else 0.0
    pos["qty"] = new_qty
    pos["avg_price"] = new_avg

    od = {
        "ts": ts_iso,
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "side": "buy",
        "qty": float(qty),
        "price": float(price),
        "note": note,
    }
    st["orders"].append(od)
    _save_state(st)
    return {"order": od, "position": pos, "cash": st["cash"]}


def paper_open_sell_manual(
    exchange: str, symbol: str, timeframe: str, qty: float, price: float, ts_iso: str, note: str | None = None
) -> Dict[str, Any]:
    st = _load_state()
    pos = _find_pos(st, exchange, symbol)
    if pos is None or float(pos.get("qty", 0.0)) <= 0.0:
        return {"status": "error", "detail": "no open position"}

    sell_qty = min(float(qty), float(pos["qty"]))
    pnl = (float(price) - float(pos["avg_price"])) * sell_qty

    pos["qty"] = float(pos["qty"]) - sell_qty
    if pos["qty"] <= 1e-12:
        pos["qty"] = 0.0
        pos["avg_price"] = 0.0

    st["cash"] = float(st.get("cash", 0.0)) + sell_qty * float(price)

    od = {
        "ts": ts_iso,
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "side": "sell",
        "qty": sell_qty,
        "price": float(price),
        "pnl": pnl,
        "note": note,
    }
    st["orders"].append(od)
    _save_state(st)
    return {"order": od, "position": pos, "cash": st["cash"], "pnl": pnl}


# --- auto ops (используются планировщиком/эндпоинтами) ---
def paper_open_buy_auto(
    exchange: str,
    symbol: str,
    timeframe: str,
    price: float,
    ts_iso: str,
    *,
    vol_state: str = "normal",
    qty: float | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Открывает лот автоматически на долю капитала из risk.policy.auto.buy_fraction.
    Можно передать qty (чтобы задать количество явно) и/или vol_state ('dead'|'normal'|'hot').
    Прочие ключи из kwargs игнорируются (например, last_price), чтобы не ломать существующий код.
    """
    pol = load_policy()
    vol_state = (vol_state or "normal").lower()

    # кандидатное qty и $-аллокация по policy.sizing (или fallback к virtual)
    if not qty or qty <= 0.0:
        qty_calc, usd_alloc = _calc_auto_qty(exchange, symbol, timeframe, float(price), vol_state, pol)
    else:
        qty_calc = float(qty)
        usd_alloc = float(qty_calc) * float(price)

    st = _load_state()

    # лимит по кол-ву открытых позиций в портфеле
    try:
        max_open = int(pol.get("max_open_positions", 0))
    except Exception:
        max_open = 0
    if max_open > 0 and not paper_has_open_position(exchange, symbol, timeframe):
        if _count_open_positions(st) >= max_open:
            return {"status": "skip", "detail": "max_open_positions reached"}

    # лимит на долю капитала в одной монете
    try:
        pos_max_frac = float(pol.get("position_max_fraction", 1.0))
    except Exception:
        pos_max_frac = 1.0
    if pos_max_frac <= 0:
        pos_max_frac = 1.0

    try:
        equity = float(paper_get_equity().get("equity", 0.0))
    except Exception:
        equity = 0.0

    # сколько уже занято в этой монете и сколько ещё можно докупить
    cur_pos = _find_pos(st, exchange, symbol) or {"qty": 0.0, "avg_price": 0.0}
    current_mv = float(cur_pos.get("qty", 0.0)) * float(price)
    max_mv = equity * pos_max_frac
    remaining_usd = max(0.0, max_mv - current_mv)

    # минимум по заказу: берём из sizing.min_order_usd (если задан) или 0
    min_order = float(((pol.get("sizing") or {}).get("min_order_usd", 0.0)))
    if remaining_usd < max(min_order, 1e-12):
        return {"status": "skip", "detail": "position_max_fraction limit"}

    # итоговая аллокация: не больше лимита по монете
    usd_final = min(usd_alloc, remaining_usd)
    if usd_final <= 0:
        return {"status": "skip", "detail": "zero allocation"}

    qprec = int(((pol.get("auto_sizing") or {}).get("qty_precision", 6)))
    qty_final = float(round(usd_final / float(price), max(0, qprec)))
    if qty_final <= 0.0:
        return {"status": "skip", "detail": "too small size after limits"}

    note_meta = {
        "mode": "policy.sizing" if (pol.get("sizing")) else "virtual",
        "usd_alloc": usd_final,
        "pos_max_usd": max_mv,
        "remaining_usd": remaining_usd,
        "vol_state": vol_state,
    }
    return paper_open_buy_manual(
        exchange,
        symbol,
        timeframe,
        qty_final,
        float(price),
        ts_iso,
        note=f"auto buy sized | {json.dumps(note_meta, ensure_ascii=False)}",
        vol_state=vol_state,
    )


def paper_close_pair(exchange: str, symbol: str, timeframe: str, price: float, ts_iso: str) -> Dict[str, Any]:
    st = _load_state()
    pos = _find_pos(st, exchange, symbol)
    if pos is None or float(pos.get("qty", 0.0)) <= 0.0:
        return {"status": "error", "detail": "no open position"}
    qty = float(pos["qty"])
    return paper_open_sell_manual(exchange, symbol, timeframe, qty, float(price), ts_iso, note="auto close")


def paper_close_with_price(exchange: str, symbol: str, timeframe: str, price: float, ts_iso: str) -> Dict[str, Any]:
    return paper_close_pair(exchange, symbol, timeframe, price, ts_iso)
