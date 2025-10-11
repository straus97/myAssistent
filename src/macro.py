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
# DXY (US Dollar Index) - через Yahoo Finance (БЕСПЛАТНО!)
# ====================

def get_dxy_index() -> Optional[float]:
    """
    Получить US Dollar Index (DXY) через Yahoo Finance
    
    Используем Yahoo Finance API (бесплатный, без ключа!)
    Тикер: DX-Y.NYB (ICE US Dollar Index)
    """
    try:
        # Yahoo Finance public API endpoint
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        params = {
            "interval": "1d",
            "range": "5d",  # Последние 5 дней
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and len(data["chart"]["result"]) > 0:
                result = data["chart"]["result"][0]
                if "meta" in result and "regularMarketPrice" in result["meta"]:
                    return float(result["meta"]["regularMarketPrice"])
        
        logger.warning("[DXY] Failed to fetch from Yahoo Finance")
        return None
    except Exception as e:
        logger.error(f"[DXY] Request failed: {e}")
        return None


def get_gold_price() -> Optional[float]:
    """Получить цену золота через Yahoo Finance (тикер: GC=F)"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        params = {"interval": "1d", "range": "5d"}
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and len(data["chart"]["result"]) > 0:
                result = data["chart"]["result"][0]
                if "meta" in result and "regularMarketPrice" in result["meta"]:
                    return float(result["meta"]["regularMarketPrice"])
        return None
    except Exception as e:
        logger.error(f"[Gold] Request failed: {e}")
        return None


def get_oil_price() -> Optional[float]:
    """Получить цену нефти WTI через Yahoo Finance (тикер: CL=F)"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F"
        params = {"interval": "1d", "range": "5d"}
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and len(data["chart"]["result"]) > 0:
                result = data["chart"]["result"][0]
                if "meta" in result and "regularMarketPrice" in result["meta"]:
                    return float(result["meta"]["regularMarketPrice"])
        return None
    except Exception as e:
        logger.error(f"[Oil] Request failed: {e}")
        return None


# ====================
# Helper: Get all macro features
# ====================

def get_macro_features() -> Dict[str, float]:
    """
    Получить все макроэкономические фичи (БЕСПЛАТНЫЕ API!)
    
    Returns:
        Dict с ключами вида "macro_{metric_name}"
    """
    features = {}
    
    # 1. Fear & Greed Index (работает всегда, бесплатно!)
    logger.info("[Macro] Fetching Fear & Greed Index...")
    fg = get_fear_greed_index()
    if fg:
        features["macro_fear_greed"] = float(fg["value"])
        # Normalized: 0 (Extreme Fear) to 100 (Extreme Greed)
        features["macro_fear_greed_norm"] = (fg["value"] - 50) / 50.0  # -1..1
    else:
        logger.warning("[Macro] Failed to fetch Fear & Greed, using defaults")
        features["macro_fear_greed"] = 50.0  # Neutral
        features["macro_fear_greed_norm"] = 0.0
    
    # 2. DXY через Yahoo Finance (бесплатно!)
    logger.info("[Macro] Fetching DXY from Yahoo Finance...")
    dxy = get_dxy_index()
    if dxy:
        features["macro_dxy"] = float(dxy)
    else:
        features["macro_dxy"] = 103.0  # Типичное значение 2025 года
    
    # 3. Gold price (бесплатно через Yahoo Finance!)
    logger.info("[Macro] Fetching Gold price...")
    gold = get_gold_price()
    if gold:
        features["macro_gold_price"] = gold
    else:
        features["macro_gold_price"] = 2000.0  # Типичная цена
    
    # 4. Oil price (бесплатно через Yahoo Finance!)
    logger.info("[Macro] Fetching Oil price...")
    oil = get_oil_price()
    if oil:
        features["macro_oil_price"] = oil
    else:
        features["macro_oil_price"] = 80.0  # Типичная цена
    
    # 5. FRED API (опционально, если есть ключ)
    if FRED_API_KEY:
        logger.info("[Macro] Fetching FRED data (API key configured)...")
        
        # Federal Funds Rate
        ffr = get_fred_series("DFF")
        if ffr and ffr["value"] is not None:
            features["macro_fed_rate"] = float(ffr["value"])
        else:
            features["macro_fed_rate"] = 5.5  # Типичная ставка 2025
        
        # 10-Year Treasury Yield
        dgs10 = get_fred_series("DGS10")
        if dgs10 and dgs10["value"] is not None:
            features["macro_treasury_10y"] = float(dgs10["value"])
        else:
            features["macro_treasury_10y"] = 4.5
        
        # 2-Year Treasury Yield
        dgs2 = get_fred_series("DGS2")
        if dgs2 and dgs2["value"] is not None:
            features["macro_treasury_2y"] = float(dgs2["value"])
            # Yield curve spread (индикатор рецессии)
            features["macro_yield_spread"] = features["macro_treasury_10y"] - features["macro_treasury_2y"]
        else:
            features["macro_treasury_2y"] = 4.8
            features["macro_yield_spread"] = -0.3  # Инверсия кривой
    else:
        # Используем типичные значения 2025 года (без API key)
        logger.info("[FRED] Using typical 2025 values (no API key configured)")
        features["macro_fed_rate"] = 5.5
        features["macro_treasury_10y"] = 4.5
        features["macro_treasury_2y"] = 4.8
        features["macro_yield_spread"] = -0.3  # Инверсия (recession signal)
    
    logger.info(f"[Macro] Successfully fetched {len(features)} macro features")
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

