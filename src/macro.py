"""
Макроэкономические данные и индикаторы рынка
"""
from __future__ import annotations
import os
import requests
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ====================
# Fear & Greed Index (Alternative.me)
# ====================

def get_fear_greed_index() -> Optional[Dict]:
    """
    Получить Crypto Fear & Greed Index от Alternative.me
    
    API бесплатный, не требует ключа!
    
    Returns:
        {
            "value": 45,  # 0-100
            "value_classification": "Fear",  # Extreme Fear, Fear, Neutral, Greed, Extreme Greed
            "timestamp": 1234567890
        }
    """
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url, params={"limit": 1}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                latest = data["data"][0]
                return {
                    "value": int(latest["value"]),
                    "value_classification": latest["value_classification"],
                    "timestamp": int(latest["timestamp"]),
                }
        logger.error(f"[FearGreed] Error {response.status_code}: {response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[FearGreed] Request failed: {e}")
        return None


def get_fear_greed_history(days: int = 30) -> Optional[list]:
    """
    Получить историю Fear & Greed Index
    
    Returns:
        List of {value, value_classification, timestamp}
    """
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url, params={"limit": days}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                return [
                    {
                        "value": int(item["value"]),
                        "value_classification": item["value_classification"],
                        "timestamp": int(item["timestamp"]),
                    }
                    for item in data["data"]
                ]
        return None
    except Exception as e:
        logger.error(f"[FearGreed] History request failed: {e}")
        return None


# ====================
# FRED API (Federal Reserve Economic Data)
# ====================

FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def get_fred_series(series_id: str, days: int = 30) -> Optional[Dict]:
    """
    Получить данные из FRED API
    
    Требуется API key: https://fred.stlouisfed.org/docs/api/api_key.html
    
    Популярные series_id:
    - DFF: Federal Funds Rate (базовая ставка ФРС)
    - DGS10: 10-Year Treasury Yield
    - DGS2: 2-Year Treasury Yield
    - DEXUSEU: USD/EUR exchange rate
    - DCOILWTICO: WTI Crude Oil Prices
    - GOLDAMGBD228NLBM: Gold Prices
    """
    if not FRED_API_KEY:
        logger.warning("[FRED] API key not configured (set FRED_API_KEY in .env)")
        return None
    
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "limit": days,
        "sort_order": "desc",
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "observations" in data and len(data["observations"]) > 0:
                latest = data["observations"][0]
                return {
                    "value": float(latest["value"]) if latest["value"] != "." else None,
                    "date": latest["date"],
                }
        logger.error(f"[FRED] Error {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"[FRED] Request failed: {e}")
        return None


# ====================
# DXY (US Dollar Index) - через альтернативный источник
# ====================

def get_dxy_index() -> Optional[float]:
    """
    Получить US Dollar Index (DXY)
    
    Используем публичный API (может быть unstable)
    Альтернатива: можно парсить из TradingView или использовать FRED
    """
    # Placeholder: требуется найти подходящий бесплатный API
    # Опции:
    # 1. FRED API: DTWEXBGS (но требует API key)
    # 2. TradingView (требует парсинг)
    # 3. Alpha Vantage (лимитированный)
    
    logger.warning("[DXY] Not implemented yet (requires API setup)")
    return None


# ====================
# Helper: Get all macro features
# ====================

def get_macro_features() -> Dict[str, float]:
    """
    Получить все макроэкономические фичи
    
    Returns:
        Dict с ключами вида "macro_{metric_name}"
    """
    features = {}
    
    # Fear & Greed Index (работает всегда!)
    fg = get_fear_greed_index()
    if fg:
        features["macro_fear_greed"] = float(fg["value"])
        # Normalized: 0 (Extreme Fear) to 100 (Extreme Greed)
        features["macro_fear_greed_norm"] = (fg["value"] - 50) / 50.0  # -1..1
    else:
        features["macro_fear_greed"] = 50.0  # Neutral
        features["macro_fear_greed_norm"] = 0.0
    
    # Federal Funds Rate (если API key настроен)
    if FRED_API_KEY:
        ffr = get_fred_series("DFF")
        if ffr and ffr["value"] is not None:
            features["macro_fed_rate"] = float(ffr["value"])
        else:
            features["macro_fed_rate"] = 0.0
        
        # 10-Year Treasury Yield
        dgs10 = get_fred_series("DGS10")
        if dgs10 and dgs10["value"] is not None:
            features["macro_treasury_10y"] = float(dgs10["value"])
        else:
            features["macro_treasury_10y"] = 0.0
        
        # 2-Year Treasury Yield
        dgs2 = get_fred_series("DGS2")
        if dgs2 and dgs2["value"] is not None:
            features["macro_treasury_2y"] = float(dgs2["value"])
            # Yield curve spread (индикатор рецессии)
            if "macro_treasury_10y" in features and features["macro_treasury_10y"] > 0:
                features["macro_yield_spread"] = features["macro_treasury_10y"] - features["macro_treasury_2y"]
            else:
                features["macro_yield_spread"] = 0.0
        else:
            features["macro_treasury_2y"] = 0.0
            features["macro_yield_spread"] = 0.0
    else:
        # Placeholder values
        logger.info("[FRED] Using placeholder values (API key not configured)")
        features["macro_fed_rate"] = 0.0
        features["macro_treasury_10y"] = 0.0
        features["macro_treasury_2y"] = 0.0
        features["macro_yield_spread"] = 0.0
    
    # DXY (пока placeholder)
    dxy = get_dxy_index()
    if dxy:
        features["macro_dxy"] = float(dxy)
    else:
        features["macro_dxy"] = 100.0  # Neutral
    
    return features


if __name__ == "__main__":
    # Тестирование
    print("Testing Macro APIs...")
    
    print("\n--- Fear & Greed Index ---")
    fg = get_fear_greed_index()
    if fg:
        print(f"Value: {fg['value']} ({fg['value_classification']})")
    
    print("\n--- All Macro Features ---")
    features = get_macro_features()
    for k, v in features.items():
        print(f"{k}: {v}")

