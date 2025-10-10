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
    from src.main import scheduler
    
    jobs = scheduler.get_jobs()
    return ok(jobs=[
        {
            "id": j.id,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            "trigger": str(j.trigger),
        }
        for j in jobs
    ])


class AutomationRunRequest(BaseModel):
    """Запрос на разовый запуск фоновой задачи"""

    action: Optional[Literal["signal_once", "scan_watchlist", "train_missing"]] = None
    job: Optional[Literal["fetch_prices", "fetch_news", "analyze_news", "train_models", "make_signals", "news_radar"]] = None


@router.post("/run")
def automation_run(req: AutomationRunRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Разовый запуск фоновой задачи"""
    from src.main import (
        job_fetch_news, job_analyze_news, job_fetch_prices,
        job_train_models, job_make_signals, job_build_report,
        job_discover_watchlist, job_news_radar
    )
    
    # Маппинг job names на функции
    job_map = {
        "fetch_news": job_fetch_news,
        "analyze_news": job_analyze_news,
        "fetch_prices": job_fetch_prices,
        "train_models": job_train_models,
        "make_signals": job_make_signals,
        "news_radar": job_news_radar,
        "build_report": job_build_report,
        "discover_watchlist": job_discover_watchlist,
    }
    
    # Если указан job, запускаем его
    if req.job and req.job in job_map:
        try:
            job_map[req.job]()
            return ok(job=req.job, status="executed")
        except Exception as e:
            return {"status": "error", "job": req.job, "detail": str(e)}
    
    # Если указан action - выполняем специфичное действие
    if req.action:
        if req.action == "signal_once":
            # Генерация одного сигнала
            try:
                job_make_signals()
                return ok(action=req.action, status="executed")
            except Exception as e:
                return {"status": "error", "action": req.action, "detail": str(e)}
        
        elif req.action == "scan_watchlist":
            # Сканирование watchlist
            try:
                job_discover_watchlist()
                return ok(action=req.action, status="executed")
            except Exception as e:
                return {"status": "error", "action": req.action, "detail": str(e)}
        
        elif req.action == "train_missing":
            # Обучение недостающих моделей
            try:
                job_train_models()
                return ok(action=req.action, status="executed")
            except Exception as e:
                return {"status": "error", "action": req.action, "detail": str(e)}
    
    return {"status": "error", "detail": "Укажите job или action"}


# NOTE: Этот роутер содержит упрощённые версии automation эндпоинтов.
# Для полной реализации нужно передать scheduler instance из main.py
# и перенести job функции из src/automation.py

