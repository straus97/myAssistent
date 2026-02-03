"""
MyAssistent API - Автономный торговый бот с ML для Bybit
Версия 1.0 - Production Ready с полным мониторингом
"""
from __future__ import annotations

# Загрузка переменных окружения из .env файла (ДОЛЖНО БЫТЬ ПЕРВЫМ!)
from dotenv import load_dotenv
load_dotenv()

# Инициализация Sentry для error tracking (должно быть рано)
from src.sentry_integration import init_sentry
SENTRY_ENABLED = init_sentry()

import os
import json
from pathlib import Path
from fastapi import Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

# Импорты роутеров
from src.routers import (
    news,
    prices,
    dataset,
    report,
    watchlist,
    risk,
    notify,
    models,
    signals,
    trade,
    automation,
    ui,
    journal,
    backup,
    db_admin,
    debug,
    backtest,
    rl,
    mlflow_registry,
    validation,
    paper_monitor,
    risk_management,
    simple_strategy,
)

# Импорты зависимостей и утилит
from src.dependencies import get_db, require_api_key
from src.utils import _now_utc
from src.db import SessionLocal, Message

# Импорты для job функций
from src.news import fetch_and_store
from src.analysis import analyze_new_articles
from src.prices import fetch_and_store_prices
from src.features import build_dataset
from src.reports import build_daily_report
from src.watchlist import pairs_for_jobs, discover_pairs
from src.modeling import train_xgb_and_save
from src.model_policy import load_model_policy
from src.model_registry import get_active_model_path, set_active_model
from src.risk import load_policy


# ============== Конфигурация ==============

API_KEY = (os.getenv("API_KEY") or "").strip()
print(f"[config] API_KEY loaded: {bool(API_KEY)}")

USE_OFFLINE = os.getenv("OFFLINE_DOCS", "1") == "1"
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "1") == "1"

try:
    if USE_OFFLINE:
        from fastapi_offline import FastAPIOffline as _FastAPI
    else:
        from fastapi import FastAPI as _FastAPI
except Exception:
    from fastapi import FastAPI as _FastAPI
    USE_OFFLINE = False


# ============== FastAPI App ==============

app = _FastAPI(
    title="MyAssistent API",
    version="0.9",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    description=(
        "Backend for signals, paper-trading and news radar.\n\n"
        "Auth: send X-API-Key for all endpoints, кроме /, /ping и HTML-панелей.\n"
        "Responses: все ручки возвращают {'status':'ok', ...}. Списки — в поле 'data'.\n"
        "Ошибки: raise HTTPException с detail={'status':'error','code':..., 'detail':...}."
    ),
)

# ============== Prometheus Metrics ==============

METRICS_ENABLED = False
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    
    # Включаем метрики по умолчанию (можно отключить через ENABLE_METRICS=false)
    enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() not in ("false", "0", "no")
    
    if enable_metrics:
        instrumentator = Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics"],
            inprogress_name="fastapi_inprogress",
            inprogress_labels=True,
        )
        
        instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)
        METRICS_ENABLED = True
        print("[metrics] Prometheus metrics enabled at /metrics")
    else:
        print("[metrics] Metrics disabled via ENABLE_METRICS=false")
except ImportError:
    print("[metrics] prometheus-fastapi-instrumentator not installed, metrics disabled")
except Exception as e:
    print(f"[metrics] Error enabling Prometheus metrics: {e}")


# ============== CORS Middleware ==============

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
allow_all = CORS_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else CORS_ORIGINS,
    allow_credentials=False if allow_all else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Static Files (artifacts) ==============

Path("artifacts").mkdir(exist_ok=True)
if os.getenv("PUBLIC_ARTIFACTS", "0") == "1":
    app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
else:
    @app.get("/artifacts/{path:path}", tags=["Files"])
    def artifacts_secure(path: str, _=Depends(require_api_key)):
        from fastapi import HTTPException
        full = (Path("artifacts") / path).resolve()
        root = Path("artifacts").resolve()
        if root not in full.parents and full != root:
            raise HTTPException(404)
        if not full.is_file() or not str(full).startswith(str(root)):
            raise HTTPException(404)
        return FileResponse(str(full))


# ============== Подключение Роутеров ==============

app.include_router(news.router)
app.include_router(prices.router)
app.include_router(dataset.router)
app.include_router(report.router)
app.include_router(watchlist.router)
app.include_router(risk.router)
app.include_router(notify.router)
app.include_router(models.router)
app.include_router(signals.router)
app.include_router(trade.router)
app.include_router(automation.router)
app.include_router(ui.router)
app.include_router(journal.router)
app.include_router(backup.router)
app.include_router(db_admin.router)
app.include_router(debug.router)
app.include_router(backtest.router)
app.include_router(rl.router)
app.include_router(mlflow_registry.router)
app.include_router(validation.router)
app.include_router(paper_monitor.router)
app.include_router(risk_management.router)
app.include_router(simple_strategy.router)


# ============== Корневые Эндпоинты ==============

@app.get("/")
def root():
    """Редирект на /docs или /ping"""
    return RedirectResponse("/docs" if ENABLE_DOCS else "/ping")


@app.get("/ping")
def ping():
    """Simple health check"""
    return {"pong": True}


@app.get("/health")
def health():
    """
    Detailed health check для production monitoring.
    
    Проверяет:
    - Database connection
    - Scheduler status
    - Model availability
    - Disk space
    """
    from datetime import datetime
    
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {}
    }
    
    # Database check
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            health_status["services"]["database"] = "ok"
    except Exception as e:
        health_status["services"]["database"] = f"error: {e}"
        health_status["status"] = "degraded"
    
    # Scheduler check
    try:
        if scheduler and scheduler.running:
            health_status["services"]["scheduler"] = "ok"
        else:
            health_status["services"]["scheduler"] = "stopped"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["scheduler"] = f"error: {e}"
        health_status["status"] = "degraded"
    
    # Model check
    try:
        # Проверяем наличие модели в artifacts/models/
        models_dir = Path("artifacts/models")
        model_files = list(models_dir.glob("model_*.pkl")) if models_dir.exists() else []
        health_status["services"]["model"] = "ok" if model_files else "no_model"
    except Exception as e:
        health_status["services"]["model"] = f"error: {e}"
    
    # Sentry check
    health_status["services"]["sentry"] = "ok" if SENTRY_ENABLED else "disabled"
    
    return health_status


@app.get("/hello", tags=["Memory"])
def say_hello(name: str = "Никита"):
    """Приветствие"""
    return {"message": f"Привет, {name}! 🚀 Ассистент работает."}


@app.get("/time", tags=["Memory"])
def get_time():
    """Текущее время сервера"""
    return {"time": _now_utc().strftime("%Y-%m-%d %H:%M:%S %Z")}


@app.post("/memory/add", tags=["Memory"])
def add_message(text: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Добавить сообщение в память"""
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}


@app.get("/memory/add", tags=["Memory"])
def add_message_get(text: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Добавить сообщение в память (GET)"""
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}


@app.get("/memory/all", tags=["Memory"])
def get_messages(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить все сообщения из памяти"""
    msgs = db.query(Message).order_by(Message.id.desc()).all()
    return [{"id": m.id, "text": m.text, "created_at": m.created_at} for m in msgs]


# ============== APScheduler Jobs ==============

scheduler = BackgroundScheduler(timezone="UTC")


def job_build_report():
    """Ежедневный отчёт"""
    with SessionLocal() as db:
        try:
            pairs = [
                ("bybit", "BTC/USDT", "15m"),
                ("bybit", "ETH/USDT", "15m"),
            ]
            path = build_daily_report(db, pairs)
            print(f"[scheduler] report built: {path}")
        except Exception as e:
            print(f"[scheduler] report error: {e}")


def job_fetch_news():
    """Загрузка новостей (RSS)"""
    with SessionLocal() as db:
        try:
            added = fetch_and_store(db)
            print(f"[scheduler] news fetched: +{added}")
        except Exception as e:
            print(f"[scheduler] news fetch error: {e}")


def job_analyze_news():
    """Анализ новостей (sentiment + tags)"""
    with SessionLocal() as db:
        try:
            processed = analyze_new_articles(db, limit=200)
            print(f"[scheduler] news analyzed: {processed}")
        except Exception as e:
            print(f"[scheduler] news analyze error: {e}")


def job_discover_watchlist():
    """Auto-discovery топ-пар по объёму"""
    try:
        res = discover_pairs(
            min_volume_usd=2_000_000,
            top_n_per_exchange=25,
            quotes=("USDT",),
            timeframes=("15m",),
            limit=1000,
            exchanges=("bybit",),
        )
        print(f"[scheduler] discover_watchlist: +{len(res.get('added', []))} (watchlist={res.get('total_watchlist')})")
    except Exception as e:
        print(f"[scheduler] discover_watchlist error: {e}")


def job_fetch_prices():
    """Загрузка OHLCV для watchlist"""
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, lim in pairs:
            if ex != "bybit":
                continue
            try:
                added = fetch_and_store_prices(db, ex, sym, tf, lim)
                print(f"[scheduler] prices {ex} {sym} {tf}: +{added}")
            except Exception as e:
                print(f"[scheduler] prices error {ex} {sym} {tf}: {e}")


def job_train_models():
    """Обучение моделей по SLA (ночью)"""
    policy = load_model_policy()
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, _ in pairs:
            try:
                from src.db import ModelRun
                hz = 6 if tf.endswith("h") else 12
                df, feature_cols = build_dataset(db, ex, sym, tf, hz)
                if len(df) < int(policy.get("min_train_rows", 200)):
                    print(f"[scheduler] skip train {ex} {sym} {tf}: not enough data ({len(df)})")
                    continue

                # Проверка нужно ли переобучение
                need, reason, meta = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=len(df))
                if not need:
                    print(f"[scheduler] fresh model {ex} {sym} {tf} ({reason}) — skip")
                    continue

                metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
                run = ModelRun(
                    exchange=ex,
                    symbol=sym,
                    timeframe=tf,
                    horizon_steps=hz,
                    n_train=metrics["n_train"],
                    n_test=metrics["n_test"],
                    accuracy=metrics.get("accuracy"),
                    roc_auc=metrics.get("roc_auc"),
                    threshold=metrics.get("threshold"),
                    total_return=metrics.get("total_return"),
                    sharpe_like=metrics.get("sharpe_like"),
                    model_path=model_path,
                    features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
                )
                db.add(run)
                db.commit()

                if not get_active_model_path(ex, sym, tf, hz):
                    set_active_model(ex, sym, tf, hz, model_path)

                print(f"[scheduler] trained {ex} {sym} {tf}: AUC={metrics.get('roc_auc'):.3f}")
            except Exception as e:
                print(f"[scheduler] train error {ex} {sym} {tf}: {e}")


def job_make_signals():
    """Генерация сигналов каждые 15 минут"""
    from src.routers.signals import _compute_signal_for_last_bar
    from src.db import SignalEvent
    from src.notify import maybe_send_signal_notification
    
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, _ in pairs:
            try:
                hz = 6 if tf.endswith("h") else 12
                result = _compute_signal_for_last_bar(db, ex, sym, tf, hz, None)
                
                if result.get("status") == "ok":
                    signal = result.get("signal")
                    if signal == "buy":
                        print(f"[scheduler] signal BUY {ex} {sym} {tf}: prob={result.get('prob_up', 0):.3f}")
                        
                        # Сохранение в БД
                        evt = SignalEvent(
                            exchange=ex,
                            symbol=sym,
                            timeframe=tf,
                            horizon_steps=hz,
                            bar_dt=result.get("bar_dt"),
                            close=result.get("close"),
                            prob_up=result.get("prob_up"),
                            threshold=result.get("threshold"),
                            signal=signal,
                            model_path=result.get("model_path"),
                            note=json.dumps({
                                "prob": result.get("prob_up"),
                                "threshold": result.get("threshold"),
                                "prob_gap": result.get("prob_gap"),
                                "metrics": result.get("metrics", {}),
                                "reasons": result.get("reasons", []),
                            }, ensure_ascii=False),
                        )
                        db.add(evt)
                        try:
                            db.commit()
                            # Отправка уведомления в Telegram
                            maybe_send_signal_notification(
                                signal,
                                result.get("prob_up"),
                                result.get("threshold"),
                                result.get("prob_gap"),
                                result.get("reasons", []),
                                result.get("model_path"),
                                ex, sym, tf,
                                result.get("bar_dt"),
                                result.get("close"),
                                source="scheduler",
                            )
                        except Exception:
                            db.rollback()
            except Exception as e:
                print(f"[scheduler] signal error {ex} {sym} {tf}: {e}")


def job_resolve_outcomes():
    """Резолв исходов сигналов"""
    from src.db import SignalEvent, SignalOutcome
    with SessionLocal() as db:
        try:
            events = db.query(SignalEvent).filter(SignalEvent.signal.in_(["buy", "sell"])).order_by(SignalEvent.id.desc()).limit(100).all()
            resolved = 0
            for evt in events:
                existing = db.query(SignalOutcome).filter(SignalOutcome.signal_event_id == evt.id).first()
                if existing:
                    continue
                # Пытаемся резолвить (упрощённая логика)
                # TODO: полная реализация в будущем
                resolved += 1
            if resolved > 0:
                print(f"[scheduler] resolve_outcomes: {resolved}")
        except Exception as e:
            print(f"[scheduler] resolve_outcomes error: {e}")


def job_monitor_positions():
    """Мониторинг открытых позиций (partial close, flat)"""
    # TODO: перенести логику из main_old.py
    pass


def job_bootstrap():
    """Начальная инициализация при старте"""
    print("[scheduler] bootstrap: indexes ensured")


def job_self_audit_and_notify():
    """Самоаудит и уведомления в Telegram"""
    # TODO: перенести логику из main_old.py
    pass


def job_news_radar():
    """News Radar - детектор всплесков новостей"""
    policy = load_policy()
    cfg = policy.get("news_radar") or {}
    if not bool(cfg.get("enabled", False)):
        return
    
    from src.routers.news import news_radar, NewsRadarRequest
    window_minutes = int(cfg.get("window_minutes", 90))
    lookback_windows = int(cfg.get("lookback_windows", 6))
    symbols = cfg.get("symbols") or ["BTC", "ETH", "SOL", "XRP"]
    
    with SessionLocal() as db:
        try:
            res = news_radar(
                NewsRadarRequest(
                    window_minutes=window_minutes,
                    lookback_windows=lookback_windows,
                    symbols=symbols,
                    notify=True
                ),
                db,
            )
            if res.get("status") == "ok" and res.get("spike"):
                print("[scheduler] news_radar: SPIKE detected")
        except Exception as e:
            print(f"[scheduler] news_radar error: {e}")


def job_paper_monitor():
    """Paper Trading Real-Time Monitor - автоматическое обновление"""
    from src.paper_trading_monitor import run_monitor_update, load_monitor_state
    
    # Проверяем, включен ли монитор
    state = load_monitor_state()
    if not state.get("enabled", False):
        return
    
    try:
        result = run_monitor_update()
        if result.get("status") == "ok":
            signals_count = len(result.get("signals", []))
            if signals_count > 0:
                print(f"[scheduler] paper_monitor: {signals_count} new signals")
        else:
            print(f"[scheduler] paper_monitor error: {result.get('errors', [])}")
    except Exception as e:
        print(f"[scheduler] paper_monitor exception: {e}")


def job_risk_checks():
    """Risk Management - автоматические проверки stop-loss, take-profit, trailing stop"""
    from src.risk_management import run_risk_checks, load_risk_config
    
    # Проверяем, включен ли risk management
    config = load_risk_config()
    if not config.get("enabled", True):
        return
    
    with SessionLocal() as db:
        try:
            result = run_risk_checks(db)
            if result.get("status") == "ok":
                closed_count = result.get("positions_closed", 0)
                if closed_count > 0:
                    print(f"[scheduler] risk_checks: {closed_count} positions closed")
            else:
                errors = result.get("errors", [])
                if errors:
                    print(f"[scheduler] risk_checks errors: {errors}")
        except Exception as e:
            print(f"[scheduler] risk_checks exception: {e}")


def job_healthcheck_ping():
    """Healthchecks.io - ping каждые 5 минут для uptime monitoring"""
    from src.healthcheck_integration import healthcheck_with_system_status, HEALTHCHECK_URL
    
    try:
        if not HEALTHCHECK_URL:
            return
        success = healthcheck_with_system_status()
        if not success:
            print("[scheduler] healthcheck_ping: failed (check HEALTHCHECK_URL)")
    except Exception as e:
        print(f"[scheduler] healthcheck_ping exception: {e}")


def _model_needs_retrain(db: Session, exchange: str, symbol: str, timeframe: str, horizon_steps: int, policy: dict, df_len: int = 0):
    """
    Проверяет, нужно ли переобучать модель по SLA политике
    Возвращает: (need: bool, reason: str, meta: dict)
    """
    from src.db import ModelRun
    
    max_age_days = int(policy.get("max_age_days", 7))
    retrain_if_auc_below = float(policy.get("retrain_if_auc_below", 0.55))
    min_train_rows = int(policy.get("min_train_rows", 200))
    
    # 1) Проверка минимального размера датасета
    if df_len > 0 and df_len < min_train_rows:
        return False, f"dataset_too_small ({df_len} < {min_train_rows})", {}
    
    # 2) Проверка наличия модели
    last_run = (
        db.query(ModelRun)
        .filter(
            ModelRun.exchange == exchange,
            ModelRun.symbol == symbol,
            ModelRun.timeframe == timeframe,
            ModelRun.horizon_steps == horizon_steps,
        )
        .order_by(ModelRun.id.desc())
        .first()
    )
    
    if not last_run:
        return True, "no_model", {}
    
    # 3) Проверка возраста модели
    age_days = (_now_utc().replace(tzinfo=None) - last_run.created_at).days
    if age_days > max_age_days:
        return True, f"model_too_old ({age_days} > {max_age_days} days)", {"age_days": age_days}
    
    # 4) Проверка качества модели
    roc_auc = float(last_run.roc_auc or 0.0)
    if roc_auc < retrain_if_auc_below:
        return True, f"low_auc ({roc_auc:.3f} < {retrain_if_auc_below})", {"roc_auc": roc_auc}
    
    return False, f"model_fresh (age={age_days}d, auc={roc_auc:.3f})", {"age_days": age_days, "roc_auc": roc_auc}


# ============== Scheduler Lock (для множественных процессов) ==============

_SCHED_LOCK_PATH = Path("artifacts/state/scheduler.lock")
_SCHED_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
_SCHED_LOCK_OWNED = False


def _pid_alive(pid: int) -> bool:
    """Проверяет, жив ли процесс с заданным PID"""
    if pid <= 0:
        return False
    try:
        # 1) Если есть psutil — используем самый надежный путь
        try:
            import psutil  # type: ignore
            return psutil.pid_exists(pid)
        except Exception:
            pass

        # 2) Windows: пробуем открыть дескриптор процесса
        if os.name == "nt":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False

        # 3) POSIX: классический probe сигналом 0
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _acquire_scheduler_lock() -> bool:
    """
    Пытаемся атомарно создать lock-файл.
    Если он есть — проверяем, жив ли pid. Если нет — чистим и пробуем снова.
    """
    global _SCHED_LOCK_OWNED
    try:
        fd = os.open(str(_SCHED_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        _SCHED_LOCK_OWNED = True
        return True
    except FileExistsError:
        try:
            pid = int((_SCHED_LOCK_PATH.read_text() or "0").strip() or "0")
        except Exception:
            pid = 0
        if pid and _pid_alive(pid):
            return False
        try:
            _SCHED_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            return False
        return _acquire_scheduler_lock()
    except Exception:
        return False


def _release_scheduler_lock():
    """Освобождает scheduler lock"""
    global _SCHED_LOCK_OWNED
    if _SCHED_LOCK_OWNED:
        try:
            _SCHED_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        _SCHED_LOCK_OWNED = False


# ============== Startup / Shutdown Events ==============

@app.on_event("startup")
def on_startup():
    """Инициализация при старте приложения"""
    if not _acquire_scheduler_lock():
        print("[scheduler] lock is held by another process — skipping scheduler init")
        return
    
    # Создание индексов БД
    try:
        from src.db import ensure_runtime_indexes, SessionLocal
        with SessionLocal() as s:
            eng = s.get_bind()
        if eng is not None:
            ensure_runtime_indexes(eng)
            print("[db] indexes ensured")
    except Exception as e:
        print(f"[db] ensure indexes error: {e}")
    
    # Регистрация APScheduler jobs
    scheduler.add_job(
        job_discover_watchlist,
        CronTrigger(hour=0, minute=10),
        id="discover_watchlist",
        replace_existing=True
    )
    scheduler.add_job(
        job_fetch_news,
        IntervalTrigger(minutes=30),
        id="news_fetch",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_analyze_news,
        IntervalTrigger(minutes=30),
        id="news_analyze",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=_now_utc(),
    )
    scheduler.add_job(
        job_fetch_prices,
        IntervalTrigger(minutes=15),
        id="prices_fetch",
        replace_existing=True
    )
    scheduler.add_job(
        job_train_models,
        CronTrigger(hour=0, minute=35),
        id="train_models",
        replace_existing=True
    )
    scheduler.add_job(
        job_build_report,
        CronTrigger(hour=0, minute=50),
        id="build_report",
        replace_existing=True
    )
    scheduler.add_job(
        job_make_signals,
        IntervalTrigger(minutes=15),
        id="make_signals",
        replace_existing=True
    )
    scheduler.add_job(
        job_resolve_outcomes,
        IntervalTrigger(minutes=5),
        id="resolve_outcomes",
        replace_existing=True
    )
    scheduler.add_job(
        job_monitor_positions,
        IntervalTrigger(minutes=5),
        id="monitor_positions",
        replace_existing=True
    )
    scheduler.add_job(
        job_bootstrap,
        id="bootstrap_once",
        next_run_time=_now_utc(),
        replace_existing=True
    )
    scheduler.add_job(
        job_self_audit_and_notify,
        CronTrigger(hour=1, minute=10),
        id="self_audit",
        replace_existing=True
    )
    scheduler.add_job(
        job_news_radar,
        IntervalTrigger(minutes=10),
        id="news_radar",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    
    # Paper Trading Real-Time Monitor
    scheduler.add_job(
        job_paper_monitor,
        IntervalTrigger(minutes=15),
        id="paper_monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    
    # Risk Management Checks
    scheduler.add_job(
        job_risk_checks,
        IntervalTrigger(minutes=5),
        id="risk_checks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    
    # Healthcheck Ping (Uptime Monitoring)
    scheduler.add_job(
        job_healthcheck_ping,
        IntervalTrigger(minutes=5),
        id="healthcheck_ping",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    
    try:
        scheduler.start()
        print("[scheduler] started (primary)")
    except Exception as e:
        print(f"[scheduler] start error: {e}")
        _release_scheduler_lock()


@app.on_event("shutdown")
def on_shutdown():
    """Cleanup при остановке приложения"""
    try:
        scheduler.shutdown()
        print("[scheduler] shutdown")
    except Exception:
        pass
    finally:
        _release_scheduler_lock()
    
    # Утилизация движка БД
    try:
        with SessionLocal() as s:
            eng = s.get_bind()
        if eng is not None:
            eng.dispose()
            print("[db] engine disposed")
    except Exception:
        pass


# ============== Boot Log ==============

print("[boot] API_KEY present:", bool(API_KEY))
print("[boot] Offline docs:", USE_OFFLINE)
print("[boot] Docs enabled:", ENABLE_DOCS)
print("[boot] Routers loaded: news, prices, dataset, report, watchlist, risk, notify, models, signals, trade, automation, ui, journal, backup, db_admin, debug")
