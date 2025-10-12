"""
Simple Strategy API Endpoints

Endpoints для работы с простыми стратегиями (RSI, EMA Crossover, Bollinger Bands)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
import pandas as pd

from ..db import SessionLocal, Price
from ..simple_strategies import (
    rsi_mean_reversion_strategy,
    ema_crossover_strategy,
    bollinger_bands_strategy
)
from ..notify import send_telegram

router = APIRouter(prefix="/simple_strategy", tags=["Simple Strategy"])


class StrategyRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    strategy: str = "ema_crossover"  # "ema_crossover", "rsi", "bollinger"
    # EMA params
    ema_fast: int = 9
    ema_slow: int = 21
    # RSI params
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    # Bollinger params
    bb_period: int = 20
    bb_std: float = 2.0


@router.post("/signal", summary="Получить сигнал от простой стратегии")
def get_simple_strategy_signal(req: StrategyRequest) -> Dict[str, Any]:
    """
    Генерирует торговый сигнал на основе простой стратегии
    
    Returns:
        - signal: "BUY", "SELL", "HOLD"
        - current_price: текущая цена
        - strategy: использованная стратегия
        - details: дополнительные детали
    """
    db = SessionLocal()
    
    try:
        # Загружаем последние 100 свечей (достаточно для любой стратегии)
        prices_query = db.query(Price).filter(
            Price.exchange == req.exchange,
            Price.symbol == req.symbol,
            Price.timeframe == req.timeframe
        ).order_by(Price.ts.desc()).limit(100).all()
        
        if not prices_query:
            raise HTTPException(
                status_code=404,
                detail=f"No prices found for {req.exchange} {req.symbol} {req.timeframe}"
            )
        
        # Reverse (старые -> новые)
        prices_query = list(reversed(prices_query))
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp(p.ts, unit='ms', tz='UTC'),
                "close": p.close,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "volume": p.volume
            }
            for p in prices_query
        ])
        
        df = df.set_index("timestamp")
        
        # Генерируем сигналы
        if req.strategy == "ema_crossover":
            signals = ema_crossover_strategy(df, fast_period=req.ema_fast, slow_period=req.ema_slow)
            strategy_name = f"EMA Crossover ({req.ema_fast}/{req.ema_slow})"
        elif req.strategy == "rsi":
            signals = rsi_mean_reversion_strategy(
                df, 
                rsi_period=req.rsi_period, 
                oversold=req.rsi_oversold, 
                overbought=req.rsi_overbought
            )
            strategy_name = f"RSI Mean-Reversion ({req.rsi_period})"
        elif req.strategy == "bollinger":
            signals = bollinger_bands_strategy(df, period=req.bb_period, num_std=req.bb_std)
            strategy_name = f"Bollinger Bands ({req.bb_period}, {req.bb_std}σ)"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")
        
        # Последний сигнал
        latest_signal = int(signals.iloc[-1])
        current_price = float(df['close'].iloc[-1])
        timestamp = df.index[-1]
        
        signal_map = {1: "BUY", -1: "SELL", 0: "HOLD"}
        signal_str = signal_map.get(latest_signal, "HOLD")
        
        # Отправляем уведомление если BUY
        if signal_str == "BUY":
            message = f"🟢 СИГНАЛ ПРОСТОЙ СТРАТЕГИИ\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"📊 Стратегия: {strategy_name}\n"
            message += f"💰 Пара: {req.symbol}\n"
            message += f"💵 Цена: ${current_price:.4f}\n"
            message += f"⏰ Время: {timestamp.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            message += f"🎯 СИГНАЛ: {signal_str}\n\n"
            message += f"💡 РЕКОМЕНДАЦИЯ:\n"
            message += f"Рассмотрите покупку на 10-20% капитала"
            
            send_telegram(message)
        
        return {
            "signal": signal_str,
            "signal_value": latest_signal,
            "current_price": current_price,
            "timestamp": str(timestamp),
            "exchange": req.exchange,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "strategy": strategy_name,
            "details": {
                "bars_analyzed": len(df),
                "total_buy_signals": int((signals == 1).sum()),
                "total_sell_signals": int((signals == -1).sum()),
                "total_hold_signals": int((signals == 0).sum())
            }
        }
    
    finally:
        db.close()


@router.get("/test_ema", summary="Тестовый endpoint для быстрой проверки EMA Crossover")
def test_ema_crossover(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h"
) -> Dict[str, Any]:
    """
    Быстрый тест EMA Crossover стратегии с дефолтными параметрами
    """
    return get_simple_strategy_signal(
        StrategyRequest(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            strategy="ema_crossover",
            ema_fast=9,
            ema_slow=21
        )
    )

