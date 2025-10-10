from __future__ import annotations
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
import re
from src.db import Article, ArticleAnnotation
from src.features import TAGS  # используем общий список тегов для связности с фичами

# --- простейшие хелперы ---
_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _detect_lang(text: str) -> str:
    """
    Лёгкая эвристика: считаем долю кириллицы → ru / иначе en.
    (Избегаем внешних зависимостей, чтобы не тянуть модели.)
    """
    if not text:
        return "en"
    s = text
    cyr = sum(1 for ch in s if "а" <= ch.lower() <= "я" or ch in "ё")
    lat = sum(1 for ch in s if "a" <= ch.lower() <= "z")
    return "ru" if cyr > lat else "en"


# Мини-лексикон (двуязычный), чтобы не зависеть от NLTK/TextBlob
POS_RU = {"рост", "бычий", "позитив", "одобрил", "листинг", "интеграция", "прорыв", "рекорд"}
NEG_RU = {
    "падение",
    "медвежий",
    "негатив",
    "запрет",
    "взлом",
    "хак",
    "хакер",
    "регресс",
    "делистинг",
    "штраф",
    "взломан",
}

POS_EN = {"rally", "bullish", "surge", "approval", "approved", "listing", "adoption", "integrates", "record"}
NEG_EN = {"selloff", "bearish", "ban", "hack", "hacked", "exploit", "breach", "delisting", "penalty", "fine"}


def _sentiment(tokens: List[str], lang: str) -> float:
    """
    Возвращает скаляр [-1..1]. Балльная схема: (pos - neg) / (pos + neg + 1).
    """
    if lang == "ru":
        pos = sum(1 for t in tokens if t in POS_RU)
        neg = sum(1 for t in tokens if t in NEG_RU)
    else:
        pos = sum(1 for t in tokens if t in POS_EN)
        neg = sum(1 for t in tokens if t in NEG_EN)
    score = (pos - neg) / (pos + neg + 1.0)
    # чуть «сжимаем», чтобы распределение было компактнее
    return max(-1.0, min(1.0, score))


# Словарь синонимов → канонический тег из TAGS (см. features.py)
_TAG_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "btc": ("btc", "bitcoin", "satoshi"),
    "eth": ("eth", "ethereum"),
    "etf": ("etf",),
    "sec": ("sec", "u.s. sec", "sec chair", "sec lawsuit"),
    "hack": ("hack", "hacked", "exploit", "breach", "хак", "взлом", "хакер", "взломан"),
    "regulation": ("regulation", "regulatory", "law", "ban", "policy"),
    "listing": ("listing", "listed", "lists", "delisting"),
    "adoption": ("adoption", "adopt", "integrates", "accepts"),
    "bullish": ("bullish", "rally", "surge", "бычий", "рост"),
    "bearish": ("bearish", "selloff", "dump", "медвежий", "падение"),
    "halving": ("halving", "halfing"),
}


def _extract_tags(text: str) -> List[str]:
    """
    Выдаём подмножество TAGS, если в тексте встречаются соответствующие синонимы.
    """
    txt = (text or "").lower()
    found: List[str] = []
    for canonical in TAGS:
        syns = _TAG_SYNONYMS.get(canonical, (canonical,))
        if any(re.search(rf"\b{re.escape(s)}\b", txt) for s in syns):
            found.append(canonical)
    # лёгкая дедупликация/сортировка для стабильности
    return sorted(list(set(found)), key=lambda x: TAGS.index(x) if x in TAGS else 999)


# --- основная функция анализа ---


def analyze_new_articles(db: Session, limit: int = 100) -> int:
    """
    Находит статьи без аннотации, вычисляет язык, тональность и теги,
    создаёт ArticleAnnotation. Возвращает количество обработанных.
    """
    # Выбираем только те Article, для которых ещё нет ArticleAnnotation
    rows: List[Article] = (
        db.query(Article)
        .outerjoin(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .filter(ArticleAnnotation.id == None)  # noqa: E711
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )

    processed = 0
    batch = 0
    for art in rows:
        text = f"{art.title or ''}\n{getattr(art, 'summary', '') or ''}"
        lang = _detect_lang(text)
        tokens = _tokenize(text)
        sent = _sentiment(tokens, lang)
        tags = _extract_tags(text)

        ann = ArticleAnnotation(
            article_id=art.id,
            lang=lang,
            sentiment=float(sent),
            tags=",".join(tags) if tags else None,
        )
        db.add(ann)
        processed += 1
        batch += 1

        if batch >= 50:
            try:
                db.commit()
            except Exception:
                db.rollback()
            batch = 0

    if batch:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return processed
