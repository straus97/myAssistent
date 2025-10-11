"""
Social signals (Twitter, Reddit, Google Trends)
"""
from __future__ import annotations
import os
import requests
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

# API Keys
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")


# ====================
# Twitter API v2
# ====================

def get_twitter_mentions(query: str = "bitcoin OR btc", max_results: int = 100) -> Optional[Dict]:
    """
    Получить упоминания в Twitter
    
    Требуется Twitter API v2 Bearer Token
    https://developer.twitter.com/en/docs/twitter-api/getting-started/getting-access-to-the-twitter-api
    
    Args:
        query: Поисковый запрос (например "bitcoin OR btc OR cryptocurrency")
        max_results: Максимум результатов (10-100)
    
    Returns:
        {
            "count": 85,
            "sentiment_estimate": 0.65,  # Примерная оценка на основе like/retweet
        }
    """
    if not TWITTER_BEARER_TOKEN:
        logger.warning("[Twitter] Bearer token not configured (set TWITTER_BEARER_TOKEN in .env)")
        return None
    
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    params = {
        "query": query,
        "max_results": min(max_results, 100),
        "tweet.fields": "public_metrics,created_at",
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                tweets = data["data"]
                count = len(tweets)
                
                # Простая оценка sentiment на основе engagement
                total_likes = sum(t.get("public_metrics", {}).get("like_count", 0) for t in tweets)
                total_retweets = sum(t.get("public_metrics", {}).get("retweet_count", 0) for t in tweets)
                
                # Normalized sentiment estimate (0-1)
                engagement = (total_likes + total_retweets * 2) / (count + 1)
                sentiment_estimate = min(engagement / 100, 1.0)  # Cap at 1.0
                
                return {
                    "count": count,
                    "sentiment_estimate": sentiment_estimate,
                }
        logger.error(f"[Twitter] Error {response.status_code}: {response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[Twitter] Request failed: {e}")
        return None


# ====================
# Reddit API - Public JSON (БЕЗ КЛЮЧА!)
# ====================

def get_reddit_sentiment(subreddits: List[str] = None, limit: int = 25) -> Optional[Dict]:
    """
    Получить sentiment из Reddit через PUBLIC JSON API (НЕ требуется OAuth!)
    
    Args:
        subreddits: Список сабреддитов (default: ["cryptocurrency", "bitcoin", "ethereum"])
        limit: Количество постов на сабреддит
    
    Returns:
        {
            "post_count": 75,
            "avg_score": 125.5,
            "sentiment_estimate": 0.72,
        }
    """
    if subreddits is None:
        subreddits = ["cryptocurrency", "bitcoin", "ethereum"]
    
    headers = {"User-Agent": "MyAssistent/1.0 (Educational purposes)"}
    all_posts = []
    
    for subreddit in subreddits:
        # Reddit Public JSON API (добавляем .json к URL)
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        params = {"limit": limit}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "children" in data["data"]:
                    posts = data["data"]["children"]
                    all_posts.extend(posts)
                    logger.info(f"[Reddit] Fetched {len(posts)} posts from r/{subreddit}")
            elif response.status_code == 429:
                logger.warning(f"[Reddit] Rate limit hit for r/{subreddit}, skipping")
                continue
        except Exception as e:
            logger.error(f"[Reddit] Failed to fetch r/{subreddit}: {e}")
            continue
    
    if not all_posts:
        logger.warning("[Reddit] No posts fetched from any subreddit")
        return None
    
    # Анализ sentiment на основе upvote/downvote ratio и score
    scores = [p["data"]["score"] for p in all_posts if "data" in p and "score" in p["data"]]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Sentiment estimate (0-1) на основе среднего score
    # Reddit scores обычно 10-500, нормализуем
    sentiment_estimate = min(max(avg_score / 500, 0), 1)
    
    return {
        "post_count": len(all_posts),
        "avg_score": avg_score,
        "sentiment_estimate": sentiment_estimate,
    }


# ====================
# Google Trends (через pytrends - опционально)
# ====================

def get_google_trends_interest(keyword: str = "bitcoin") -> Optional[float]:
    """
    Получить интерес Google Trends
    
    Требуется библиотека pytrends (pip install pytrends)
    Работает без API key!
    """
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe="now 7-d")
        
        df = pytrends.interest_over_time()
        if not df.empty and keyword in df.columns:
            # Возвращаем последнее значение (0-100)
            return float(df[keyword].iloc[-1])
        return None
    except ImportError:
        logger.warning("[GoogleTrends] pytrends not installed (pip install pytrends)")
        return None
    except Exception as e:
        logger.error(f"[GoogleTrends] Request failed: {e}")
        return None


# ====================
# Helper: Get all social features
# ====================

def get_social_features() -> Dict[str, float]:
    """
    Получить все social фичи (БЕСПЛАТНЫЕ API!)
    
    Returns:
        Dict с ключами вида "social_{metric_name}"
    """
    features = {}
    
    # 1. Reddit sentiment (PUBLIC JSON API - всегда работает!)
    logger.info("[Social] Fetching Reddit sentiment (public JSON)...")
    reddit = get_reddit_sentiment(subreddits=["cryptocurrency", "bitcoin"], limit=15)
    if reddit:
        features["social_reddit_posts"] = float(reddit["post_count"])
        features["social_reddit_sentiment"] = reddit["sentiment_estimate"]
        features["social_reddit_avg_score"] = reddit["avg_score"]
    else:
        features["social_reddit_posts"] = 0.0
        features["social_reddit_sentiment"] = 0.5  # Neutral
        features["social_reddit_avg_score"] = 0.0
    
    # 2. Google Trends (через pytrends - бесплатно!)
    logger.info("[Social] Fetching Google Trends...")
    trends = get_google_trends_interest("bitcoin")
    if trends is not None:
        features["social_google_trends"] = trends
    else:
        logger.warning("[Social] pytrends not available or failed")
        features["social_google_trends"] = 50.0  # Neutral (mid-range 0-100)
    
    # 3. Twitter mentions (если есть token, иначе пропускаем)
    if TWITTER_BEARER_TOKEN:
        logger.info("[Social] Fetching Twitter mentions...")
        twitter = get_twitter_mentions("bitcoin OR btc OR cryptocurrency", max_results=50)
        if twitter:
            features["social_twitter_mentions"] = float(twitter["count"])
            features["social_twitter_sentiment"] = twitter["sentiment_estimate"]
        else:
            features["social_twitter_mentions"] = 0.0
            features["social_twitter_sentiment"] = 0.5
    else:
        # Без Twitter API используем Reddit как прокси
        logger.info("[Social] Twitter API not configured, using Reddit as proxy")
        features["social_twitter_mentions"] = features["social_reddit_posts"]  # Proxy
        features["social_twitter_sentiment"] = features["social_reddit_sentiment"]
    
    logger.info(f"[Social] Successfully fetched {len(features)} social features")
    return features


if __name__ == "__main__":
    # Тестирование
    print("Testing Social APIs...")
    
    print("\n--- All Social Features ---")
    features = get_social_features()
    for k, v in features.items():
        print(f"{k}: {v}")

