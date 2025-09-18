from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from src.db import SessionLocal, Message, Article
from src.news import fetch_and_store

app = FastAPI(title="My Assistant API", version="0.3")

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
