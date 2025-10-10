from __future__ import annotations
from datetime import datetime, timezone, timedelta
from dateutil import parser as dtparse
import feedparser
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import time
import requests
from src.db import Article, ArticleAnnotation
from .news_url import canonicalize_url
import re

# Базовый список лент (можно расширять конфигом позже)
FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://www.reuters.com/markets/cryptocurrency/rss",
]


def _hostname(url: str) -> str:
    try:
        host = urlparse(url).hostname
        return host or "unknown"
    except Exception:
        return "unknown"


def _parse_published(entry) -> datetime | None:
    # стараемся корректно считать published/update
    dt_candidates = []
    for attr in ("published", "updated", "pubDate"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt_candidates.append(dtparse.parse(val))
            except Exception:
                pass
    # feedparser также кладёт *_parsed — это time.struct_time
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt_candidates.append(datetime.fromtimestamp(time.mktime(val), tz=timezone.utc))
            except Exception:
                pass

    if not dt_candidates:
        return None
    # берём максимально "свежее"
    dt = max(dt_candidates)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def fetch_and_store(
    db: Session,
    feeds: List[str] | None = None,
    per_feed_limit: int = 50,
    req_timeout: float = 10.0,
    total_limit: int | None = None,
) -> int:
    """
    Надёжная загрузка новостей:
      - requests.get(..., timeout=req_timeout) -> feedparser.parse(bytes)
      - per_feed_limit: ограничение записей на фид
      - total_limit: общий лимит (None = без лимита)
      - коммиты пачками
      - канонизация URL (без UTM и прочих трекеров) + дедупликация:
         1) жёсткая — по каноническому URL
         2) мягкая — тот же источник и идентичный заголовок в окне ±48h
    """
    feeds = feeds or FEEDS
    headers = {"User-Agent": "MyAssistantBot/0.7 (+https://local)"}

    added = 0
    batch = 0
    start_time = time.time()

    for feed_url in feeds:
        try:
            r = requests.get(feed_url, timeout=req_timeout, headers=headers)
            r.raise_for_status()
        except Exception as e:
            print(f"[news] skip {feed_url}: {e}")
            continue

        try:
            feed = feedparser.parse(r.content)
            entries = feed.entries or []
        except Exception as e:
            print(f"[news] parse error {feed_url}: {e}")
            continue

        for entry in entries[:per_feed_limit]:
            title = getattr(entry, "title", None) or ""
            link = getattr(entry, "link", None)
            if not link:
                continue

            # 1) канонизируем URL (срежем utm/рефы, нормализуем хост/путь/квери)
            can_link = canonicalize_url(link)

            # 2) жёсткая уникальность по каноническому URL
            if db.query(Article).filter(Article.url == can_link).first():
                continue

            # 3) нормализуем источник по домену СТАТЬИ (не фида)
            source = (urlparse(can_link).hostname or "unknown").lower()

            # 4) время публикации
            published_at = _parse_published(entry)
            if published_at is not None:
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
                else:
                    published_at = published_at.astimezone(timezone.utc)

            # 5) мягкая дедупликация по заголовку в окне ±48h для того же источника
            #    (избавляет от копий с одинаковыми заголовками)
            title_norm = re.sub(r"\s+", " ", title).strip().lower()
            if published_at is not None:
                since = published_at - timedelta(hours=48)
                until = published_at + timedelta(hours=48)
                recent = (
                    db.query(Article)
                    .filter(Article.source == source)
                    .filter(Article.published_at >= since)
                    .filter(Article.published_at <= until)
                    .order_by(Article.published_at.desc().nullslast())
                    .limit(50)
                    .all()
                )
                if any(re.sub(r"\s+", " ", (r.title or "")).strip().lower() == title_norm for r in recent):
                    continue

            # 6) сохраняем
            art = Article(
                source=source, title=title, url=can_link, published_at=published_at  # <— сохраняем канонический URL
            )
            db.add(art)
            batch += 1
            added += 1

            if batch >= 50:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                batch = 0

            if total_limit and added >= total_limit:
                break

        if total_limit and added >= total_limit:
            break

    if batch:
        try:
            db.commit()
        except Exception:
            db.rollback()

    took = time.time() - start_time
    print(f"[news] fetch done: +{added} in {took:.1f}s from {len(feeds)} feeds")
    return added


def news_stats(db: Session, hours: int = 24) -> Dict[str, Any]:
    """
    Небольшая сводная статистика по новостям за последние N часов:
      - всего статей
      - аннотированных
      - неаннотированных
      - топ-теги (по ArticleAnnotation.tags)
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    total = db.query(Article).count()
    total_24h = db.query(Article).filter(Article.published_at.is_not(None), Article.published_at >= since).count()

    ann_rows = db.query(ArticleAnnotation).all()
    annotated_ids = {a.article_id for a in ann_rows}
    annotated = len(annotated_ids)

    # "неаннотированных" по всей базе (а не только 24 часа)
    unannotated = max(0, total - annotated)

    # топ-теги
    from collections import Counter

    c = Counter()
    for a in ann_rows:
        if a.tags:
            for t in a.tags.split(","):
                t = t.strip().lower()
                if t:
                    c[t] += 1
    top_tags = [{"tag": k, "count": v} for k, v in c.most_common(20)]

    return {
        "total_articles": total,
        "total_articles_24h": total_24h,
        "annotated": annotated,
        "unannotated": unannotated,
        "top_tags": top_tags,
        "window_hours": hours,
    }
