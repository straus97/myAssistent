from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from src.db import SessionLocal, Message, Article, ArticleAnnotation, Price
from src.news import fetch_and_store
from src.analysis import analyze_new_articles
from src.prices import fetch_and_store_prices

from src.features import build_dataset
from pathlib import Path
from src.modeling import train_and_save


app = FastAPI(title="My Assistant API", version="0.4")

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