"""
Роутер для экспорта журнала сделок
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok


router = APIRouter(prefix="/journal", tags=["Journal"])


@router.get("/export")
def journal_export(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Экспорт журнала сделок в CSV"""
    # TODO: перенести реализацию из main.py
    return ok(message="Journal CSV export (stub)")


@router.get("/export_pretty")
def journal_export_pretty(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Экспорт журнала сделок в красиво отформатированный Excel"""
    # TODO: перенести реализацию из main.py (XlsxWriter)
    return ok(message="Journal XLSX export (stub)")


# NOTE: Этот роутер содержит заглушки для journal эндпоинтов.
# Для полной реализации нужно перенести код генерации CSV/XLSX из main.py

