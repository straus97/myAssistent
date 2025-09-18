# src/news.py
from datetime import datetime
from dateutil import parser as dtparse
import feedparser
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from .db import Article

# Базовый список лент (потом расширим)
FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://www.reuters.com/markets/cryptocurrency/rss",
]

def _hostname(url: str) -> str:
    return urlparse(url).hostname or "unknown"

def fetch_and_store(db: Session, limit_per_feed: int = 30) -> int:
    """
    Скачивает последние записи из FEEDS и сохраняет новые статьи в БД.
    Возвращает кол-во добавленных записей.
    """
    added = 0
    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", None)

            # пытаемся распарсить дату публикации, если она есть
            published_at = None
            try:
                if getattr(entry, "published", None):
                    published_at = dtparse.parse(entry.published)
            except Exception:
                published_at = None

            if not title or not link:
                continue

            # Пропускаем дубликаты (по URL)
            exists = db.query(Article).filter(Article.url == link).first()
            if exists:
                continue

            article = Article(
                source=_hostname(link),
                title=title[:500],
                url=link[:1000],
                summary=summary,
                published_at=published_at
            )
            db.add(article)
            try:
                db.commit()
                added += 1
            except Exception:
                db.rollback()
    return added
