from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session

from datetime import datetime
from pathlib import Path

# НОВОЕ: планировщик
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Импорты модулей проекта
from src.db import SessionLocal, Message, Article, ArticleAnnotation, Price
from src.news import fetch_and_store
from src.analysis import analyze_new_articles
from src.prices import fetch_and_store_prices
from src.features import build_dataset
from src.modeling import train_and_save

from fastapi.responses import HTMLResponse
from src.reports import build_daily_report

app = FastAPI(title="My Assistant API", version="0.5")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/hello")
def say_hello(name: str = "Никита"):
    return {"message": f"Привет, {name}! 🚀 Ассистент работает."}

@app.get("/time")
def get_time():
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Оставляем POST-эндпоинт как есть
@app.post("/memory/add")
def add_message(text: str, db: Session = Depends(get_db)):
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}

# ДОБАВИЛИ удобный GET-эндпоинт
@app.get("/memory/add")
def add_message_get(text: str, db: Session = Depends(get_db)):
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}

@app.get("/memory/all")
def get_messages(db: Session = Depends(get_db)):
    msgs = db.query(Message).order_by(Message.id.desc()).all()
    return [{"id": m.id, "text": m.text, "created_at": m.created_at} for m in msgs]

# --- НОВОЕ: новости ---
@app.post("/news/fetch")
def news_fetch(db: Session = Depends(get_db)):
    added = fetch_and_store(db)
    return {"status": "ok", "added": added}

@app.get("/news/latest")
def news_latest(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(Article)
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "source": r.source,
            "title": r.title,
            "url": r.url,
            "published_at": r.published_at,
        }
        for r in rows
    ]

@app.get("/news/search")
def news_search(q: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
    q_like = f"%{q.lower()}%"
    rows = (
        db.query(Article)
        .filter((Article.title.ilike(q_like)) | (Article.summary.ilike(q_like)))
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "source": r.source,
            "title": r.title,
            "url": r.url,
            "published_at": r.published_at,
        }
        for r in rows
    ]


# --- НОВОЕ: аналитика ---
@app.post("/news/analyze")
def news_analyze(limit: int = 100, db: Session = Depends(get_db)):
    processed = analyze_new_articles(db, limit=limit)
    return {"status": "ok", "processed": processed}

@app.get("/news/annotated")
def news_annotated(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for art, ann in rows:
        result.append({
            "id": art.id,
            "source": art.source,
            "title": art.title,
            "url": art.url,
            "published_at": art.published_at,
            "lang": ann.lang,
            "sentiment": ann.sentiment,
            "tags": ann.tags.split(",") if ann.tags else []
        })
    return result

@app.get("/news/by_tag")
def news_by_tag(tag: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
    tag = tag.lower()
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .filter(ArticleAnnotation.tags.ilike(f"%{tag}%"))
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": art.id,
            "source": art.source,
            "title": art.title,
            "url": art.url,
            "published_at": art.published_at,
            "lang": ann.lang,
            "sentiment": ann.sentiment,
            "tags": ann.tags.split(",") if ann.tags else []
        }
        for art, ann in rows
    ]

@app.post("/prices/fetch")
def prices_fetch(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 500,
    db: Session = Depends(get_db)
):
    try:
        added = fetch_and_store_prices(db, exchange, symbol, timeframe, limit)
        return {"status": "ok", "added": added}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/prices/latest")
def prices_latest(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 100,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(Price)
        .filter(Price.exchange==exchange, Price.symbol==symbol, Price.timeframe==timeframe)
        .order_by(Price.ts.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [
        {"ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ]

@app.post("/dataset/build")
def dataset_build(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    horizon_steps: int = 6,
    db: Session = Depends(get_db)
):
    try:
        df, feature_cols = build_dataset(db, exchange, symbol, timeframe, horizon_steps)
        info = {
            "rows": int(len(df)),
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "n_features": len(feature_cols),
            "features": feature_cols[:10] + (["..."] if len(feature_cols) > 10 else [])
        }
        # по желанию: сохранить в CSV для дебага
        Path("artifacts").mkdir(exist_ok=True)
        csv_path = Path("artifacts") / "dataset_preview.csv"
        df.head(200).to_csv(csv_path, encoding="utf-8")
        info["preview_csv"] = str(csv_path.resolve())
        return {"status": "ok", "info": info}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/model/train")
def model_train(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    horizon_steps: int = 6,
    db: Session = Depends(get_db)
):
    try:
        df, feature_cols = build_dataset(db, exchange, symbol, timeframe, horizon_steps)
        if len(df) < 200:
            return {"status": "error", "detail": "Данных слишком мало (<200 строк) для тренировки. Загрузите больше свечей."}
        metrics = train_and_save(df, feature_cols, target_col="y", artifacts_dir="artifacts")
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/report/daily")
def report_daily(db: Session = Depends(get_db)):
    # какие пары включать в отчёт (можно изменить под себя)
    pairs = [("binance", "BTC/USDT", "1h"), ("binance", "ETH/USDT", "15m")]
    path = build_daily_report(db, pairs)
    return {"status": "ok", "path": str(path.resolve())}

@app.get("/report/latest", response_class=HTMLResponse)
def report_latest():
    p = Path("artifacts") / "reports" / "latest.html"
    if not p.exists():
        return HTMLResponse("<h3>Отчёт ещё не сформирован</h3>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


# --------------------------
# НОВОЕ: АВТОМАТИЗАЦИЯ (планировщик задач)
# --------------------------

scheduler = BackgroundScheduler(timezone="UTC")

# Конфигурация того, что и когда обновлять
PAIRS = [
    # (exchange, symbol, timeframe, limit)
    ("binance", "BTC/USDT", "1h", 500),
    ("binance", "ETH/USDT", "15m", 1000),
]

def job_build_report():
    from pathlib import Path
    with SessionLocal() as db:
        try:
            pairs = [("binance", "BTC/USDT", "1h"), ("binance", "ETH/USDT", "15m")]
            path = build_daily_report(db, pairs)
            print(f"[scheduler] report built: {path}")
        except Exception as e:
            print(f"[scheduler] report error: {e}")

def job_fetch_news():
    with SessionLocal() as db:
        try:
            added = fetch_and_store(db)
            print(f"[scheduler] news fetched: +{added}")
        except Exception as e:
            print(f"[scheduler] news fetch error: {e}")

def job_analyze_news():
    with SessionLocal() as db:
        try:
            processed = analyze_new_articles(db, limit=200)
            print(f"[scheduler] news analyzed: {processed}")
        except Exception as e:
            print(f"[scheduler] news analyze error: {e}")

def job_fetch_prices():
    with SessionLocal() as db:
        for ex, sym, tf, lim in PAIRS:
            try:
                added = fetch_and_store_prices(db, ex, sym, tf, lim)
                print(f"[scheduler] prices {ex} {sym} {tf}: +{added}")
            except Exception as e:
                print(f"[scheduler] prices error {ex} {sym} {tf}: {e}")

def job_train_models():
    with SessionLocal() as db:
        for ex, sym, tf, _ in PAIRS:
            try:
                # horizon_steps можно варьировать: для 1h=6 (~6ч), для 15m=12 (~3ч)
                horizon = 6 if tf == "1h" else 12
                df, feature_cols = build_dataset(db, ex, sym, tf, horizon)
                if len(df) < 200:
                    print(f"[scheduler] skip train {sym} {tf}: not enough data ({len(df)})")
                    continue
                metrics = train_and_save(df, feature_cols, target_col="y", artifacts_dir="artifacts")
                print(f"[scheduler] trained {sym} {tf}: {metrics}")
            except Exception as e:
                print(f"[scheduler] train error {sym} {tf}: {e}")

@app.on_event("startup")
def on_startup():
    # Новости: каждые 30 минут
    scheduler.add_job(job_fetch_news, IntervalTrigger(minutes=30), id="news_fetch", replace_existing=True)
    # Аналитика новостей: каждые 30 минут, со сдвигом (через 5 минут после фетча)
    scheduler.add_job(job_analyze_news, IntervalTrigger(minutes=30), id="news_analyze", replace_existing=True,
                      next_run_time=None)
    # Цены: каждые 15 минут
    scheduler.add_job(job_fetch_prices, IntervalTrigger(minutes=15), id="prices_fetch", replace_existing=True)
    # Ночная тренировка: каждый день в 02:00 UTC
    scheduler.add_job(job_train_models, CronTrigger(hour=0, minute=35), id="train_models", replace_existing=True)
    # ежедневный отчёт после тренировки
    scheduler.add_job(job_build_report, CronTrigger(hour=0, minute=50), id="build_report", replace_existing=True)

    try:
        scheduler.start()
        print("[scheduler] started")
    except Exception as e:
        print(f"[scheduler] start error: {e}")

@app.on_event("shutdown")
def on_shutdown():
    try:
        scheduler.shutdown()
        print("[scheduler] shutdown")
    except Exception:
        pass

# Вспомогательный статус-эндпоинт
@app.get("/automation/status")
def automation_status():
    jobs = scheduler.get_jobs()
    return [
        {
            "id": j.id,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            "trigger": str(j.trigger)
        }
        for j in jobs
    ]