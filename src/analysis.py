from __future__ import annotations
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
import re
import logging
from src.db import Article, ArticleAnnotation
from src.features import TAGS  # используем общий список тегов для связности с фичами

logger = logging.getLogger(__name__)

# FinBERT pipeline (lazy loading)
_finbert_pipeline = None

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


# --- FinBERT sentiment analysis ---


def _get_finbert_pipeline():
    """
    Lazy loading FinBERT pipeline. Загружает модель только при первом вызове.
    """
    global _finbert_pipeline
    if _finbert_pipeline is None:
        try:
            from transformers import pipeline
            logger.info("[FinBERT] Loading ProsusAI/finbert model...")
            _finbert_pipeline = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                device=-1,  # CPU (device=0 для GPU)
                truncation=True,
                max_length=512,
            )
            logger.info("[FinBERT] Model loaded successfully")
        except Exception as e:
            logger.error(f"[FinBERT] Failed to load model: {e}")
            _finbert_pipeline = False  # Mark as failed to avoid repeated attempts
    return _finbert_pipeline if _finbert_pipeline is not False else None


def sentiment_finbert(text: str) -> Dict[str, float]:
    """
    Анализ sentiment через FinBERT (ProsusAI/finbert).
    
    Returns:
        {
            "label": "positive" | "negative" | "neutral",
            "score": 0.0-1.0 (confidence),
            "sentiment": -1.0-1.0 (normalized: -1=negative, 0=neutral, 1=positive)
        }
    """
    pipeline_obj = _get_finbert_pipeline()
    if pipeline_obj is None:
        # Fallback to lexicon-based if FinBERT unavailable
        logger.warning("[FinBERT] Model not available, using lexicon fallback")
        tokens = _tokenize(text)
        lang = _detect_lang(text)
        sent = _sentiment(tokens, lang)
        return {
            "label": "positive" if sent > 0.1 else ("negative" if sent < -0.1 else "neutral"),
            "score": abs(sent),
            "sentiment": sent,
        }
    
    try:
        # Truncate text to avoid OOM
        text_truncated = text[:2000] if len(text) > 2000 else text
        
        result = pipeline_obj(text_truncated)[0]
        label = result["label"].lower()
        confidence = result["score"]
        
        # Map label to sentiment score [-1..1]
        sentiment_map = {
            "positive": 1.0,
            "neutral": 0.0,
            "negative": -1.0,
        }
        sentiment_score = sentiment_map.get(label, 0.0) * confidence
        
        return {
            "label": label,
            "score": confidence,
            "sentiment": sentiment_score,
        }
    except Exception as e:
        logger.error(f"[FinBERT] Error during inference: {e}")
        # Fallback to lexicon
        tokens = _tokenize(text)
        lang = _detect_lang(text)
        sent = _sentiment(tokens, lang)
        return {
            "label": "positive" if sent > 0.1 else ("negative" if sent < -0.1 else "neutral"),
            "score": abs(sent),
            "sentiment": sent,
        }


def sentiment_finbert_batch(texts: List[str], batch_size: int = 8) -> List[Dict[str, float]]:
    """
    Batch inference для эффективности. Обрабатывает несколько текстов за раз.
    """
    pipeline_obj = _get_finbert_pipeline()
    if pipeline_obj is None:
        # Fallback to sequential lexicon processing
        return [sentiment_finbert(text) for text in texts]
    
    results = []
    try:
        # Truncate texts
        texts_truncated = [text[:2000] if len(text) > 2000 else text for text in texts]
        
        # Process in batches
        for i in range(0, len(texts_truncated), batch_size):
            batch = texts_truncated[i : i + batch_size]
            batch_results = pipeline_obj(batch)
            
            for result in batch_results:
                label = result["label"].lower()
                confidence = result["score"]
                sentiment_map = {
                    "positive": 1.0,
                    "neutral": 0.0,
                    "negative": -1.0,
                }
                sentiment_score = sentiment_map.get(label, 0.0) * confidence
                
                results.append({
                    "label": label,
                    "score": confidence,
                    "sentiment": sentiment_score,
                })
    except Exception as e:
        logger.error(f"[FinBERT] Batch inference error: {e}")
        # Fallback to sequential lexicon processing
        return [sentiment_finbert(text) for text in texts]
    
    return results


# --- основная функция анализа ---


def analyze_new_articles(db: Session, limit: int = 100, use_finbert: bool = False) -> int:
    """
    Находит статьи без аннотации, вычисляет язык, тональность и теги,
    создаёт ArticleAnnotation. Возвращает количество обработанных.
    
    Args:
        db: SQLAlchemy session
        limit: Максимальное количество статей для обработки
        use_finbert: Использовать FinBERT вместо лексиконов (медленнее, но точнее)
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

    if not rows:
        return 0

    logger.info(f"[Analysis] Processing {len(rows)} articles (use_finbert={use_finbert})")

    processed = 0
    batch = 0
    
    if use_finbert:
        # Batch processing with FinBERT (более эффективно)
        texts = [f"{art.title or ''}\n{getattr(art, 'summary', '') or ''}" for art in rows]
        finbert_results = sentiment_finbert_batch(texts, batch_size=8)
        
        for art, finbert_res in zip(rows, finbert_results):
            text = f"{art.title or ''}\n{getattr(art, 'summary', '') or ''}"
            lang = _detect_lang(text)
            tags = _extract_tags(text)
            
            ann = ArticleAnnotation(
                article_id=art.id,
                lang=lang,
                sentiment=float(finbert_res["sentiment"]),
                tags=",".join(tags) if tags else None,
            )
            db.add(ann)
            processed += 1
            batch += 1
            
            if batch >= 50:
                try:
                    db.commit()
                except Exception as e:
                    logger.error(f"[Analysis] Commit error: {e}")
                    db.rollback()
                batch = 0
    else:
        # Lexicon-based processing (быстрее)
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
                except Exception as e:
                    logger.error(f"[Analysis] Commit error: {e}")
                    db.rollback()
                batch = 0

    if batch:
        try:
            db.commit()
        except Exception as e:
            logger.error(f"[Analysis] Final commit error: {e}")
            db.rollback()

    logger.info(f"[Analysis] Processed {processed} articles")
    return processed
