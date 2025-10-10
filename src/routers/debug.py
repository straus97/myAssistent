"""
Роутер для отладочных эндпоинтов
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as _sa_text

from src.dependencies import get_db


router = APIRouter(tags=["Debug"])


@router.get("/_debug/info")
def debug_info():
    """Отладочная информация (routes, cwd, sys.path)"""
    return {
        "cwd": str(Path.cwd()),
        "sys_path": sys.path[:5],
        "python_version": sys.version,
    }


@router.get("/_debug/env")
def debug_env():
    """Переменные окружения (masked)"""
    env = {}
    for k, v in os.environ.items():
        if any(s in k.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            env[k] = "***"
        else:
            env[k] = v[:100] if len(v) > 100 else v
    return env


@router.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    """Health check эндпоинт"""
    db_ok = True
    try:
        db.execute(_sa_text("SELECT 1"))
    except Exception:
        db_ok = False
    
    # TODO: получить scheduler из main.py для проверки jobs
    return {
        "ok": db_ok,
        "db_ok": db_ok,
        "scheduler": {"jobs": 0, "locked": False},
    }


# NOTE: Этот роутер содержит отладочные эндпоинты.
# Для полного healthz нужно передать scheduler instance из main.py

