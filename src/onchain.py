"""
On-chain метрики через БЕСПЛАТНЫЕ API (CoinGecko, CoinGlass, Blockchain.com)
НЕ требуется API key! 🚀
"""
from __future__ import annotations
import os
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

# API endpoints (все бесплатные!)
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"
BLOCKCHAIN_INFO_BASE = "https://blockchain.info"


def _rate_limit_sleep(delay: float = 1.2):
    """Rate limiting для бесплатных API (50 req/min = 1.2 sec delay)"""
    time.sleep(delay)


def _coingecko_get(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Запрос к CoinGecko API (бесплатный, 50 req/min)"""
    url = f"{COINGECKO_BASE}/{endpoint}"
    try:
        response = requests.get(url, params=params or {}, timeout=15)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            logger.warning("[CoinGecko] Rate limit hit, sleeping 60s...")
            time.sleep(60)
            return None
        else:
            logger.error(f"[CoinGecko] Error {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"[CoinGecko] Request failed: {e}")
        return None


def _blockchain_info_get(endpoint: str) -> Optional[Dict]:
    """Запрос к Blockchain.info API (бесплатный для BTC)"""
    url = f"{BLOCKCHAIN_INFO_BASE}/{endpoint}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"[Blockchain.info] Error {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"[Blockchain.info] Request failed: {e}")
        return None


# ====================
# CoinGecko - Market Data (бесплатный!)
# ====================

def get_coingecko_market_data(coin_id: str = "bitcoin") -> Optional[Dict]:
    """
    Получить рыночные данные с CoinGecko
    
    Включает: market cap, volume, price changes, circulating supply
    """
    data = _coingecko_get(f"coins/{coin_id}", params={
        "localization": "false",
        "tickers": "false",
        "community_data": "false",
        "developer_data": "false"
    })
    
    if not data or "market_data" not in data:
        return None
    
    md = data["market_data"]
    return {
        "market_cap_usd": md.get("market_cap", {}).get("usd", 0),
        "total_volume_usd": md.get("total_volume", {}).get("usd", 0),
        "circulating_supply": md.get("circulating_supply", 0),
        "price_change_24h_pct": md.get("price_change_percentage_24h", 0),
        "price_change_7d_pct": md.get("price_change_percentage_7d", 0),
        "price_change_30d_pct": md.get("price_change_percentage_30d", 0),
    }


# ====================
# Blockchain.info - Bitcoin On-chain (бесплатный!)
# ====================

def get_btc_blockchain_stats() -> Optional[Dict]:
    """
    Bitcoin blockchain статистика от Blockchain.info
    
    Returns:
        {
            "n_btc_mined": количество добытых BTC,
            "market_price_usd": цена,
            "hash_rate": хешрейт сети,
            "difficulty": сложность,
            "n_tx": количество транзакций за 24h,
            "trade_volume_usd": объем торгов,
        }
    """
    data = _blockchain_info_get("stats?format=json")
    if not data:
        return None
    
    return {
        "n_btc_mined": data.get("n_btc_mined", 0) / 1e8,  # Satoshi to BTC
        "market_price_usd": data.get("market_price_usd", 0),
        "hash_rate": data.get("hash_rate", 0),
        "difficulty": data.get("difficulty", 0),
        "n_tx": data.get("n_tx", 0),
        "trade_volume_usd": data.get("trade_volume_usd", 0),
        "mempool_size": data.get("mempool_size", 0),
    }


# ====================
# CoinGlass - Derivatives Data (бесплатный!)
# ====================

def get_coinglass_funding_rate(symbol: str = "BTC") -> Optional[float]:
    """
    Funding Rate - индикатор настроения на derivatives рынке
    Положительный = longs платят shorts (bullish sentiment)
    Отрицательный = shorts платят longs (bearish sentiment)
    """
    try:
        # CoinGlass Public API (без ключа!)
        url = f"https://fapi.coinglass.com/api/fundingRate/v2/home"
        params = {"symbol": symbol}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "data" in data:
                # Усреднение по биржам
                rates = [float(item["rate"]) for item in data["data"] if "rate" in item]
                if rates:
                    return sum(rates) / len(rates)
        return None
    except Exception as e:
        logger.error(f"[CoinGlass] Funding rate request failed: {e}")
        return None


def get_coinglass_liquidations(symbol: str = "BTC") -> Optional[Dict]:
    """
    24h Liquidations - объем ликвидаций за последние 24h
    Высокие ликвидации = волатильность
    """
    try:
        url = f"https://fapi.coinglass.com/api/futures/liquidation/chart"
        params = {"symbol": symbol, "interval": "h1"}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "data" in data:
                liq_data = data["data"]
                total_longs = sum(float(item.get("longLiquidationValue", 0)) for item in liq_data)
                total_shorts = sum(float(item.get("shortLiquidationValue", 0)) for item in liq_data)
                return {
                    "total_liquidations_usd": total_longs + total_shorts,
                    "long_liquidations_usd": total_longs,
                    "short_liquidations_usd": total_shorts,
                }
        return None
    except Exception as e:
        logger.error(f"[CoinGlass] Liquidations request failed: {e}")
        return None


# ====================
# Helper: Get all metrics as features
# ====================

def get_onchain_features(asset: str = "BTC") -> Dict[str, float]:
    """
    Получить все on-chain метрики как словарь фич (БЕСПЛАТНЫЕ API!)
    
    Returns:
        Dict с ключами вида "onchain_{metric_name}"
    """
    features = {}
    
    # Маппинг coin_id для CoinGecko
    coin_id_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "USDT": "tether",
        "BNB": "binancecoin",
    }
    coin_id = coin_id_map.get(asset, "bitcoin")
    
    # 1. CoinGecko Market Data (всегда доступно!)
    logger.info(f"[OnChain] Fetching CoinGecko data for {coin_id}...")
    market_data = get_coingecko_market_data(coin_id)
    if market_data:
        features["onchain_market_cap"] = market_data["market_cap_usd"] / 1e9  # В миллиардах
        features["onchain_volume_24h"] = market_data["total_volume_usd"] / 1e9
        features["onchain_circulating_supply"] = market_data["circulating_supply"] / 1e6  # В миллионах
        features["onchain_price_change_24h"] = market_data["price_change_24h_pct"]
        features["onchain_price_change_7d"] = market_data["price_change_7d_pct"]
        features["onchain_price_change_30d"] = market_data["price_change_30d_pct"]
    else:
        logger.warning("[OnChain] Failed to fetch CoinGecko data, using defaults")
        features.update({
            "onchain_market_cap": 0.0,
            "onchain_volume_24h": 0.0,
            "onchain_circulating_supply": 0.0,
            "onchain_price_change_24h": 0.0,
            "onchain_price_change_7d": 0.0,
            "onchain_price_change_30d": 0.0,
        })
    
    _rate_limit_sleep()  # Rate limiting
    
    # 2. Blockchain.info (только для BTC)
    if asset == "BTC":
        logger.info("[OnChain] Fetching Blockchain.info data...")
        btc_stats = get_btc_blockchain_stats()
        if btc_stats:
            features["onchain_hash_rate"] = btc_stats["hash_rate"] / 1e18  # В EH/s
            features["onchain_difficulty"] = btc_stats["difficulty"] / 1e12  # В триллионах
            features["onchain_tx_count_24h"] = btc_stats["n_tx"] / 1000  # В тысячах
        else:
            features.update({
                "onchain_hash_rate": 0.0,
                "onchain_difficulty": 0.0,
                "onchain_tx_count_24h": 0.0,
            })
    else:
        # Заглушки для других монет
        features.update({
            "onchain_hash_rate": 0.0,
            "onchain_difficulty": 0.0,
            "onchain_tx_count_24h": 0.0,
        })
    
    _rate_limit_sleep()
    
    # 3. CoinGlass Derivatives Data (для всех)
    logger.info(f"[OnChain] Fetching CoinGlass data for {asset}...")
    funding_rate = get_coinglass_funding_rate(asset)
    if funding_rate is not None:
        features["onchain_funding_rate"] = funding_rate * 100  # В процентах
    else:
        features["onchain_funding_rate"] = 0.0
    
    _rate_limit_sleep()
    
    liquidations = get_coinglass_liquidations(asset)
    if liquidations:
        features["onchain_liquidations_24h"] = liquidations["total_liquidations_usd"] / 1e6  # В миллионах
        features["onchain_long_liquidations"] = liquidations["long_liquidations_usd"] / 1e6
        features["onchain_short_liquidations"] = liquidations["short_liquidations_usd"] / 1e6
    else:
        features.update({
            "onchain_liquidations_24h": 0.0,
            "onchain_long_liquidations": 0.0,
            "onchain_short_liquidations": 0.0,
        })
    
    logger.info(f"[OnChain] Successfully fetched {len(features)} on-chain features")
    return features


if __name__ == "__main__":
    # Тестирование (НЕ требуется API keys!)
    print("Testing FREE On-chain APIs...")
    print("\nCoinGecko + Blockchain.info + CoinGlass\n")
    
    features = get_onchain_features("BTC")
    for k, v in features.items():
        print(f"{k}: {v}")

