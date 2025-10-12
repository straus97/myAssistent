"""
Real-time Paper Trading Monitor

Автоматически:
1. Обновляет цены каждые 15 минут
2. Генерирует сигналы на новых данных
3. Обновляет equity позиций
4. Сохраняет историю для графиков
5. Отправляет уведомления о важных событиях
"""

from __future__ import annotations
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from .db import SessionLocal, Price
from .prices import fetch_and_store_prices
from .features import build_dataset
from .modeling import load_latest_model
from .trade import paper_get_equity, paper_get_positions
from .risk import load_policy
from .notify import send_telegram

logger = logging.getLogger(__name__)

# Путь к файлу истории equity
EQUITY_HISTORY_PATH = Path("artifacts/equity_history_realtime.json")
EQUITY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

# Путь к файлу состояния монитора
MONITOR_STATE_PATH = Path("artifacts/state/paper_monitor.json")
MONITOR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_monitor_state() -> Dict:
    """Загружает состояние монитора"""
    if MONITOR_STATE_PATH.exists():
        try:
            return json.loads(MONITOR_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    return {
        "enabled": False,
        "last_update": None,
        "update_interval_minutes": 15,
        "symbols": ["BTC/USDT"],
        "exchange": "bybit",
        "timeframe": "1h",
        "auto_execute": False,  # Автоматическое исполнение сигналов
        "notifications": True,
        "stats": {
            "total_updates": 0,
            "total_signals": 0,
            "last_signal_time": None,
            "errors": 0
        }
    }


def save_monitor_state(state: Dict) -> None:
    """Сохраняет состояние монитора"""
    state["updated_at"] = datetime.utcnow().isoformat()
    MONITOR_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_equity_history() -> List[Dict]:
    """Загружает историю equity"""
    if EQUITY_HISTORY_PATH.exists():
        try:
            return json.loads(EQUITY_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_equity_snapshot(equity_data: Dict) -> None:
    """Сохраняет снимок equity в историю"""
    history = load_equity_history()
    
    # Добавляем timestamp
    snapshot = {
        "timestamp": datetime.utcnow().isoformat(),
        **equity_data
    }
    
    history.append(snapshot)
    
    # Храним последние 30 дней (30*24*4 = 2880 снимков при обновлении каждые 15 минут)
    max_snapshots = 2880
    if len(history) > max_snapshots:
        history = history[-max_snapshots:]
    
    EQUITY_HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    logger.info(f"[MONITOR] Saved equity snapshot: ${equity_data.get('equity', 0):.2f}")


def update_prices_for_symbols(symbols: List[str], exchange: str, timeframe: str) -> bool:
    """Обновляет цены для всех символов"""
    try:
        db = SessionLocal()
        try:
            for symbol in symbols:
                logger.info(f"[MONITOR] Updating prices for {symbol}...")
                fetch_and_store_prices(db, exchange, symbol, timeframe, limit=100)
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[MONITOR] Error updating prices: {e}")
        return False


def generate_signals_for_symbols(
    symbols: List[str],
    exchange: str,
    timeframe: str,
    db: Session
) -> List[Dict]:
    """Генерирует сигналы для всех символов"""
    signals = []
    
    try:
        # Загружаем модель
        model_tuple = load_latest_model()
        if not model_tuple:
            logger.warning("[MONITOR] No model found, skipping signal generation")
            return signals
        
        # Распаковываем tuple (model, feature_cols, threshold, path)
        model, feature_cols_from_model, threshold, model_path = model_tuple
        logger.info(f"[MONITOR] Loaded model from {model_path}")
        
        # Загружаем risk policy
        policy = load_policy()
        
        for symbol in symbols:
            try:
                # Строим датасет
                df, feature_list = build_dataset(db, exchange, symbol, timeframe)
                
                if df is None or len(df) < 50:
                    logger.warning(f"[MONITOR] Not enough data for {symbol}")
                    continue
                
                # Получаем последнюю строку
                last_row = df.iloc[-1]
                
                # Определяем feature columns
                feature_cols = [col for col in df.columns if col not in [
                    'future_ret', 'y', 'timestamp'
                ]]
                
                # Предсказание
                X = df[feature_cols].iloc[[-1]].fillna(0)
                proba = model.predict_proba(X)[0, 1]
                
                # Простая проверка порога вероятности
                min_prob = policy.get("min_probability", 0.55)
                
                if proba >= min_prob:
                    signal = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "exchange": exchange,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "probability": float(proba),
                        "action": "BUY",
                        "price": float(last_row.get("close", 0)),
                        "vol_state": "normal"
                    }
                    
                    signals.append(signal)
                    logger.info(f"[MONITOR] Generated signal for {symbol}: BUY @ {signal['price']:.2f} (prob: {proba:.3f})")
            
            except Exception as e:
                logger.error(f"[MONITOR] Error generating signal for {symbol}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"[MONITOR] Error in signal generation: {e}")
    
    return signals


def execute_signals_if_enabled(signals: List[Dict], auto_execute: bool) -> None:
    """Исполняет сигналы если включено автоматическое исполнение"""
    if not auto_execute or not signals:
        return
    
    from .trade import paper_buy_auto
    
    for signal in signals:
        try:
            logger.info(f"[MONITOR] Auto-executing signal: {signal['symbol']}")
            
            db = SessionLocal()
            try:
                result = paper_buy_auto(
                    db=db,
                    exchange=signal["exchange"],
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    price=signal["price"],
                    probability=signal["probability"],
                    vol_state=signal.get("vol_state")
                )
                
                if result.get("status") == "ok":
                    logger.info(f"[MONITOR] Successfully executed: {result}")
                else:
                    logger.warning(f"[MONITOR] Failed to execute: {result}")
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"[MONITOR] Error executing signal: {e}")


def send_notification_if_enabled(
    signals: List[Dict],
    equity_data: Dict,
    notifications_enabled: bool
) -> None:
    """Отправляет уведомление о сигналах"""
    if not notifications_enabled or not signals:
        return
    
    try:
        equity = equity_data.get("equity", 0)
        pnl = equity_data.get("total_pnl", 0)
        pnl_pct = (pnl / 10000.0) * 100 if equity > 0 else 0
        
        message = f"[PAPER TRADING] Новые сигналы!\n\n"
        message += f"Equity: ${equity:.2f} ({pnl_pct:+.2f}%)\n"
        message += f"Позиций: {equity_data.get('n_positions', 0)}\n\n"
        
        for sig in signals[:3]:  # Первые 3 сигнала
            message += f"{sig['symbol']}: BUY @ ${sig['price']:.2f}\n"
            message += f"Probability: {sig['probability']:.1%}\n\n"
        
        if len(signals) > 3:
            message += f"... и еще {len(signals) - 3} сигналов"
        
        send_telegram(message)
        logger.info("[MONITOR] Notification sent")
    
    except Exception as e:
        logger.error(f"[MONITOR] Error sending notification: {e}")


def run_monitor_update() -> Dict:
    """
    Запускает один цикл обновления монитора.
    
    Returns:
        Dict с результатами обновления
    """
    start_time = datetime.utcnow()
    
    # Загружаем состояние
    state = load_monitor_state()
    
    if not state.get("enabled", False):
        return {
            "status": "disabled",
            "message": "Monitor is disabled"
        }
    
    logger.info("[MONITOR] Starting update cycle...")
    
    results = {
        "status": "ok",
        "timestamp": start_time.isoformat(),
        "updates": {},
        "signals": [],
        "equity": {},
        "errors": []
    }
    
    try:
        # 1. Обновляем цены
        symbols = state.get("symbols", ["BTC/USDT"])
        exchange = state.get("exchange", "bybit")
        timeframe = state.get("timeframe", "1h")
        
        logger.info(f"[MONITOR] Updating prices for {len(symbols)} symbols...")
        prices_updated = update_prices_for_symbols(symbols, exchange, timeframe)
        
        if not prices_updated:
            results["errors"].append("Failed to update prices")
        
        # 2. Генерируем сигналы
        db = SessionLocal()
        try:
            logger.info("[MONITOR] Generating signals...")
            signals = generate_signals_for_symbols(symbols, exchange, timeframe, db)
            results["signals"] = signals
            
            # 3. Исполняем сигналы (если включено)
            if state.get("auto_execute", False):
                execute_signals_if_enabled(signals, True)
            
            # 4. Получаем текущий equity
            equity_data = paper_get_equity()
            results["equity"] = equity_data
            
            # 5. Сохраняем snapshot equity
            save_equity_snapshot(equity_data)
            
            # 6. Отправляем уведомления
            if signals and state.get("notifications", True):
                send_notification_if_enabled(signals, equity_data, True)
            
            # 7. Обновляем статистику
            state["last_update"] = start_time.isoformat()
            state["stats"]["total_updates"] += 1
            state["stats"]["total_signals"] += len(signals)
            
            if signals:
                state["stats"]["last_signal_time"] = start_time.isoformat()
            
            save_monitor_state(state)
        
        finally:
            db.close()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"[MONITOR] Update cycle completed in {duration:.2f}s")
        results["duration_seconds"] = duration
        
    except Exception as e:
        logger.error(f"[MONITOR] Error in update cycle: {e}")
        results["status"] = "error"
        results["errors"].append(str(e))
        
        # Увеличиваем счётчик ошибок
        state["stats"]["errors"] += 1
        save_monitor_state(state)
    
    return results


def get_equity_chart_data(hours: int = 24) -> Dict:
    """
    Получает данные для графика equity за последние N часов.
    
    Args:
        hours: Количество часов истории
        
    Returns:
        Dict с данными для графика
    """
    history = load_equity_history()
    
    if not history:
        return {
            "timestamps": [],
            "equity": [],
            "pnl": [],
            "pnl_pct": []
        }
    
    # Фильтруем по времени
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    filtered = [
        h for h in history
        if datetime.fromisoformat(h["timestamp"]) >= cutoff
    ]
    
    if not filtered:
        filtered = history[-min(100, len(history)):]  # Последние 100 точек
    
    return {
        "timestamps": [h["timestamp"] for h in filtered],
        "equity": [h.get("equity", 0) for h in filtered],
        "pnl": [h.get("total_pnl", 0) for h in filtered],
        "pnl_pct": [
            (h.get("total_pnl", 0) / 10000.0) * 100 if h.get("equity", 0) > 0 else 0
            for h in filtered
        ]
    }


def get_monitor_status() -> Dict:
    """Получает текущий статус монитора"""
    state = load_monitor_state()
    equity = paper_get_equity()
    positions = paper_get_positions()
    
    return {
        "enabled": state.get("enabled", False),
        "last_update": state.get("last_update"),
        "update_interval_minutes": state.get("update_interval_minutes", 15),
        "auto_execute": state.get("auto_execute", False),
        "notifications": state.get("notifications", True),
        "symbols": state.get("symbols", []),
        "stats": state.get("stats", {}),
        "equity": equity,
        "positions_count": len(positions)
    }

