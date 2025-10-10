"""
Роутер для отчётов (HTML daily report)
"""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key
from src.reports import build_daily_report


router = APIRouter(prefix="/report", tags=["Report"])


@router.post("/daily")
def report_daily(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Формирование ежедневного HTML-отчёта"""
    pairs = [
        ("bybit", "BTC/USDT", "15m"),
        ("bybit", "ETH/USDT", "15m"),
    ]
    path = build_daily_report(db, pairs)
    return {"status": "ok", "path": str(path.resolve())}


@router.get("/latest", response_class=HTMLResponse)
def report_latest():
    """Получить последний сформированный HTML-отчёт"""
    p = Path("artifacts") / "reports" / "latest.html"
    if not p.exists():
        return HTMLResponse("<h3>Отчёт ещё не сформирован</h3>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))

