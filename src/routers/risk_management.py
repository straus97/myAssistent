"""
API endpoints для Advanced Risk Management
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from ..dependencies import require_api_key, get_db
from ..risk_management import (
    load_risk_config,
    save_risk_config,
    run_risk_checks,
    get_risk_status,
    load_trailing_stops,
    save_trailing_stops
)

router = APIRouter(prefix="/risk-management", tags=["Risk Management"])


# ============================
# Pydantic модели
# ============================

class StopLossConfig(BaseModel):
    """Конфигурация Stop-Loss"""
    enabled: bool = Field(True, description="Включен ли stop-loss")
    percentage: float = Field(0.02, ge=0.001, le=0.50, description="Процент убытка для триггера (0.02 = -2%)")
    notify: bool = Field(True, description="Отправлять уведомления")


class TakeProfitConfig(BaseModel):
    """Конфигурация Take-Profit"""
    enabled: bool = Field(True, description="Включен ли take-profit")
    percentage: float = Field(0.05, ge=0.001, le=1.0, description="Процент прибыли для триггера (0.05 = +5%)")
    notify: bool = Field(True, description="Отправлять уведомления")


class TrailingStopConfig(BaseModel):
    """Конфигурация Trailing Stop"""
    enabled: bool = Field(False, description="Включен ли trailing stop")
    activation_percentage: float = Field(
        0.03, ge=0.001, le=1.0,
        description="Процент прибыли для активации trailing stop (0.03 = +3%)"
    )
    trail_percentage: float = Field(
        0.015, ge=0.001, le=0.50,
        description="Процент trailing от максимума (0.015 = 1.5%)"
    )
    notify: bool = Field(True, description="Отправлять уведомления")


class MaxExposureConfig(BaseModel):
    """Конфигурация Max Exposure"""
    enabled: bool = Field(True, description="Включен ли контроль exposure")
    percentage: float = Field(0.50, ge=0.01, le=1.0, description="Максимальный процент капитала в позициях (0.50 = 50%)")
    block_new_trades: bool = Field(True, description="Блокировать новые сделки при превышении")
    notify: bool = Field(True, description="Отправлять уведомления")


class PositionHealthConfig(BaseModel):
    """Конфигурация Position Health"""
    check_interval_minutes: int = Field(5, ge=1, le=60, description="Интервал проверки в минутах")
    max_position_age_hours: float = Field(72, ge=0, le=720, description="Максимальный возраст позиции в часах (0 = отключено)")
    notify_unhealthy: bool = Field(True, description="Уведомлять о нездоровых позициях")


class RiskManagementConfig(BaseModel):
    """Полная конфигурация Risk Management"""
    enabled: bool = Field(True, description="Включен ли risk management")
    stop_loss: Optional[StopLossConfig] = None
    take_profit: Optional[TakeProfitConfig] = None
    trailing_stop: Optional[TrailingStopConfig] = None
    max_exposure: Optional[MaxExposureConfig] = None
    position_health: Optional[PositionHealthConfig] = None


# ============================
# API Endpoints
# ============================

@router.get("/status")
async def get_status(_=Depends(require_api_key)):
    """
    Получить текущий статус risk management.
    
    Returns:
        - Текущая конфигурация
        - Текущий exposure
        - Активные позиции
        - Активные trailing stops
    """
    try:
        status = get_risk_status()
        return {
            "status": "ok",
            **status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.get("/config")
async def get_config(_=Depends(require_api_key)):
    """
    Получить текущую конфигурацию risk management.
    """
    try:
        config = load_risk_config()
        return {
            "status": "ok",
            "config": config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


@router.post("/config")
async def update_config(
    config: RiskManagementConfig,
    _=Depends(require_api_key)
):
    """
    Обновить конфигурацию risk management.
    
    Parameters:
        - enabled: Включить/выключить risk management
        - stop_loss: Конфигурация stop-loss
        - take_profit: Конфигурация take-profit
        - trailing_stop: Конфигурация trailing stop
        - max_exposure: Конфигурация max exposure
        - position_health: Конфигурация position health
    """
    try:
        current_config = load_risk_config()
        
        # Обновляем только предоставленные поля
        updated_config = {
            "enabled": config.enabled,
            "stop_loss": config.stop_loss.dict() if config.stop_loss else current_config.get("stop_loss"),
            "take_profit": config.take_profit.dict() if config.take_profit else current_config.get("take_profit"),
            "trailing_stop": config.trailing_stop.dict() if config.trailing_stop else current_config.get("trailing_stop"),
            "max_exposure": config.max_exposure.dict() if config.max_exposure else current_config.get("max_exposure"),
            "position_health": config.position_health.dict() if config.position_health else current_config.get("position_health")
        }
        
        save_risk_config(updated_config)
        
        return {
            "status": "ok",
            "message": "Risk management configuration updated",
            "config": updated_config
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@router.post("/enable")
async def enable(_=Depends(require_api_key)):
    """
    Включить risk management.
    """
    try:
        config = load_risk_config()
        config["enabled"] = True
        save_risk_config(config)
        
        return {
            "status": "ok",
            "message": "Risk management enabled"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enabling: {str(e)}")


@router.post("/disable")
async def disable(_=Depends(require_api_key)):
    """
    Выключить risk management.
    
    ВНИМАНИЕ: Это отключит все автоматические проверки!
    """
    try:
        config = load_risk_config()
        config["enabled"] = False
        save_risk_config(config)
        
        return {
            "status": "ok",
            "message": "Risk management disabled",
            "warning": "All automatic checks are now disabled!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disabling: {str(e)}")


@router.post("/check")
async def run_checks(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_api_key)
):
    """
    Запустить проверки risk management вручную.
    
    Проверяет все открытые позиции на:
    - Stop-loss условия
    - Take-profit условия
    - Trailing stop условия
    - Возраст позиций
    - Max exposure
    
    Автоматически закрывает позиции при нарушении правил.
    """
    try:
        # Запускаем в фоне
        background_tasks.add_task(run_risk_checks, db)
        
        return {
            "status": "ok",
            "message": "Risk checks started in background"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting checks: {str(e)}")


@router.get("/trailing-stops")
async def get_trailing_stops(_=Depends(require_api_key)):
    """
    Получить текущие активные trailing stops.
    
    Returns:
        Dict с активными trailing stops для каждой позиции
    """
    try:
        stops = load_trailing_stops()
        
        return {
            "status": "ok",
            "count": len(stops),
            "trailing_stops": stops
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting trailing stops: {str(e)}")


@router.delete("/trailing-stops")
async def clear_trailing_stops(_=Depends(require_api_key)):
    """
    Очистить все trailing stops.
    
    ВНИМАНИЕ: Это удалит все активные trailing stops!
    """
    try:
        save_trailing_stops({})
        
        return {
            "status": "ok",
            "message": "All trailing stops cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing trailing stops: {str(e)}")


@router.delete("/trailing-stops/{position_key}")
async def delete_trailing_stop(
    position_key: str,
    _=Depends(require_api_key)
):
    """
    Удалить конкретный trailing stop.
    
    Parameters:
        position_key: Ключ позиции (format: exchange_symbol_timeframe)
    """
    try:
        stops = load_trailing_stops()
        
        if position_key not in stops:
            raise HTTPException(status_code=404, detail=f"Trailing stop for {position_key} not found")
        
        del stops[position_key]
        save_trailing_stops(stops)
        
        return {
            "status": "ok",
            "message": f"Trailing stop for {position_key} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting trailing stop: {str(e)}")


@router.get("/exposure")
async def get_exposure(_=Depends(require_api_key)):
    """
    Получить текущий exposure портфеля.
    
    Returns:
        - Equity
        - Positions value
        - Exposure percentage
        - Max allowed percentage
        - Status (OK/WARNING)
    """
    try:
        status = get_risk_status()
        exposure = status.get("current_exposure", {})
        
        return {
            "status": "ok",
            **exposure
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting exposure: {str(e)}")


@router.get("/recommendations")
async def get_recommendations(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """
    Получить рекомендации по risk management для текущих позиций.
    
    Returns:
        Список рекомендаций для каждой позиции
    """
    try:
        from ..trade import paper_get_positions
        from ..risk_management import (
            get_current_price,
            check_stop_loss,
            check_take_profit,
            check_position_age,
            load_risk_config
        )
        
        config = load_risk_config()
        positions = paper_get_positions()
        
        recommendations = []
        
        for position in positions:
            exchange = position.get("exchange", "")
            symbol = position.get("symbol", "")
            timeframe = position.get("timeframe", "1h")
            entry_price = float(position.get("avg_price", 0))
            
            if entry_price <= 0:
                continue
            
            current_price = get_current_price(db, exchange, symbol, timeframe)
            if current_price is None:
                continue
            
            current_pnl_pct = ((current_price / entry_price) - 1) * 100
            
            rec = {
                "symbol": symbol,
                "entry_price": entry_price,
                "current_price": current_price,
                "pnl_pct": current_pnl_pct,
                "warnings": [],
                "suggestions": []
            }
            
            # Проверки
            should_close_sl, sl_reason = check_stop_loss(position, current_price, config)
            if should_close_sl:
                rec["warnings"].append(sl_reason)
            
            should_close_tp, tp_reason = check_take_profit(position, current_price, config)
            if should_close_tp:
                rec["warnings"].append(tp_reason)
            
            should_close_age, age_reason = check_position_age(position, config)
            if should_close_age:
                rec["warnings"].append(age_reason)
            
            # Suggestions
            if -0.01 < current_pnl_pct < 0.01:
                rec["suggestions"].append("Position near breakeven - consider setting trailing stop")
            
            if current_pnl_pct < -0.015 and not config.get("stop_loss", {}).get("enabled"):
                rec["suggestions"].append("Position losing - consider enabling stop-loss")
            
            if current_pnl_pct > 0.03 and not config.get("trailing_stop", {}).get("enabled"):
                rec["suggestions"].append("Good profit - consider enabling trailing stop to protect gains")
            
            recommendations.append(rec)
        
        return {
            "status": "ok",
            "recommendations": recommendations
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")

