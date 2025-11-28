"""
Healthchecks.io Integration for Uptime Monitoring

Отправляет ping каждые 5 минут, чтобы подтвердить что сервис работает.
Если ping не приходит - получаете alert (email/SMS/Telegram).
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL")


def ping_healthcheck(status: str = "success") -> bool:
    """
    Отправляет ping в healthchecks.io.
    
    Args:
        status: Статус пинга:
            - "success" (или пусто) - всё работает
            - "fail" - есть проблемы
            - "start" - задача началась
            - "log" - текстовый лог
    
    Returns:
        True если ping успешен, False иначе
    """
    if not HEALTHCHECK_URL:
        return False
    
    try:
        import httpx
        
        # Определяем URL в зависимости от статуса
        if status == "success" or not status:
            url = HEALTHCHECK_URL
        elif status == "fail":
            url = f"{HEALTHCHECK_URL}/fail"
        elif status == "start":
            url = f"{HEALTHCHECK_URL}/start"
        elif status == "log":
            url = f"{HEALTHCHECK_URL}/log"
        else:
            url = HEALTHCHECK_URL
        
        response = httpx.get(url, timeout=5)
        
        if response.status_code == 200:
            logger.debug(f"[healthcheck] Ping successful ({status})")
            return True
        else:
            logger.warning(f"[healthcheck] Ping failed: {response.status_code}")
            return False
    
    except ImportError:
        logger.warning("[healthcheck] httpx not installed, run: pip install httpx")
        return False
    
    except Exception as e:
        logger.error(f"[healthcheck] Ping error: {e}")
        return False


def ping_with_data(data: str) -> bool:
    """
    Отправляет ping с текстовыми данными (log).
    
    Args:
        data: Текст для логирования (до 10KB)
    
    Example:
        ping_with_data("Paper Monitor: 5 signals generated, equity $10,500")
    """
    if not HEALTHCHECK_URL:
        return False
    
    try:
        import httpx
        
        url = f"{HEALTHCHECK_URL}/log"
        
        response = httpx.post(
            url,
            data=data[:10000],  # Максимум 10KB
            timeout=5,
            headers={"Content-Type": "text/plain"}
        )
        
        return response.status_code == 200
    
    except Exception as e:
        logger.error(f"[healthcheck] Ping with data error: {e}")
        return False


def create_check_summary() -> str:
    """
    Создаёт краткую сводку о состоянии системы для healthcheck log.
    
    Returns:
        Строка с информацией о системе
    """
    try:
        from .trade import paper_get_equity, paper_get_positions
        from .paper_trading_monitor import get_monitor_status
        from .risk_management import get_risk_status
        
        equity_data = paper_get_equity()
        positions = paper_get_positions()
        monitor_status = get_monitor_status()
        risk_status = get_risk_status()
        
        summary = []
        summary.append(f"[{datetime.utcnow().isoformat()}]")
        summary.append(f"Equity: ${equity_data.get('equity', 0):.2f}")
        summary.append(f"Positions: {len(positions)}")
        summary.append(f"Paper Monitor: {'ON' if monitor_status.get('enabled') else 'OFF'}")
        summary.append(f"Risk Management: {'ON' if risk_status.get('enabled') else 'OFF'}")
        summary.append(f"Exposure: {risk_status.get('current_exposure', {}).get('exposure_pct', 0):.1f}%")
        
        return " | ".join(summary)
    
    except Exception as e:
        logger.error(f"[healthcheck] Error creating summary: {e}")
        return f"[{datetime.utcnow().isoformat()}] Error: {e}"


def healthcheck_with_system_status() -> bool:
    """
    Отправляет ping с полной информацией о системе.
    
    Удобно для мониторинга состояния системы в healthchecks.io logs.
    """
    summary = create_check_summary()
    return ping_with_data(summary)

