"""
Advanced Risk Management Module

Автоматическая защита капитала через:
1. Stop-Loss - закрытие при убытке
2. Take-Profit - закрытие при прибыли
3. Trailing Stop - динамический stop-loss
4. Max Exposure - ограничение общего размера позиций
5. Position Health Monitor - проверка состояния всех позиций
"""

from __future__ import annotations
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from .db import Price
from .trade import paper_get_positions, paper_get_equity, paper_close_pair
from .notify import send_telegram

logger = logging.getLogger(__name__)

# Путь к конфигурации risk management
RISK_CONFIG_PATH = Path("artifacts/config/risk_management.json")
RISK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Путь к состоянию trailing stops
TRAILING_STOPS_PATH = Path("artifacts/state/trailing_stops.json")
TRAILING_STOPS_PATH.parent.mkdir(parents=True, exist_ok=True)


DEFAULT_CONFIG = {
    "enabled": True,
    "stop_loss": {
        "enabled": True,
        "percentage": 0.02,  # -2% от entry price
        "notify": True
    },
    "take_profit": {
        "enabled": True,
        "percentage": 0.05,  # +5% от entry price
        "notify": True
    },
    "trailing_stop": {
        "enabled": False,  # По умолчанию выключен
        "activation_percentage": 0.03,  # Активируется при +3% прибыли
        "trail_percentage": 0.015,  # Trailing на 1.5% от максимума
        "notify": True
    },
    "max_exposure": {
        "enabled": True,
        "percentage": 0.50,  # Максимум 50% капитала в позициях
        "block_new_trades": True,  # Блокировать новые сделки при превышении
        "notify": True
    },
    "position_health": {
        "check_interval_minutes": 5,
        "max_position_age_hours": 72,  # Закрывать позиции старше 72 часов
        "notify_unhealthy": True
    }
}


def load_risk_config() -> Dict:
    """Загружает конфигурацию risk management"""
    if RISK_CONFIG_PATH.exists():
        try:
            cfg = json.loads(RISK_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    
    save_risk_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_risk_config(config: Dict) -> None:
    """Сохраняет конфигурацию risk management"""
    RISK_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_trailing_stops() -> Dict:
    """Загружает состояние trailing stops"""
    if TRAILING_STOPS_PATH.exists():
        try:
            return json.loads(TRAILING_STOPS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_trailing_stops(stops: Dict) -> None:
    """Сохраняет состояние trailing stops"""
    TRAILING_STOPS_PATH.write_text(
        json.dumps(stops, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_current_price(db: Session, exchange: str, symbol: str, timeframe: str) -> Optional[float]:
    """Получает текущую цену актива"""
    try:
        latest_price = (
            db.query(Price)
            .filter(
                Price.exchange == exchange,
                Price.symbol == symbol,
                Price.timeframe == timeframe
            )
            .order_by(Price.ts.desc())
            .first()
        )
        
        if latest_price:
            return float(latest_price.close)
        
        return None
    except Exception as e:
        logger.error(f"[RISK] Error getting current price: {e}")
        return None


def check_stop_loss(
    position: Dict,
    current_price: float,
    config: Dict
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет условие stop-loss.
    
    Returns:
        (should_close, reason)
    """
    if not config.get("stop_loss", {}).get("enabled", True):
        return False, None
    
    entry_price = float(position.get("avg_price", 0))
    if entry_price <= 0:
        return False, None
    
    stop_loss_pct = float(config.get("stop_loss", {}).get("percentage", 0.02))
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    
    if current_price <= stop_loss_price:
        loss_pct = ((current_price / entry_price) - 1) * 100
        reason = f"Stop-Loss triggered: {loss_pct:.2f}% (price ${current_price:.2f} <= SL ${stop_loss_price:.2f})"
        return True, reason
    
    return False, None


def check_take_profit(
    position: Dict,
    current_price: float,
    config: Dict
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет условие take-profit.
    
    Returns:
        (should_close, reason)
    """
    if not config.get("take_profit", {}).get("enabled", True):
        return False, None
    
    entry_price = float(position.get("avg_price", 0))
    if entry_price <= 0:
        return False, None
    
    take_profit_pct = float(config.get("take_profit", {}).get("percentage", 0.05))
    take_profit_price = entry_price * (1 + take_profit_pct)
    
    if current_price >= take_profit_price:
        profit_pct = ((current_price / entry_price) - 1) * 100
        reason = f"Take-Profit triggered: +{profit_pct:.2f}% (price ${current_price:.2f} >= TP ${take_profit_price:.2f})"
        return True, reason
    
    return False, None


def check_trailing_stop(
    position: Dict,
    current_price: float,
    config: Dict,
    trailing_stops: Dict
) -> Tuple[bool, Optional[str], Dict]:
    """
    Проверяет условие trailing stop.
    
    Trailing stop активируется когда прибыль достигает activation_percentage,
    и затем движется за ценой на trail_percentage от максимума.
    
    Returns:
        (should_close, reason, updated_trailing_stops)
    """
    if not config.get("trailing_stop", {}).get("enabled", False):
        return False, None, trailing_stops
    
    entry_price = float(position.get("avg_price", 0))
    if entry_price <= 0:
        return False, None, trailing_stops
    
    ts_config = config.get("trailing_stop", {})
    activation_pct = float(ts_config.get("activation_percentage", 0.03))
    trail_pct = float(ts_config.get("trail_percentage", 0.015))
    
    # Ключ для позиции
    pos_key = f"{position['exchange']}_{position['symbol']}_{position.get('timeframe', '1h')}"
    
    # Текущая прибыль
    profit_pct = (current_price / entry_price) - 1
    
    # Если trailing stop еще не активирован
    if pos_key not in trailing_stops:
        if profit_pct >= activation_pct:
            # Активируем trailing stop
            trailing_stops[pos_key] = {
                "max_price": current_price,
                "trail_stop_price": current_price * (1 - trail_pct),
                "activated_at": datetime.utcnow().isoformat(),
                "entry_price": entry_price
            }
            logger.info(f"[RISK] Trailing stop activated for {pos_key} at ${current_price:.2f}")
        return False, None, trailing_stops
    
    # Trailing stop активирован - обновляем максимум и stop цену
    ts_data = trailing_stops[pos_key]
    max_price = max(float(ts_data.get("max_price", 0)), current_price)
    trail_stop_price = max_price * (1 - trail_pct)
    
    trailing_stops[pos_key]["max_price"] = max_price
    trailing_stops[pos_key]["trail_stop_price"] = trail_stop_price
    
    # Проверяем triggering
    if current_price <= trail_stop_price:
        profit_at_close = ((current_price / entry_price) - 1) * 100
        reason = f"Trailing Stop triggered: +{profit_at_close:.2f}% (price ${current_price:.2f} <= TS ${trail_stop_price:.2f}, max was ${max_price:.2f})"
        
        # Удаляем из tracking после закрытия
        del trailing_stops[pos_key]
        
        return True, reason, trailing_stops
    
    return False, None, trailing_stops


def check_max_exposure(config: Dict) -> Tuple[bool, Optional[str]]:
    """
    Проверяет максимальный exposure портфеля.
    
    Returns:
        (exposure_ok, warning_message)
    """
    if not config.get("max_exposure", {}).get("enabled", True):
        return True, None
    
    try:
        equity_data = paper_get_equity()
        equity = float(equity_data.get("equity", 0))
        cash = float(equity_data.get("cash", 0))
        
        if equity <= 0:
            return True, None
        
        positions_value = equity - cash
        exposure_pct = (positions_value / equity) if equity > 0 else 0
        
        max_exposure_pct = float(config.get("max_exposure", {}).get("percentage", 0.50))
        
        if exposure_pct > max_exposure_pct:
            message = f"Max exposure exceeded: {exposure_pct*100:.1f}% > {max_exposure_pct*100:.1f}%"
            return False, message
        
        return True, None
    
    except Exception as e:
        logger.error(f"[RISK] Error checking max exposure: {e}")
        return True, None


def check_position_age(position: Dict, config: Dict) -> Tuple[bool, Optional[str]]:
    """
    Проверяет возраст позиции.
    
    Returns:
        (should_close, reason)
    """
    health_config = config.get("position_health", {})
    max_age_hours = float(health_config.get("max_position_age_hours", 72))
    
    if max_age_hours <= 0:
        return False, None
    
    try:
        # Получаем время открытия позиции
        opened_at_str = position.get("opened_at")
        if not opened_at_str:
            return False, None
        
        opened_at = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        age = datetime.utcnow() - opened_at.replace(tzinfo=None)
        age_hours = age.total_seconds() / 3600
        
        if age_hours > max_age_hours:
            reason = f"Position too old: {age_hours:.1f}h > {max_age_hours:.1f}h"
            return True, reason
        
        return False, None
    
    except Exception as e:
        logger.error(f"[RISK] Error checking position age: {e}")
        return False, None


def run_risk_checks(db: Session) -> Dict:
    """
    Запускает все проверки risk management для всех открытых позиций.
    
    Returns:
        Dict с результатами проверок и действиями
    """
    start_time = datetime.utcnow()
    
    config = load_risk_config()
    
    if not config.get("enabled", True):
        return {
            "status": "disabled",
            "message": "Risk management is disabled"
        }
    
    logger.info("[RISK] Running risk checks...")
    
    results = {
        "status": "ok",
        "timestamp": start_time.isoformat(),
        "positions_checked": 0,
        "positions_closed": 0,
        "actions": [],
        "warnings": [],
        "errors": []
    }
    
    try:
        # Получаем все позиции
        positions = paper_get_positions()
        results["positions_checked"] = len(positions)
        
        if not positions:
            logger.info("[RISK] No open positions to check")
            return results
        
        # Проверка max exposure
        exposure_ok, exposure_warning = check_max_exposure(config)
        if not exposure_ok:
            results["warnings"].append(exposure_warning)
            # Отправляем более понятное уведомление
            if config.get("max_exposure", {}).get("notify", True):
                equity_data = paper_get_equity()
                equity = float(equity_data.get("equity", 0))
                positions_value = equity - float(equity_data.get("cash", 0))
                exposure_pct = (positions_value / equity * 100) if equity > 0 else 0
                max_pct = config.get("max_exposure", {}).get("percentage", 0.50) * 100
                
                message = "⚠️ РИСК МЕНЕДЖЕР\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                message += "🚨 ВЫСОКИЙ EXPOSURE\n\n"
                message += "📊 ТЕКУЩИЙ СТАТУС:\n"
                message += f"• Exposure: {exposure_pct:.1f}% (лимит: {max_pct:.0f}%)\n"
                message += f"• Превышение: {exposure_pct - max_pct:.1f}%\n\n"
                message += "💰 КАПИТАЛ:\n"
                message += f"• Всего: ${equity:,.2f}\n"
                message += f"• В позициях: ${positions_value:,.2f}\n"
                message += f"• Свободно: ${equity - positions_value:,.2f}\n\n"
                message += "🛡️ ЗАЩИТНЫЕ МЕРЫ:\n"
                message += "✓ Новые сделки ЗАБЛОКИРОВАНЫ\n"
                message += "✓ Открытые позиции под контролем\n"
                message += "✓ SL/TP активны\n\n"
                message += "💡 РЕКОМЕНДАЦИЯ:\n"
                message += "Дождаться закрытия позиций по Stop Loss / Take Profit"
                
                send_telegram(message)
        
        # Загружаем trailing stops
        trailing_stops = load_trailing_stops()
        trailing_stops_updated = False
        
        # Проверяем каждую позицию
        for position in positions:
            exchange = position.get("exchange", "")
            symbol = position.get("symbol", "")
            timeframe = position.get("timeframe", "1h")
            entry_price = float(position.get("avg_price", 0))
            
            if entry_price <= 0:
                continue
            
            # Получаем текущую цену
            current_price = get_current_price(db, exchange, symbol, timeframe)
            if current_price is None:
                results["warnings"].append(f"No price data for {symbol}")
                continue
            
            # Текущий PnL
            current_pnl_pct = ((current_price / entry_price) - 1) * 100
            
            action = None
            reason = None
            
            # 1. Проверка Stop-Loss
            should_close_sl, sl_reason = check_stop_loss(position, current_price, config)
            if should_close_sl:
                action = "stop_loss"
                reason = sl_reason
            
            # 2. Проверка Take-Profit (если не triggered SL)
            if not action:
                should_close_tp, tp_reason = check_take_profit(position, current_price, config)
                if should_close_tp:
                    action = "take_profit"
                    reason = tp_reason
            
            # 3. Проверка Trailing Stop (если не triggered SL/TP)
            if not action:
                should_close_ts, ts_reason, new_trailing_stops = check_trailing_stop(
                    position, current_price, config, trailing_stops
                )
                if new_trailing_stops != trailing_stops:
                    trailing_stops = new_trailing_stops
                    trailing_stops_updated = True
                
                if should_close_ts:
                    action = "trailing_stop"
                    reason = ts_reason
            
            # 4. Проверка возраста позиции (если не triggered ничего)
            if not action:
                should_close_age, age_reason = check_position_age(position, config)
                if should_close_age:
                    action = "position_too_old"
                    reason = age_reason
            
            # Если нужно закрыть позицию
            if action:
                try:
                    close_result = paper_close_pair(
                        exchange=exchange,
                        symbol=symbol,
                        timeframe=timeframe,
                        price=current_price,
                        ts_iso=datetime.utcnow().isoformat()
                    )
                    
                    results["positions_closed"] += 1
                    results["actions"].append({
                        "action": action,
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "close_price": current_price,
                        "pnl_pct": current_pnl_pct,
                        "reason": reason,
                        "result": close_result
                    })
                    
                    logger.info(f"[RISK] Closed {symbol}: {reason}")
                    
                    # Отправляем уведомление
                    if config.get(action.split("_")[0], {}).get("notify", True):
                        # Улучшенное форматирование уведомлений
                        action_emoji = {
                            "stop_loss": "🛑",
                            "take_profit": "🎯",
                            "trailing_stop": "📉",
                            "max_age": "⏰"
                        }.get(action, "⚠️")
                        
                        action_name = {
                            "stop_loss": "STOP LOSS",
                            "take_profit": "TAKE PROFIT",
                            "trailing_stop": "TRAILING STOP",
                            "max_age": "MAX AGE"
                        }.get(action, action.upper().replace("_", " "))
                        
                        pnl_emoji = "✅" if current_pnl_pct > 0 else "❌"
                        
                        message = f"{action_emoji} {action_name}\n"
                        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                        message += f"💰 Пара: {symbol}\n"
                        message += f"{pnl_emoji} P&L: {current_pnl_pct:+.2f}%\n\n"
                        message += "📊 ДЕТАЛИ:\n"
                        message += f"• Вход: ${entry_price:.4f}\n"
                        message += f"• Выход: ${current_price:.4f}\n\n"
                        message += f"📝 Причина:\n{reason}\n\n"
                        
                        # Добавляем совет
                        if action == "stop_loss":
                            message += "💡 СОВЕТ:\nУбыток зафиксирован, защищая капитал"
                        elif action == "take_profit":
                            message += "💡 СОВЕТ:\nПрибыль зафиксирована, поздравляем!"
                        elif action == "trailing_stop":
                            message += "💡 СОВЕТ:\nПрибыль частично зафиксирована"
                        
                        send_telegram(message)
                    
                    # Удаляем из trailing stops если был
                    pos_key = f"{exchange}_{symbol}_{timeframe}"
                    if pos_key in trailing_stops:
                        del trailing_stops[pos_key]
                        trailing_stops_updated = True
                
                except Exception as e:
                    error_msg = f"Error closing {symbol}: {e}"
                    results["errors"].append(error_msg)
                    logger.error(f"[RISK] {error_msg}")
        
        # Сохраняем trailing stops если обновились
        if trailing_stops_updated:
            save_trailing_stops(trailing_stops)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        results["duration_seconds"] = duration
        
        logger.info(f"[RISK] Checks completed: {results['positions_closed']}/{results['positions_checked']} closed")
    
    except Exception as e:
        logger.error(f"[RISK] Error in risk checks: {e}")
        results["status"] = "error"
        results["errors"].append(str(e))
    
    return results


def get_risk_status() -> Dict:
    """Получает текущий статус risk management"""
    config = load_risk_config()
    positions = paper_get_positions()
    trailing_stops = load_trailing_stops()
    
    # Проверка exposure
    exposure_ok, exposure_warning = check_max_exposure(config)
    
    equity_data = paper_get_equity()
    equity = float(equity_data.get("equity", 0))
    cash = float(equity_data.get("cash", 0))
    positions_value = equity - cash
    exposure_pct = (positions_value / equity * 100) if equity > 0 else 0
    
    return {
        "enabled": config.get("enabled", True),
        "config": config,
        "current_exposure": {
            "equity": equity,
            "positions_value": positions_value,
            "exposure_pct": exposure_pct,
            "max_allowed_pct": config.get("max_exposure", {}).get("percentage", 0.50) * 100,
            "status": "OK" if exposure_ok else "WARNING",
            "message": exposure_warning
        },
        "active_positions": len(positions),
        "active_trailing_stops": len(trailing_stops),
        "trailing_stops_details": trailing_stops
    }

