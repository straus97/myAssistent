"""
Роутер для UI эндпоинтов (HTML summary, equity charts)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.dependencies import get_db


router = APIRouter(prefix="/ui", tags=["UI"])


@router.get("/summary")
def ui_summary(db: Session = Depends(get_db)):
    """Получить JSON-сводку для UI"""
    # TODO: перенести реализацию из main.py
    return {"status": "ok", "summary": {"message": "Summary (stub)"}}


@router.get("/summary_html", response_class=HTMLResponse)
def ui_summary_html(db: Session = Depends(get_db)):
    """Получить HTML-сводку для UI"""
    # TODO: перенести реализацию из main.py
    return HTMLResponse("<h3>Summary HTML (stub)</h3>")


@router.get("/equity_html", response_class=HTMLResponse)
def ui_equity_html(db: Session = Depends(get_db)):
    """Получить HTML-график equity"""
    # TODO: перенести реализацию из main.py
    return HTMLResponse("<h3>Equity Chart HTML (stub)</h3>")


# NOTE: Этот роутер содержит заглушки для UI эндпоинтов.
# Для полной реализации нужно перенести код генерации HTML из main.py

