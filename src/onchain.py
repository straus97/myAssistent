"""
On-chain метрики через Glassnode API
Требуется API key: https://glassnode.com/
"""
from __future__ import annotations
import os
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Glassnode API
GLASSNODE_API_KEY = os.getenv("GLASSNODE_API_KEY", "")
GLASSNODE_BASE_URL = "https://api.glassnode.com/v1/metrics"


def _get_glassnode(endpoint: str, asset: str = "BTC", params: Optional[Dict] = None) -> Optional[pd.DataFrame]:
    """
    Базовый запрос к Glassnode API
    
    Args:
        endpoint: Например "addresses/active_count"
        asset: BTC, ETH, etc.
        params: Дополнительные параметры (since, until, interval)
    
    Returns:
        DataFrame с колонками [timestamp, value] или None если ошибка
    """
    if not GLASSNODE_API_KEY:
        logger.warning("[Glassnode] API key not configured (set GLASSNODE_API_KEY in .env)")
        return None
    
    url = f"{GLASSNODE_BASE_URL}/{endpoint}"
    params = params or {}
    params["a"] = asset
    params["api_key"] = GLASSNODE_API_KEY
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if not data:
                return None
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
            df = df.rename(columns={"v": "value"})
            return df[["timestamp", "value"]]
        else:
            logger.error(f"[Glassnode] Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"[Glassnode] Request failed: {e}")
        return None


# ====================
# Exchange Flows
# ====================

def get_exchange_netflow(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    Exchange Net Flows - приток/отток с бирж
    Отрицательные значения = вывод с бирж (потенциально bullish)
    Положительные = приток на биржи (потенциально bearish)
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("transactions/transfers_volume_exchanges_net", asset, params)


def get_exchange_inflow(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    Exchange Inflows - приток на биржи
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("transactions/transfers_volume_to_exchanges", asset, params)


def get_exchange_outflow(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    Exchange Outflows - вывод с бирж
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("transactions/transfers_volume_from_exchanges", asset, params)


# ====================
# Network Activity
# ====================

def get_active_addresses(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    Active Addresses - количество уникальных активных адресов
    Показатель сетевой активности
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("addresses/active_count", asset, params)


def get_new_addresses(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    New Addresses - новые адреса (первые транзакции)
    Показатель adoption
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("addresses/new_non_zero_count", asset, params)


# ====================
# Profitability Metrics
# ====================

def get_sopr(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    SOPR (Spent Output Profit Ratio)
    > 1 = монеты продаются в прибыли
    < 1 = монеты продаются в убытке
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("indicators/sopr", asset, params)


def get_mvrv_ratio(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    MVRV Ratio (Market Value to Realized Value)
    > 3.5 = потенциально overvalued (top signal)
    < 1.0 = потенциально undervalued (bottom signal)
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("market/mvrv", asset, params)


def get_nupl(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    NUPL (Net Unrealized Profit/Loss)
    > 0.75 = euphoria (top signal)
    < 0 = capitulation (bottom signal)
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("indicators/net_unrealized_profit_loss", asset, params)


# ====================
# Miner Metrics
# ====================

def get_puell_multiple(asset: str = "BTC", days: int = 30) -> Optional[pd.DataFrame]:
    """
    Puell Multiple - mining economics
    > 4 = miners selling heavily (potential top)
    < 0.5 = miners struggling (potential bottom)
    """
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    params = {"since": since, "i": "24h"}
    return _get_glassnode("indicators/puell_multiple", asset, params)


# ====================
# Helper: Get all metrics as features
# ====================

def get_onchain_features(asset: str = "BTC", days: int = 30) -> Dict[str, float]:
    """
    Получить все on-chain метрики как словарь фич (последние значения)
    
    Returns:
        Dict с ключами вида "onchain_{metric_name}"
    """
    features = {}
    
    # Placeholder values (если API key не настроен)
    if not GLASSNODE_API_KEY:
        logger.info("[Glassnode] Using placeholder values (API key not configured)")
        return {
            "onchain_exchange_netflow": 0.0,
            "onchain_exchange_inflow": 0.0,
            "onchain_exchange_outflow": 0.0,
            "onchain_active_addresses": 0.0,
            "onchain_new_addresses": 0.0,
            "onchain_sopr": 1.0,  # Neutral
            "onchain_mvrv": 1.5,  # Neutral
            "onchain_nupl": 0.3,  # Neutral
            "onchain_puell_multiple": 1.0,  # Neutral
        }
    
    # Fetch real data
    metrics = {
        "exchange_netflow": get_exchange_netflow(asset, days),
        "exchange_inflow": get_exchange_inflow(asset, days),
        "exchange_outflow": get_exchange_outflow(asset, days),
        "active_addresses": get_active_addresses(asset, days),
        "new_addresses": get_new_addresses(asset, days),
        "sopr": get_sopr(asset, days),
        "mvrv": get_mvrv_ratio(asset, days),
        "nupl": get_nupl(asset, days),
        "puell_multiple": get_puell_multiple(asset, days),
    }
    
    for name, df in metrics.items():
        if df is not None and not df.empty:
            # Берём последнее значение
            features[f"onchain_{name}"] = float(df["value"].iloc[-1])
        else:
            features[f"onchain_{name}"] = 0.0
    
    return features


if __name__ == "__main__":
    # Тестирование (требуется GLASSNODE_API_KEY в .env)
    print("Testing Glassnode API...")
    features = get_onchain_features("BTC", days=7)
    for k, v in features.items():
        print(f"{k}: {v}")

