"""
API endpoints для Real-time Paper Trading Monitor
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from ..dependencies import require_api_key
from ..paper_trading_monitor import (
    load_monitor_state,
    save_monitor_state,
    run_monitor_update,
    get_equity_chart_data,
    get_monitor_status
)

router = APIRouter(prefix="/paper-monitor", tags=["Paper Trading Monitor"])


# ============================
# Pydantic модели
# ============================

class MonitorConfig(BaseModel):
    """Конфигурация монитора"""
    enabled: bool = Field(False, description="Включен ли монитор")
    update_interval_minutes: int = Field(15, ge=1, le=1440, description="Интервал обновления в минутах")
    symbols: List[str] = Field(["BTC/USDT"], description="Список символов для мониторинга")
    exchange: str = Field("bybit", description="Биржа")
    timeframe: str = Field("1h", description="Таймфрейм")
    auto_execute: bool = Field(False, description="Автоматическое исполнение сигналов")
    use_ml_model: bool = Field(True, description="Использовать ML модель (True) или EMA Crossover (False)")
    notifications: bool = Field(True, description="Отправлять уведомления")


class MonitorStatus(BaseModel):
    """Статус монитора"""
    enabled: bool
    last_update: Optional[str]
    update_interval_minutes: int
    auto_execute: bool
    notifications: bool
    symbols: List[str]
    stats: Dict
    equity: Dict
    positions_count: int


# ============================
# API Endpoints
# ============================

@router.get("/status", response_model=MonitorStatus)
async def get_status(_=Depends(require_api_key)):
    """
    Получить текущий статус real-time монитора.
    
    Возвращает:
    - Состояние монитора (включен/выключен)
    - Последнее обновление
    - Статистика (кол-во обновлений, сигналов, ошибок)
    - Текущий equity
    - Количество открытых позиций
    """
    try:
        status = get_monitor_status()
        return MonitorStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.post("/config")
async def update_config(config: MonitorConfig, _=Depends(require_api_key)):
    """
    Обновить конфигурацию монитора.
    
    Параметры:
    - enabled: Включить/выключить монитор
    - update_interval_minutes: Интервал обновления (1-1440 минут)
    - symbols: Список символов для мониторинга
    - exchange: Биржа (bybit, binance)
    - timeframe: Таймфрейм (1h, 4h, 1d)
    - auto_execute: Автоматически исполнять сигналы
    - notifications: Отправлять Telegram уведомления
    """
    try:
        state = load_monitor_state()
        
        # Обновляем конфигурацию
        state["enabled"] = config.enabled
        state["update_interval_minutes"] = config.update_interval_minutes
        state["symbols"] = config.symbols
        state["exchange"] = config.exchange
        state["timeframe"] = config.timeframe
        state["auto_execute"] = config.auto_execute
        state["use_ml_model"] = config.use_ml_model
        state["notifications"] = config.notifications
        
        save_monitor_state(state)
        
        return {
            "status": "ok",
            "message": "Monitor configuration updated",
            "config": config.dict()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@router.post("/start")
async def start_monitor(_=Depends(require_api_key)):
    """
    Запустить real-time монитор.
    
    Монитор будет автоматически:
    1. Обновлять цены каждые N минут
    2. Генерировать сигналы на новых данных
    3. Обновлять equity позиций
    4. Отправлять уведомления (если включено)
    5. Автоматически исполнять сигналы (если включено)
    """
    try:
        state = load_monitor_state()
        state["enabled"] = True
        save_monitor_state(state)
        
        return {
            "status": "ok",
            "message": "Monitor started",
            "config": {
                "update_interval_minutes": state.get("update_interval_minutes", 15),
                "auto_execute": state.get("auto_execute", False)
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting monitor: {str(e)}")


@router.post("/stop")
async def stop_monitor(_=Depends(require_api_key)):
    """
    Остановить real-time монитор.
    
    Прекращает автоматические обновления и генерацию сигналов.
    """
    try:
        state = load_monitor_state()
        state["enabled"] = False
        save_monitor_state(state)
        
        return {
            "status": "ok",
            "message": "Monitor stopped"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping monitor: {str(e)}")


@router.post("/update")
async def manual_update(background_tasks: BackgroundTasks, _=Depends(require_api_key)):
    """
    Запустить обновление монитора вручную.
    
    Выполняет один цикл обновления:
    1. Обновляет цены
    2. Генерирует сигналы
    3. Обновляет equity
    4. Сохраняет snapshot
    """
    try:
        # Запускаем обновление в фоне
        background_tasks.add_task(run_monitor_update)
        
        return {
            "status": "ok",
            "message": "Update started in background"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting update: {str(e)}")


@router.get("/equity/chart")
async def get_equity_chart(
    hours: int = 24,
    _=Depends(require_api_key)
):
    """
    Получить данные для графика equity за последние N часов.
    
    Args:
        hours: Количество часов истории (по умолчанию 24)
        
    Returns:
        Dict с массивами: timestamps, equity, pnl, pnl_pct
    """
    try:
        if hours < 1 or hours > 720:  # Максимум 30 дней
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")
        
        data = get_equity_chart_data(hours)
        
        return {
            "status": "ok",
            "hours": hours,
            "data_points": len(data["timestamps"]),
            "data": data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chart data: {str(e)}")


@router.get("/equity/summary")
async def get_equity_summary(_=Depends(require_api_key)):
    """
    Получить сводку по equity за разные периоды.
    
    Returns:
        Статистика за 1h, 24h, 7d, 30d
    """
    try:
        from datetime import datetime, timedelta
        from ..paper_trading_monitor import load_equity_history
        
        history = load_equity_history()
        
        if not history:
            return {
                "status": "ok",
                "message": "No history available",
                "summary": {}
            }
        
        now = datetime.utcnow()
        periods = {
            "1h": 1,
            "24h": 24,
            "7d": 24 * 7,
            "30d": 24 * 30
        }
        
        summary = {}
        
        for period_name, hours in periods.items():
            cutoff = now - timedelta(hours=hours)
            period_data = [
                h for h in history
                if datetime.fromisoformat(h["timestamp"]) >= cutoff
            ]
            
            if period_data:
                first = period_data[0]
                last = period_data[-1]
                
                equity_change = last.get("equity", 0) - first.get("equity", 0)
                equity_change_pct = (
                    (equity_change / first.get("equity", 1)) * 100
                    if first.get("equity", 0) > 0 else 0
                )
                
                summary[period_name] = {
                    "equity_start": first.get("equity", 0),
                    "equity_end": last.get("equity", 0),
                    "change": equity_change,
                    "change_pct": equity_change_pct,
                    "data_points": len(period_data)
                }
            else:
                summary[period_name] = {
                    "equity_start": 0,
                    "equity_end": 0,
                    "change": 0,
                    "change_pct": 0,
                    "data_points": 0
                }
        
        return {
            "status": "ok",
            "timestamp": now.isoformat(),
            "summary": summary
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")


@router.get("/stats")
async def get_stats(_=Depends(require_api_key)):
    """
    Получить статистику монитора.
    
    Returns:
        Полная статистика работы монитора
    """
    try:
        state = load_monitor_state()
        stats = state.get("stats", {})
        
        return {
            "status": "ok",
            "stats": {
                "total_updates": stats.get("total_updates", 0),
                "total_signals": stats.get("total_signals", 0),
                "last_signal_time": stats.get("last_signal_time"),
                "errors": stats.get("errors", 0),
                "last_update": state.get("last_update")
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.delete("/history")
async def clear_history(_=Depends(require_api_key)):
    """
    Очистить историю equity.
    
    ВНИМАНИЕ: Это действие необратимо!
    """
    try:
        from ..paper_trading_monitor import EQUITY_HISTORY_PATH
        
        if EQUITY_HISTORY_PATH.exists():
            EQUITY_HISTORY_PATH.write_text("[]", encoding="utf-8")
        
        return {
            "status": "ok",
            "message": "Equity history cleared"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")

