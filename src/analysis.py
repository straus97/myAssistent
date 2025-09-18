# src/analysis.py
import re
from typing import List, Optional, Tuple
from langdetect import detect, DetectorFactory
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from sqlalchemy.orm import Session
from .db import Article, ArticleAnnotation

# Фикс детерминизма langdetect
DetectorFactory.seed = 42

# Инициализируем один раз
_analyzer = SentimentIntensityAnalyzer()

# Простые паттерны для тегов (en/ru):
_PATTERNS = {
    "btc": r"\b(btc|bitcoin|биткоин)\b",
    "eth": r"\b(eth|ethereum|эфириум|эфир)\b",
    "etf": r"\betf\b",
    "sec": r"\bsec\b",
    "hack": r"(hack|exploit|breach|взлом|эксплойт|утечк)",
    "regulation": r"(regulat|ban|prohibit|compliance|запрет|санкц|регулир|регулятор)",
    "listing": r"(list|листинг|список|листингуется)",
    "adoption": r"(adopt|mass|integrat|partnership|партнерств|интеграц|массов)",
    "bullish": r"(surge|rally|рост|быч)",
    "bearish": r"(fall|drop|selloff|crash|падени|медвеж)"
}
_PATTERNS = {k: re.compile(v, re.IGNORECASE) for k, v in _PATTERNS.items()}

def detect_lang(text: str) -> Optional[str]:
    try:
        return detect(text)
    except Exception:
        return None

def sentiment_score(text: str) -> float:
    # compound ∈ [-1..1]; VADER лучше работает на английском
    return float(_analyzer.polarity_scores(text).get("compound", 0.0))

def extract_tags(*texts: str) -> List[str]:
    joined = " ".join([t for t in texts if t])
    tags = [name for name, pat in _PATTERNS.items() if pat.search(joined)]
    return list(sorted(set(tags)))

def analyze_article(article: Article) -> Tuple[Optional[str], Optional[float], List[str]]:
    text = (article.title or "") + " " + (article.summary or "")
    lang = detect_lang(text) if text.strip() else None
    sent = sentiment_score(text) if text.strip() else None
    tags = extract_tags(article.title or "", article.summary or "", article.source or "")
    return lang, sent, tags

def analyze_new_articles(db: Session, limit: int = 100) -> int:
    """
    Находит последние статьи без аннотаций, считает аналитику и сохраняет.
    Возвращает число обработанных статей.
    """
    # Берём последние N статей
    q = db.query(Article).order_by(Article.id.desc()).limit(limit).all()
    processed = 0
    for art in q:
        # Есть ли уже аннотация?
        exists = db.query(ArticleAnnotation).filter(ArticleAnnotation.article_id == art.id).first()
        if exists:
            continue
        lang, sent, tags = analyze_article(art)
        ann = ArticleAnnotation(
            article_id=art.id,
            lang=lang,
            sentiment=sent,
            tags=",".join(tags) if tags else None
        )
        db.add(ann)
        try:
            db.commit()
            processed += 1
        except Exception:
            db.rollback()
    return processed
