from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from src.db import SessionLocal, Message

app = FastAPI(title="My Assistant API", version="0.2")

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
    msgs = db.query(Message).all()
    return [{"id": m.id, "text": m.text, "created_at": m.created_at} for m in msgs]
