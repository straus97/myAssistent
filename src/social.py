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
# Reddit API
# ====================

def _get_reddit_token() -> Optional[str]:
    """Получить OAuth token для Reddit API"""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    
    url = "https://www.reddit.com/api/v1/access_token"
    auth = (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
    headers = {"User-Agent": "MyAssistent/1.0"}
    data = {"grant_type": "client_credentials"}
    
    try:
        response = requests.post(url, auth=auth, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception:
        return None


def get_reddit_sentiment(subreddits: List[str] = None, limit: int = 25) -> Optional[Dict]:
    """
    Получить sentiment из Reddit
    
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
    
    token = _get_reddit_token()
    if not token:
        logger.warning("[Reddit] OAuth token not available (check REDDIT_CLIENT_ID/SECRET)")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "MyAssistent/1.0",
    }
    
    all_posts = []
    for subreddit in subreddits:
        url = f"https://oauth.reddit.com/r/{subreddit}/hot"
        params = {"limit": limit}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "children" in data["data"]:
                    posts = data["data"]["children"]
                    all_posts.extend(posts)
        except Exception as e:
            logger.error(f"[Reddit] Failed to fetch r/{subreddit}: {e}")
            continue
    
    if not all_posts:
        return None
    
    # Анализ sentiment на основе upvote/downvote ratio
    scores = [p["data"]["score"] for p in all_posts if "data" in p]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Sentiment estimate (0-1) на основе среднего score
    # Высокие scores = позитивный sentiment
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
    Получить все social фичи
    
    Returns:
        Dict с ключами вида "social_{metric_name}"
    """
    features = {}
    
    # Twitter mentions
    twitter = get_twitter_mentions("bitcoin OR btc OR cryptocurrency")
    if twitter:
        features["social_twitter_mentions"] = float(twitter["count"])
        features["social_twitter_sentiment"] = twitter["sentiment_estimate"]
    else:
        features["social_twitter_mentions"] = 0.0
        features["social_twitter_sentiment"] = 0.5  # Neutral
    
    # Reddit sentiment
    reddit = get_reddit_sentiment()
    if reddit:
        features["social_reddit_posts"] = float(reddit["post_count"])
        features["social_reddit_sentiment"] = reddit["sentiment_estimate"]
    else:
        features["social_reddit_posts"] = 0.0
        features["social_reddit_sentiment"] = 0.5  # Neutral
    
    # Google Trends
    trends = get_google_trends_interest("bitcoin")
    if trends is not None:
        features["social_google_trends"] = trends
    else:
        features["social_google_trends"] = 50.0  # Neutral
    
    return features


if __name__ == "__main__":
    # Тестирование
    print("Testing Social APIs...")
    
    print("\n--- All Social Features ---")
    features = get_social_features()
    for k, v in features.items():
        print(f"{k}: {v}")

