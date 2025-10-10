from __future__ import annotations
import os
import time
import logging
import threading
from typing import Dict, Any
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.watchlist import list_watchlist, discover_pairs
from src.notify import get_notify_config, send_telegram

log = logging.getLogger("automation")
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = float(os.getenv("APP_HTTP_TIMEOUT", "25"))
CONCURRENCY_HINT = int(os.getenv("APP_AUTOMATION_CONCURRENCY", "1"))

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _call(method: str, path: str, json_body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    for attempt in range(3):
        try:
            r = requests.request(method, url, json=json_body, timeout=TIMEOUT)
            if r.ok:
                return r.json() if r.content else {}
            log.warning("HTTP %s %s -> %s %s", method, path, r.status_code, r.text[:200])
        except Exception as e:
            log.warning("HTTP %s %s error: %s", method, path, e)
        time.sleep(1.5 * (attempt + 1))
    return {}


# --- Jobs ---
def job_watchlist_discover():
    """Расширяем лист по ликвидности: раз в 6 часов."""
    res = discover_pairs(
        min_volume_usd=float(os.getenv("DISCOVER_MIN_VOL_USD", "2000000")),
        top_n_per_exchange=int(os.getenv("DISCOVER_TOP_N", "25")),
        quotes=tuple(os.getenv("DISCOVER_QUOTES", "USDT").split(",")),
        timeframes=tuple(os.getenv("DISCOVER_TIMEFRAMES", "15m").split(",")),
        limit=int(os.getenv("DISCOVER_LIMIT", "1000")),
        exchanges=tuple(os.getenv("DISCOVER_EXCHANGES", "binance,bybit").split(",")),
    )
    added = res.get("added", [])
    if added:
        log.info("discover_pairs: added %d", len(added))
        # пинганём в тг, если включено
        cfg = get_notify_config()
        if cfg.get("enabled"):
            send_telegram(
                f"[WL] Added {len(added)} pairs:\n"
                + "\n".join(f"{p['exchange']} {p['symbol']} {p['timeframe']}" for p in added[:15])
            )


def job_prices_sync():
    """Подгружаем OHLCV для всех пар из watchlist: каждые 2–5 минут."""
    pairs = list_watchlist()
    for p in pairs:
        body = {
            "exchange": p["exchange"],
            "symbol": p["symbol"],
            "timeframe": p["timeframe"],
            "limit": p.get("limit", 500),
        }
        _call("POST", "/prices/fetch", body)


def job_news_fetch():
    """Тянем RSS/источники: каждые 5 минут."""
    _call("POST", "/news/fetch", {})


def job_news_analyze():
    """Запускаем разметку новостей: каждые 10 минут."""
    _call("POST", "/news/analyze", {})


def job_models_maint():
    """Ежедневное обновление датасета/тренировка по всем парам (ночью)."""
    pairs = list_watchlist()
    for p in pairs:
        base = {
            "exchange": p["exchange"],
            "symbol": p["symbol"],
            "timeframe": p["timeframe"],
            "horizon_steps": int(os.getenv("HORIZON_STEPS", "12")),
        }
        _call("POST", "/dataset/build", base)
        _call("POST", "/model/train", base)


def job_signals_cycle():
    """Каждые 5 минут оцениваем сигналы по всем парам (уведомления включаются политикой)."""
    pairs = list_watchlist()
    for p in pairs:
        base = {
            "exchange": p["exchange"],
            "symbol": p["symbol"],
            "timeframe": p["timeframe"],
            "horizon_steps": int(os.getenv("HORIZON_STEPS", "12")),
        }
        _call("POST", "/signal/latest", base)


def job_daily_report():
    """Раз в день собираем отчет и, если надо, кидаем ссылку в ТГ."""
    res = _call("POST", "/report/daily", {})
    path = (res or {}).get("path") or "artifacts/reports/latest.html"
    cfg = get_notify_config()
    if cfg.get("enabled"):
        send_telegram(f"[Report] Сформирован дневной отчёт: {path}")


# --- Lifecycle ---
def start_scheduler():
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return _scheduler
        _scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "UTC"))
        # discovery: каждые 6 часов
        _scheduler.add_job(job_watchlist_discover, IntervalTrigger(hours=6), id="discover")
        # цены: каждые 3 минуты (регулируется переменной)
        every_min = int(os.getenv("PRICES_EVERY_MIN", "3"))
        _scheduler.add_job(job_prices_sync, IntervalTrigger(minutes=every_min), id="prices")
        # новости
        _scheduler.add_job(job_news_fetch, IntervalTrigger(minutes=5), id="news_fetch")
        _scheduler.add_job(job_news_analyze, IntervalTrigger(minutes=10), id="news_analyze")
        # модели ночью (по умолчанию 03:20 UTC)
        hh, mm = os.getenv("MODELS_DAILY_UTC", "03:20").split(":")
        _scheduler.add_job(job_models_maint, CronTrigger(hour=int(hh), minute=int(mm)), id="models_daily")
        # сигналы — каждые 5 минут
        _scheduler.add_job(job_signals_cycle, IntervalTrigger(minutes=5), id="signals")
        # отчёт — 03:50 UTC
        rh, rm = os.getenv("REPORT_DAILY_UTC", "03:50").split(":")
        _scheduler.add_job(job_daily_report, CronTrigger(hour=int(rh), minute=int(rm)), id="report_daily")

        _scheduler.start()
        log.warning("Automation scheduler started")
        return _scheduler


def stop_scheduler():
    global _scheduler
    with _lock:
        if _scheduler:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            log.warning("Automation scheduler stopped")
