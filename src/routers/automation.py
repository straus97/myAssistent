"""
Роутер для управления автоматизацией (APScheduler jobs)
"""
from __future__ import annotations
from typing import Optional, Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.dependencies import get_db, require_api_key, ok
from sqlalchemy.orm import Session


router = APIRouter(prefix="/automation", tags=["Automation"])


@router.get("/status")
def automation_status(_=Depends(require_api_key)):
    """Получить статус всех фоновых задач (APScheduler jobs)"""
    # TODO: получить scheduler из main.py и вернуть список jobs
    return ok(jobs=[], message="Scheduler status (stub - needs scheduler instance)")


class AutomationRunRequest(BaseModel):
    """Запрос на разовый запуск фоновой задачи"""

    action: Optional[Literal["signal_once", "scan_watchlist", "train_missing"]] = None
    job: Optional[Literal["fetch_prices", "fetch_news", "analyze_news", "train_models", "make_signals", "news_radar"]] = None


@router.post("/run")
def automation_run(req: AutomationRunRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Разовый запуск фоновой задачи"""
    # TODO: реализация запуска конкретной job
    return ok(action=req.action, job=req.job, message="Job run (stub)")


# NOTE: Этот роутер содержит упрощённые версии automation эндпоинтов.
# Для полной реализации нужно передать scheduler instance из main.py
# и перенести job функции из src/automation.py

