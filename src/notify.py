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

    # 4) «человеческий» стиль с максимальной детализацией
    side = "ПОКУПКА" if final_signal.lower() == "buy" else "БЕЗ ДЕЙСТВИЯ"
    emoji = "🟢" if final_signal.lower() == "buy" else "⚪"
    ex = (exchange or "").upper()
    price_s = _fmt_price(float(close))
    time_s = _ts_hhmm_utc(bar_dt)
    gap_pp = delta * 100.0

    # Определяем состояние волатильности из фильтров
    vol_state = "normal"
    vol_info = ""
    try:
        if reasons:
            for r in reasons:
                if "dead_volatility" in r.lower():
                    vol_state = "dead"
                    vol_info = "🧊 Низкая волатильность (рынок спокоен)"
                    break
                elif "hot_volatility" in r.lower() or "hot market" in r.lower():
                    vol_state = "hot"
                    vol_info = "🔥 Высокая волатильность (рынок активен)"
                    break
        if not vol_info:
            vol_info = "〰️ Нормальная волатильность"
    except Exception:
        pass
    _vol_emoji(vol_state)

    # Анализ фильтров для детального вывода
    filter_details = []
    risk_warnings = []
    if reasons:
        for r in reasons:
            r_lower = r.lower()
            if "pass" in r_lower or "ok" in r_lower or "allow" in r_lower:
                continue  # Пропускаем "pass" фильтры
            if "block" in r_lower or "reject" in r_lower or "dead" in r_lower:
                risk_warnings.append(f"⚠️ {r}")
            elif "volume" in r_lower:
                filter_details.append(f"📊 {r}")
            elif "trend" in r_lower or "ema" in r_lower:
                filter_details.append(f"📈 {r}")
            elif "cooldown" in r_lower:
                filter_details.append(f"⏱ {r}")
            else:
                filter_details.append(f"• {r}")

    # Размер позиции и советы
    buy_fraction = 0.10
    try:
        if isinstance(pol.get("buy_fraction"), (int, float)):
            buy_fraction = float(pol.get("buy_fraction"))
        else:
            bf_auto = (pol.get("auto") or {}).get("buy_fraction") or {}
            if isinstance(bf_auto, dict) and "normal" in bf_auto:
                buy_fraction = float(bf_auto.get("normal", buy_fraction))
    except Exception:
        pass

    # Информация о модели
    model_info = ""
    if model_path:
        try:
            model_name = Path(model_path).stem if model_path else "unknown"
            # Попытаемся извлечь дату из имени файла (формат: model_SYMBOL_TF_YYYYMMDD_HHMMSS.pkl)
            parts = model_name.split("_")
            if len(parts) >= 4:
                date_part = parts[-2] if parts[-2].isdigit() and len(parts[-2]) == 8 else ""
                if date_part:
                    model_info = f"📦 Модель: {date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                else:
                    model_info = f"📦 Модель: {model_name[:30]}"
            else:
                model_info = f"📦 Модель: {model_name[:30]}"
        except Exception:
            model_info = "📦 Модель: активная"

    # Формирование сообщения
    msg_lines = [
        f"{emoji} {side}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏦 Биржа: {ex}",
        f"💰 Пара: {symbol}",
        f"⏰ Таймфрейм: {timeframe}",
        f"💵 Цена: {price_s}",
        f"🕐 Время: {time_s}",
        "",
        "📊 СИГНАЛ:",
        f"• Вероятность: {proba:.1%}",
        f"• Порог модели: {threshold:.1%}",
        f"• Запас: {gap_pp:+.1f} п.п. ({'сильный' if abs(gap_pp) > 5 else 'умеренный'})",
        "",
        vol_info,
    ]

    if model_info:
        msg_lines.append(f"{model_info}")

    # Добавляем предупреждения о рисках
    if risk_warnings:
        msg_lines.append("")
        msg_lines.append("⚠️ РИСКИ:")
        for warn in risk_warnings[:3]:  # Макс 3 предупреждения
            msg_lines.append(warn)

    # Добавляем детали фильтров (если есть и сигнал BUY)
    if filter_details and final_signal.lower() == "buy":
        msg_lines.append("")
        msg_lines.append("✓ ФИЛЬТРЫ ПРОЙДЕНЫ:")
        for detail in filter_details[:4]:  # Макс 4 фильтра
            msg_lines.append(detail)

    # Рекомендации и команды
    msg_lines.append("")
    if final_signal.lower() == "buy":
        msg_lines.append("💡 РЕКОМЕНДАЦИЯ:")
        msg_lines.append(f"Купить на {buy_fraction*100:.0f}% от капитала")
        msg_lines.append("")
        msg_lines.append("🤖 Быстрая команда:")
        msg_lines.append(f"/buy {exchange} {symbol} {buy_fraction}")
    else:
        msg_lines.append("💡 РЕКОМЕНДАЦИЯ:")
        msg_lines.append("Пропустить сделку (не выполнены условия)")
        if reasons:
            top_reason = reasons[0] if reasons else "неизвестно"
            msg_lines.append(f"Причина: {top_reason}")

    msg = "\n".join(msg_lines)
    send_telegram(msg)
