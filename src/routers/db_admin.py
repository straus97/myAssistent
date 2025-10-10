"""
Роутер для административных операций с БД
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import inspect as _sa_inspect

from src.dependencies import get_db, require_api_key, ok
from src.db import SessionLocal


router = APIRouter(prefix="/db", tags=["DB"])


@router.get("/info")
def db_info(_=Depends(require_api_key)):
    """Получить информацию о БД (URL, dialect, таблицы)"""
    with SessionLocal() as s:
        eng = s.get_bind()
        url = str(getattr(eng, "url", None)) if eng else None
        dialect = getattr(getattr(eng, "dialect", None), "name", None) if eng else None
        insp = _sa_inspect(eng) if eng else None
        tables = sorted(insp.get_table_names()) if insp else []
    return {"url": url, "dialect": dialect, "tables": tables}


@router.get("/tables")
def db_tables(_=Depends(require_api_key), db: Session = Depends(get_db)):
    """Получить список таблиц в БД"""
    eng = db.get_bind()
    insp = _sa_inspect(eng)
    tables = sorted(insp.get_table_names())
    return ok(tables=tables)


@router.get("/table")
def db_table(table_name: str, limit: int = 10, _=Depends(require_api_key), db: Session = Depends(get_db)):
    """Получить данные из таблицы"""
    # TODO: перенести реализацию из main.py (безопасный SELECT)
    return ok(table=table_name, rows=[], message=f"Table '{table_name}' preview (stub)")


# NOTE: Этот роутер содержит базовые DB admin эндпоинты.
# Для полной реализации db/table нужно перенести код SELECT из main.py

