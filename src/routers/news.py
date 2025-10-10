"""
Роутер для работы с новостями (RSS, анализ, sentiment, tags)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone as _tz
from urllib.parse import urlparse

import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok, ok_data
from src.db import Article, ArticleAnnotation, SessionLocal
from src.news import fetch_and_store
from src.analysis import analyze_new_articles
from src.watchlist import list_watchlist
from src.risk import load_policy
from src.notify import send_telegram
from src.utils import _radar_now_utc


router = APIRouter(prefix="/news", tags=["News"])


# ===== Основные эндпоинты новостей =====


@router.post("/fetch")
def news_fetch(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Загрузка RSS новостей из источников"""
    added = fetch_and_store(db)
    return {"status": "ok", "added": added}


@router.get("/latest")
def news_latest(limit: int = 20, db: Session = Depends(get_db)):
    """Получить последние новости"""
    rows = (
        db.query(Article)
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "source": r.source, "title": r.title, "url": r.url, "published_at": r.published_at} for r in rows
    ]


@router.get("/search")
def news_search(q: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
    """Поиск новостей по ключевым словам"""
    q_like = f"%{q.lower()}%"
    rows = (
        db.query(Article)
        .filter((Article.title.ilike(q_like)) | (Article.summary.ilike(q_like)))
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return ok_data(
        [{"id": r.id, "source": r.source, "title": r.title, "url": r.url, "published_at": r.published_at} for r in rows]
    )


@router.post("/analyze")
def news_analyze(limit: int = 100, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Анализ новостей (sentiment + tags)"""
    processed = analyze_new_articles(db, limit=limit)
    return {"status": "ok", "processed": processed}


@router.get("/annotated")
def news_annotated(limit: int = 20, db: Session = Depends(get_db)):
    """Получить новости с sentiment-аннотациями"""
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for art, ann in rows:
        out.append(
            {
                "id": art.id,
                "source": art.source,
                "title": art.title,
                "url": art.url,
                "published_at": art.published_at,
                "lang": ann.lang,
                "sentiment": ann.sentiment,
                "tags": ann.tags.split(",") if ann.tags else [],
            }
        )
    return out


@router.get("/by_tag")
def news_by_tag(tag: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
    """Получить новости по тегу"""
    tag = tag.lower()
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .filter(ArticleAnnotation.tags.ilike(f"%{tag}%"))
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for art, ann in rows:
        out.append(
            {
                "id": art.id,
                "source": art.source,
                "title": art.title,
                "url": art.url,
                "published_at": art.published_at,
                "lang": ann.lang,
                "sentiment": ann.sentiment,
                "tags": ann.tags.split(",") if ann.tags else [],
            }
        )
    return out


# ===== News Radar (burst detection) =====


class NewsRadarRequest(BaseModel):
    """Запрос для News Radar (детектор всплесков новостей)"""

    window_minutes: Optional[int] = None
    lookback_windows: Optional[int] = None
    symbols: Optional[Dict[str, list[str]]] = None
    notify: bool = True


_NR_STATE_PATH = Path("artifacts/state/news_radar_state.json")
_NR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _wl_keywords_default() -> Dict[str, list[str]]:
    """Формирует ключевые слова для мониторинга из watchlist"""
    mapping: Dict[str, list[str]] = {}
    try:
        for p in list_watchlist():
            sym = (p.get("symbol") or "").upper()
            base = sym.split("/")[0] if "/" in sym else sym
            if base:
                mapping[sym] = list({base.lower()})
    except Exception:
        pass
    mapping.setdefault("BTC/USDT", ["btc", "bitcoin"])
    mapping.setdefault("ETH/USDT", ["eth", "ethereum"])
    return mapping


def _news_radar_metrics(db: Session, window_minutes: int, lookback_windows: int, symbols_kw: Dict[str, list[str]]):
    """Вычисляет метрики всплесков новостей по символам"""
    now = _radar_now_utc()
    win = timedelta(minutes=int(window_minutes))
    total_back = (lookback_windows + 1) * win
    since = now - total_back

    rows = (
        db.query(Article, ArticleAnnotation)
        .outerjoin(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .filter(Article.published_at >= since)
        .order_by(Article.published_at.asc().nullslast())
        .all()
    )

    def _bucket_index(ts: datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_tz.utc)
        delta = ts - since
        i = int(delta.total_seconds() // win.total_seconds())
        return max(0, min(lookback_windows, i))

    out = []
    for sym, kw in (symbols_kw or {}).items():
        kw_l = [k.lower() for k in kw if k] or []
        if not kw_l:
            continue

        buckets = [[] for _ in range(lookback_windows + 1)]
        for art, ann in rows:
            ts = art.published_at or art.created_at or now
            i = _bucket_index(ts)
            title = (art.title or "").lower()
            summ = (getattr(art, "summary", None) or "").lower()
            tags = (ann.tags if ann else "") or ""
            tags_l = tags.lower()
            if any(k in title or k in summ or k in tags_l for k in kw_l):
                buckets[i].append((art, ann))

        cur = buckets[-1]
        prev = buckets[:-1]
        n_current = len(cur)
        n_prev_avg = (sum(len(b) for b in prev) / float(max(1, len(prev)))) if prev else 0.0
        if n_prev_avg > 0:
            ratio = n_current / n_prev_avg
        else:
            ratio = float("inf") if n_current > 0 else 0.0
        ratio = float(min(ratio, 99.0))

        sources = set()
        for a, _ann in cur:
            host = urlparse(a.source or "").netloc or (a.source or "")
            host = host.lower().strip()
            if host:
                sources.add(host)

        s_vals = [float(_ann.sentiment) for (_a, _ann) in cur if (_ann and _ann.sentiment is not None)]
        s_mean = (sum(s_vals) / len(s_vals)) if s_vals else 0.0
        examples = [a.title for (a, _ann) in cur if a.title][:3]

        out.append(
            {
                "symbol": sym,
                "keywords": kw_l,
                "n_current": int(n_current),
                "n_prev_avg": float(n_prev_avg),
                "ratio": float(ratio),
                "unique_sources": len(sources),
                "sentiment_mean": float(s_mean),
                "sentiment_abs": float(abs(s_mean)),
                "examples": examples,
            }
        )
    out.sort(key=lambda x: (x["ratio"], x["n_current"], x["unique_sources"]), reverse=True)
    return out


def _nr_cfg(policy: dict) -> dict:
    """Извлекает конфигурацию News Radar из policy"""
    d = (policy or {}).get("news_radar") or {}
    return {
        "enabled": bool(d.get("enabled", True)),
        "window_minutes": int(d.get("window_minutes", 60)),
        "lookback_windows": int(d.get("lookback_windows", 6)),
        "min_new": int(d.get("min_new", 6)),
        "min_ratio_vs_prev": float(d.get("min_ratio_vs_prev", 2.0)),
        "min_unique_sources": int(d.get("min_unique_sources", 3)),
        "min_sentiment_abs": float(d.get("min_sentiment_abs", 0.0)),
        "symbols": d.get("symbols")
        or {
            "BTC/USDT": ["btc", "bitcoin"],
            "ETH/USDT": ["eth", "ethereum"],
        },
        "cooldown_minutes": int(d.get("cooldown_minutes", 60)),
    }


def _nr_load_state() -> dict:
    """Загружает состояние News Radar из JSON"""
    try:
        return json.loads(_NR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _nr_save_state(st: dict) -> None:
    """Сохраняет состояние News Radar в JSON"""
    _NR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NR_STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _news_radar_compute(
    db: Session,
    window_minutes: int,
    lookback_windows: int,
    symbols_kw: Dict[str, list[str]],
    min_new: int,
    min_ratio: float,
    min_sources: int,
    min_sent_abs: float,
):
    """
    Единое ядро: считает buckets, метрики и отбирает алерты.
    Возвращает {"metrics":[...], "alerts":[...]}.
    """
    metrics = _news_radar_metrics(db, window_minutes, lookback_windows, symbols_kw)

    alerts = []
    for m in metrics:
        if (
            m["n_current"] >= min_new
            and m["ratio"] >= min_ratio
            and m["unique_sources"] >= min_sources
            and m["sentiment_abs"] >= min_sent_abs
        ):
            alerts.append(m)
    return {"metrics": metrics, "alerts": alerts}


@router.post("/radar")
def news_radar(req: NewsRadarRequest, db: Session = Depends(get_db)):
    """News Radar - детектор всплесков новостей по символам"""
    policy = load_policy()
    cfg = _nr_cfg(policy)
    enabled = bool(cfg["enabled"])

    window_minutes = int(req.window_minutes or cfg.get("window_minutes", 90))
    lookback_windows = int(req.lookback_windows or cfg.get("lookback_windows", 6))
    symbols = req.symbols or cfg.get("symbols") or _wl_keywords_default()
    min_new = int(cfg.get("min_new", 6))
    min_ratio = float(cfg.get("min_ratio_vs_prev", 2.0))
    min_sources = int(cfg.get("min_unique_sources", 3))
    min_sent_abs = float(cfg.get("min_sentiment_abs", 0.0))

    out = _news_radar_compute(db, window_minutes, lookback_windows, symbols, min_new, min_ratio, min_sources, min_sent_abs)
    metrics, alerts = out["metrics"], out["alerts"]

    if (req.notify and enabled) and alerts:
        st = _nr_load_state()
        now = _radar_now_utc()
        cool_min = int(cfg.get("cooldown_minutes", 60))

        for a in alerts[:5]:
            key = f"nr_last:{a['symbol']}"
            last_iso = st.get(key)
            last_dt = pd.to_datetime(last_iso) if last_iso else None
            if last_dt is not None and (now - last_dt) < timedelta(minutes=cool_min):
                continue
            try:
                msg = (
                    "🛰️ NEWS RADAR\n"
                    f"{a['symbol']} • {a['n_current']} стат. за {window_minutes}м "
                    f"(в {a['unique_sources']} источ.) — {a['ratio']:.1f}× чаще обычного\n"
                    f"Sent={a['sentiment_mean']:+.2f}\n"
                    + ("Примеры: " + " • ".join(a["examples"]) if a["examples"] else "")
                )
                send_telegram(msg)
                st[key] = now.isoformat()
                _nr_save_state(st)
            except Exception:
                pass

    return {
        "status": "ok",
        "window_minutes": window_minutes,
        "lookback_windows": lookback_windows,
        "metrics": metrics,
        "alerts": alerts,
    }


# ===== Job функция для APScheduler =====


def job_news_radar():
    """Фоновая задача для News Radar (вызывается планировщиком)"""
    policy = load_policy()
    cfg = policy.get("news_radar") or {}
    if not bool(cfg.get("enabled", False)):
        return
    window_minutes = int(cfg.get("window_minutes", 90))
    lookback_windows = int(cfg.get("lookback_windows", 6))
    symbols = cfg.get("symbols") or _wl_keywords_default()
    with SessionLocal() as db:
        res = news_radar(
            NewsRadarRequest(
                window_minutes=window_minutes, lookback_windows=lookback_windows, symbols=symbols, notify=True
            ),
            db,  # type: ignore
        )
        return res

