from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Tuple
import requests
from .risk import load_policy
import math
from datetime import timezone as _tz

CFG_DIR = Path("artifacts") / "config"
CFG_DIR.mkdir(parents=True, exist_ok=True)
CFG_PATH = CFG_DIR / "notify.json"

DEFAULT_CFG: Dict[str, Any] = {
    "enabled": False,
    "telegram": {"token": "", "chat_id": 0},
    # дополнительные правила (можно расширять по вкусу)
    "rules": {
        "prefix": "[MyAssistant]",
        "send_flat": False,  # слать ли flat-сигналы
        "min_abs_prob_gap": 0.0,  # минимальный |prob - thr| для уведомления
    },
}


def _load_raw() -> Dict[str, Any]:
    if not CFG_PATH.exists():
        CFG_PATH.write_text(json.dumps(DEFAULT_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_CFG.copy()
    try:
        data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return {**DEFAULT_CFG, **(data or {})}


def get_notify_config(mask: bool = True) -> Dict[str, Any]:
    cfg = _load_raw()
    if mask:
        tg = cfg.get("telegram") or {}
        if "token" in tg and tg["token"]:
            tg = {**tg, "token": tg["token"][:7] + "..." + tg["token"][-4:]}
        cfg["telegram"] = tg
    return cfg


def save_notify_config(cfg: Dict[str, Any]) -> None:
    data = {**DEFAULT_CFG, **(cfg or {})}
    CFG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def send_telegram(text: str) -> Tuple[bool, str]:
    """Отправляет сообщение в телеграм. Возвращает (ok, detail)."""
    cfg = _load_raw()
    if not cfg.get("enabled"):
        return False, "notifications disabled"
    tg = cfg.get("telegram") or {}
    token = (tg.get("token") or "").strip()
    chat_id = int(tg.get("chat_id") or 0)
    if not token or not chat_id:
        return False, "telegram token/chat_id not configured"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.ok:
            return True, "sent"
        return False, f"{r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"error: {e}"


def _fmt_price(x: float) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    if x >= 100:
        return f"{x:,.2f}".replace(",", " ")
    if x >= 1:
        return f"{x:,.3f}"
    if x >= 0.01:
        return f"{x:,.4f}"
    return f"{x:.6f}"


def _ts_hhmm_utc(dt) -> str:
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.astimezone(_tz.utc).strftime("%H:%M UTC")
    except Exception:
        return str(dt)


def _vol_emoji(state: str | None) -> str:
    return {"hot": "🔥", "dead": "🧊", "normal": "〰️"}.get((state or "normal"), "〰️")


def maybe_send_signal_notification(
    final_signal: str,
    proba: float,
    threshold: float,
    delta: float,
    reasons: list[str],
    model_path: str | None,
    exchange: str,
    symbol: str,
    timeframe: str,
    bar_dt,
    close: float,
    source: str = "endpoint",
) -> None:
    """
    Новый «человеческий» формат сообщений.
    Переключается через policy.notify.style = "simple" | "raw"
    и policy.notify.send_flat (если нужно присылать FLAT).
    """
    # 1) базовые настройки из artifacts/config/notify.json
    cfg = _load_raw()
    if not cfg.get("enabled"):
        return
    rules = cfg.get("rules") or {}
    send_flat = bool(rules.get("send_flat", False))
    min_gap = float(rules.get("min_abs_prob_gap", 0.0))
    if final_signal == "flat" and not send_flat:
        return
    if abs(delta) < min_gap:
        return

    # 2) учтём предпочтения из policy.json
    pol = load_policy() or {}
    notify_pol = pol.get("notify") or {}
    style = str(notify_pol.get("style", "simple")).lower()

    # 3) сырой стиль на случай отладки
    if style == "raw":
        prefix = str(rules.get("prefix", "") or "").strip()
        if prefix:
            prefix += " "
        raw = (
            f"{prefix}СИГНАЛ ({source})\n"
            f"{exchange.upper()} {symbol} {timeframe} @ {bar_dt}\n"
            f"close={close:.6f}\n"
            f"signal={final_signal.upper()} • p={proba:.3f} thr={threshold:.3f} gap={delta:+.3f}\n"
        )
        if reasons:
            raw += "Фильтры: " + "; ".join(reasons[:6])
        if model_path:
            raw += f"\n{model_path}"
        send_telegram(raw)
        return

    # 4) «человеческий» стиль
    side = "ПОКУПКА" if final_signal.lower() == "buy" else "БЕЗ ДЕЙСТВИЯ"
    emoji = "🟢" if final_signal.lower() == "buy" else "⚪"
    ex = (exchange or "").upper()
    price_s = _fmt_price(float(close))
    time_s = _ts_hhmm_utc(bar_dt)
    gap_pp = delta * 100.0

    # эмодзи волатильности — по тексту причины если есть
    vol_state = None
    try:
        if reasons and any("dead_volatility" in r for r in reasons):
            vol_state = "dead"
    except Exception:
        pass
    vol = _vol_emoji(vol_state)

    # совет по доле покупки: берём root buy_fraction либо дефолт 0.10
    buy_fraction = 0.10
    try:
        if isinstance(pol.get("buy_fraction"), (int, float)):
            buy_fraction = float(pol.get("buy_fraction"))
        else:
            # запасной вариант: если в pol["auto"]["buy_fraction"] есть словарь — возьмём «normal»
            bf_auto = (pol.get("auto") or {}).get("buy_fraction") or {}
            if isinstance(bf_auto, dict) and "normal" in bf_auto:
                buy_fraction = float(bf_auto.get("normal", buy_fraction))
    except Exception:
        pass

    advise = "Совет: ничего не делать"
    if final_signal.lower() == "buy":
        advise = f"Совет: купить на {buy_fraction*100:.0f}% капитала"

    # быстрая команда SELL (как ты просил)
    # Пример: /sell bybit BTC/USDT 0.25 @ 3520 tf=15m
    # Возьмём текущую цену и подставим 0.25 как шаблон.
    quick_sell = f"/sell {exchange} {symbol} 0.25 @ {close:.2f} tf={timeframe}"

    msg = (
        f"{emoji} {side} — {ex} • {symbol} • {timeframe}\n"
        f"Цена: {price_s}  •  Время: {time_s}\n"
        f"Шанс: {proba:.1%}  (порог {threshold:.1%}, запас {gap_pp:+.1f} п.п.)\n"
        f"{vol} {advise}\n"
        f"Команда: {quick_sell}"
    )

    send_telegram(msg)
