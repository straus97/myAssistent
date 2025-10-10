"""
Общие зависимости для FastAPI роутеров
"""
from __future__ import annotations
import os
from typing import Optional, Any
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from src.db import SessionLocal


API_KEY = (os.getenv("API_KEY") or "").strip()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_db() -> Session:
    """Генератор сессии БД для dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> bool:
    """Проверка X-API-Key header для защищённых эндпоинтов"""
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "code": "auth.server_misconfigured", "detail": "Set env API_KEY"},
        )
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "auth.missing", "detail": "Provide X-API-Key header"},
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "auth.invalid", "detail": "X-API-Key is invalid"},
        )
    return True


def ok(**kwargs) -> dict:
    """Успешный ответ с дополнительными полями"""
    return {"status": "ok", **kwargs}


def ok_data(data: Any) -> dict:
    """Успешный ответ с данными"""
    return {"status": "ok", "data": data}


def err(code: str, detail: Any = None, http: int = 400):
    """Единый способ отдавать ошибки"""
    raise HTTPException(status_code=http, detail={"status": "error", "code": code, "detail": detail})

