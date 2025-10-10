from __future__ import annotations
import os
import sys
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Literal, List, Optional
from datetime import datetime, timedelta, timezone as _tz
from urllib.parse import urlparse
import pandas as pd
from fastapi import Depends, Query, HTTPException, APIRouter, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from src.risk_schema import Policy as RiskPolicy
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text as _sa_text
from sqlalchemy import inspect as _sa_inspect
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.db import (
    SessionLocal,
    Message,
    Article,
    ArticleAnnotation,
    Price,
    ModelRun,
    SignalEvent,
    SignalOutcome,
    PaperPosition,
    PaperOrder,
    PaperTrade,
)
from src.modeling import train_xgb_and_save, load_latest_model, load_model_from_path
from src.news import fetch_and_store
from src.analysis import analyze_new_articles
from src.prices import fetch_and_store_prices
from src.features import build_dataset
from src.reports import build_daily_report
from src.risk import load_policy, save_policy, evaluate_filters
from src.notify import get_notify_config, save_notify_config, send_telegram, maybe_send_signal_notification
from src.trade import paper_open_buy_auto, paper_close_pair, paper_get_positions, paper_get_equity, paper_get_orders
from src.watchlist import (
    list_watchlist,
    set_watchlist,
    add_pair as wl_add_pair,
    remove_pair as wl_remove_pair,
    pairs_for_jobs,
    discover_pairs,
)
from src.model_registry import load_model_for, set_active_model, get_active_model_path, choose_latest_model_path
from src.model_policy import load_model_policy, save_model_policy
from src.champion import eval_model_oos, compare_and_maybe_promote
from fastapi.middleware.cors import CORSMiddleware
from src.cmd_parser import _parse_trade_cmd
from typing import Any as _Any

_HTTPException = HTTPException

API_KEY = (os.getenv("API_KEY") or "").strip()
print(f"[config] API_KEY loaded: {bool(API_KEY)}")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def ok(**kwargs) -> dict:
    return {"status": "ok", **kwargs}


def ok_data(data):
    return {"status": "ok", "data": data}


def err(code: str, detail: _Any = None, http: int = 400):
    # Единый способ отдавать ошибки
    raise _HTTPException(status_code=http, detail={"status": "error", "code": code, "detail": detail})


# Заменяем require_api_key на унифицированный
def require_api_key(x_api_key: Optional[str] = Security(api_key_header)):
    if not API_KEY:
        err("auth.server_misconfigured", "Set env API_KEY", 503)
    if not x_api_key:
        err("auth.missing", "Provide X-API-Key header", 401)
    if x_api_key != API_KEY:
        err("auth.invalid", "X-API-Key is invalid", 401)
    return True


# ---- флаги docs
USE_OFFLINE = os.getenv("OFFLINE_DOCS", "1") == "1"
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "1") == "1"

# --- trade guard (kill switch) ---
_TRADE_GUARD_PATH = Path("artifacts/state/trade_guard.json")
_TRADE_GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)


def _trade_guard_load() -> dict:
    try:
        st = json.loads(_TRADE_GUARD_PATH.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    # env-переопределение: TRADE_MODE=locked|close_only|live
    env_mode = (os.getenv("TRADE_MODE") or "").strip().lower()
    if env_mode in ("locked", "close_only", "live"):
        st["mode"] = env_mode
    if "mode" not in st:
        st["mode"] = "live"
    return st


def _trade_guard_save(st: dict) -> None:
    st = dict(st or {})
    st.setdefault("mode", "live")
    st["updated_at"] = _now_utc().replace(microsecond=0).isoformat()
    _TRADE_GUARD_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


# kind: open (buy/short/open), reduce (partial sell), close (close/cover), admin (reset/cash/etc)
def _trade_guard_enforce(kind: Literal["open", "reduce", "close", "admin"]) -> None:
    st = _trade_guard_load()
    mode = (st.get("mode") or "live").lower()
    allowed = {
        "live": {"open", "reduce", "close", "admin"},
        "close_only": {"reduce", "close"},
        "locked": set(),
    }.get(mode, {"open", "reduce", "close", "admin"})
    if kind not in allowed:
        reason = st.get("reason")
        err("trade.locked", {"mode": mode, "kind": kind, "reason": reason}, 423)


# Служебные эндпойнты управления стоп-краном
class TradeGuardSet(BaseModel):
    mode: Literal["live", "close_only", "locked"]
    reason: str | None = None


router = APIRouter()

try:
    if USE_OFFLINE:
        from fastapi_offline import FastAPIOffline as _FastAPI
    else:
        from fastapi import FastAPI as _FastAPI
except Exception:
    from fastapi import FastAPI as _FastAPI

    USE_OFFLINE = False

app = _FastAPI(
    title="My Assistant API",
    version="0.7",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    description=(
        "Backend for signals, paper-trading and news radar.\n\n"
        "Auth: send X-API-Key for all endpoints, кроме /, /ping и HTML-панелей.\n"
        "Responses: все ручки возвращают {'status':'ok', ...}. Списки — в поле 'data'.\n"
        "Ошибки: raise HTTPException с detail={'status':'error','code':..., 'detail':...}."
    ),
)

app.include_router(router)


@app.get("/trade/guard", tags=["Trade"])
def trade_guard_get(_=Depends(require_api_key)):
    return _trade_guard_load()


@app.post("/trade/guard", tags=["Trade"])
def trade_guard_set(req: TradeGuardSet, _=Depends(require_api_key)):
    st = _trade_guard_load()
    st["mode"] = req.mode
    st["reason"] = (req.reason or "").strip() or None
    _trade_guard_save(st)
    return {"status": "ok", "state": _trade_guard_load()}


CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
allow_all = CORS_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else CORS_ORIGINS,
    allow_credentials=False if allow_all else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- статика: artifacts ---
Path("artifacts").mkdir(exist_ok=True)
if os.getenv("PUBLIC_ARTIFACTS", "0") == "1":
    app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
else:
    from fastapi.responses import FileResponse

    @app.get("/artifacts/{path:path}", tags=["Files"])
    def artifacts_secure(path: str, _=Depends(require_api_key)):
        full = (Path("artifacts") / path).resolve()
        root = Path("artifacts").resolve()
        if root not in full.parents and full != root:  # защита от traversal
            raise HTTPException(404)
        if not full.is_file() or not str(full).startswith(str(root)):
            raise HTTPException(404)
        return FileResponse(str(full))


# ------------------ утилиты ------------------
def _now_utc() -> datetime:
    try:
        return datetime.now(_tz.utc)
    except Exception:
        return datetime.utcnow().replace(tzinfo=_tz.utc)


def _radar_now_utc() -> datetime:
    return _now_utc()


def _to_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz.utc)
    return int(dt.timestamp() * 1000)


_TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def _tf_minutes(tf: str) -> int:
    tf = (tf or "").lower()
    if tf in _TF_MIN:
        return _TF_MIN[tf]
    if tf.endswith("m"):
        try:
            return int(tf[:-1])
        except:
            return 60
    if tf.endswith("h"):
        try:
            return int(tf[:-1]) * 60
        except:
            return 60
    if tf.endswith("d"):
        try:
            return int(tf[:-1]) * 1440
        except:
            return 1440
    return 60


def _deep_merge_policy(base: dict, updates: dict) -> dict:
    """
    Рекурсивно мёрджит словари: вложенные dict-ы объединяются, остальные значения перезаписываются.
    Списки НЕ склеиваются — второе значение полностью заменяет первое.
    """
    out = dict(base or {})
    for k, v in (updates or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_policy(out[k], v)
        else:
            out[k] = v
    return out


def _policy_vol_thr(policy: dict, timeframe: str) -> dict:
    tf = (timeframe or "1h").lower()
    v = (policy or {}).get("volatility_thresholds") or {}
    defaults = {
        "15m": {"dead": 0.0025, "hot": 0.0090},
        "1h": {"dead": 0.0040, "hot": 0.0150},
        "4h": {"dead": 0.0060, "hot": 0.0200},
        "1d": {"dead": 0.0100, "hot": 0.0300},
    }
    if tf in v:
        return {"dead": float(v[tf]["dead"]), "hot": float(v[tf]["hot"])}
    if tf.endswith("m"):
        return defaults["15m"]
    if tf.endswith("h"):
        return defaults["1h"]
    if tf.endswith("d"):
        return defaults["1d"]
    return defaults["1h"]


def _atr_pct(df: pd.DataFrame, window: int = 14) -> float:
    df = df[["high", "low", "close"]].copy()
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(window, min_periods=window).mean()
    val = (atr / df["close"]).iloc[-1]
    return float(val) if pd.notna(val) else float("nan")


# ------------------ debug ------------------
@app.get("/")
def _root():
    return RedirectResponse("/docs" if ENABLE_DOCS else "/ping")


@app.get("/ping")
def _ping():
    return {"pong": True}


@app.get("/_debug/info")
def _debug_info(_=Depends(require_api_key)):
    return {
        "main_file": __file__,
        "cwd": os.getcwd(),
        "sys_path_top": sys.path[:5],
        "routes": sorted([getattr(r, "path", str(r)) for r in app.routes])[:200],
    }


@app.get("/_debug/env")
def _debug_env(_=Depends(require_api_key)):
    length = len(API_KEY)
    return {"API_KEY_present": bool(API_KEY), "API_KEY_length": length}


# лог загрузки модулей
try:
    from src import risk as _risk

    print("[boot] risk module:", _risk.__file__)
except Exception as e:
    print("[boot] risk import ERROR:", e)
try:
    from src import notify as _notify

    print("[boot] notify module:", _notify.__file__)
except Exception as e:
    print("[boot] notify import ERROR:", e)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------ базовые эндпоинты ------------------
@app.get("/hello", tags=["Memory"])
def say_hello(name: str = "Никита"):
    return {"message": f"Привет, {name}! 🚀 Ассистент работает."}


@app.get("/time", tags=["Memory"])
def get_time():
    return {"time": _now_utc().strftime("%Y-%m-%d %H:%M:%S %Z")}


@app.post("/memory/add", tags=["Memory"])
def add_message(text: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}


@app.get("/memory/add", tags=["Memory"])
def add_message_get(text: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    msg = Message(text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "text": msg.text, "created_at": msg.created_at}


@app.get("/memory/all", tags=["Memory"])
def get_messages(db: Session = Depends(get_db), _=Depends(require_api_key)):
    msgs = db.query(Message).order_by(Message.id.desc()).all()
    return [{"id": m.id, "text": m.text, "created_at": m.created_at} for m in msgs]


# ------------------ новости и аналитика ------------------
@app.post("/news/fetch", tags=["News"])
def news_fetch(db: Session = Depends(get_db), _=Depends(require_api_key)):
    added = fetch_and_store(db)
    return {"status": "ok", "added": added}


@app.get("/news/latest", tags=["News"])
def news_latest(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(Article)
        .order_by(Article.published_at.is_(None), Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "source": r.source, "title": r.title, "url": r.url, "published_at": r.published_at} for r in rows
    ]


@app.get("/news/search", tags=["News"])
def news_search(q: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
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


@app.post("/news/analyze", tags=["News"])
def news_analyze(limit: int = 100, db: Session = Depends(get_db), _=Depends(require_api_key)):
    processed = analyze_new_articles(db, limit=limit)
    return {"status": "ok", "processed": processed}


@app.get("/news/annotated", tags=["News"])
def news_annotated(limit: int = 20, db: Session = Depends(get_db)):
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


@app.get("/news/by_tag", tags=["News"])
def news_by_tag(tag: str = Query(..., min_length=2), limit: int = 30, db: Session = Depends(get_db)):
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
    window_minutes: int | None = None
    lookback_windows: int | None = None
    symbols: Dict[str, list[str]] | None = None
    notify: bool = True


def _wl_keywords_default() -> Dict[str, list[str]]:
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


_NR_STATE_PATH = Path("artifacts/state/news_radar_state.json")
_NR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

_MON_STATE_PATH = Path("artifacts/state/monitor_state.json")


def _mon_load_state() -> dict:
    try:
        return json.loads(_MON_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mon_save_state(st: dict) -> None:
    _MON_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MON_STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _nr_load_state() -> dict:
    try:
        return json.loads(_NR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _nr_save_state(st: dict) -> None:
    _NR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NR_STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _volatility_guard(row, df: pd.DataFrame, timeframe: str, policy: dict):
    thr = _policy_vol_thr(policy, timeframe)
    try:
        atrp = _atr_pct(df.tail(200))
    except Exception:
        atrp = float("nan")
    if pd.isna(atrp):
        state = "normal"
    else:
        state = "dead" if atrp < thr["dead"] else ("hot" if atrp >= thr["hot"] else "normal")
    metrics = {"atr_pct": atrp, "vol_state": state, "vol_thr_dead": thr["dead"], "vol_thr_hot": thr["hot"]}
    block = bool((policy or {}).get("block_if_dead_volatility", True))
    if block and state == "dead":
        return False, [f"dead_volatility: ATR% {atrp:.2%} < {thr['dead']:.2%}"], metrics
    return True, [], metrics


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
        # два способа учёта «тональности»:
        # (а) mean(abs(sentiment)) за текущий срез (уже есть в metrics как sentiment_abs)
        # (б) (опционально) можно фильтровать статьи на входе; оставляем (а) как стабильное правило
        if (
            m["n_current"] >= min_new
            and m["ratio"] >= min_ratio
            and m["unique_sources"] >= min_sources
            and m["sentiment_abs"] >= min_sent_abs
        ):
            alerts.append(m)
    return {"metrics": metrics, "alerts": alerts}


@app.post("/news/radar", tags=["News"])
def news_radar(req: NewsRadarRequest, db: Session = Depends(get_db)):
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

    out = _news_radar_compute(
        db, window_minutes, lookback_windows, symbols, min_new, min_ratio, min_sources, min_sent_abs
    )
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


def job_news_radar():
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


# ------------------ цены / датасет / модель ------------------
class PriceFetchRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    limit: int = 500


@app.post("/prices/fetch", tags=["Prices"])
def prices_fetch(req: PriceFetchRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    try:
        added = fetch_and_store_prices(db, req.exchange, req.symbol, req.timeframe, req.limit)
        return ok(added=added)
    except Exception as e:
        err("prices.fetch_failed", str(e), 500)


@app.get("/prices/latest", tags=["Prices"])
def prices_latest(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    rows = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return ok_data(
        [{"ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume} for r in rows]
    )


@app.get("/market/volatility", tags=["Market"])
def market_volatility(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    df, _ = build_dataset(db, exchange, symbol, timeframe, 12)
    if df.empty:
        return {"status": "error", "detail": "нет данных"}
    atrp = _atr_pct(df.tail(200))
    thr = _policy_vol_thr(load_policy(), timeframe)
    if pd.isna(atrp):
        state = "normal"
    else:
        state = "dead" if atrp < thr["dead"] else ("hot" if atrp >= thr["hot"] else "normal")
    return {
        "status": "ok",
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "atr_pct": atrp,
        "dead_thr": thr["dead"],
        "hot_thr": thr["hot"],
        "state": state,
    }


class MonitorPreviewItem(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    type: Literal["partial", "flat"]
    qty: float
    avg: float
    last: float
    ret_pct: float
    pnl_abs: float
    state_key: str
    last_ts: Optional[str] = None
    last_ret: Optional[float] = None
    ok_cooldown: bool
    ok_change: bool
    would_send: bool


class MonitorPreviewResponse(BaseModel):
    status: Literal["ok"]
    preview: List[MonitorPreviewItem]


@app.get("/monitor/preview", tags=["Trade"], response_model=MonitorPreviewResponse)
def monitor_preview(db: Session = Depends(get_db)):
    policy = load_policy()
    cfg = _monitor_cfg(policy)
    tf = cfg["timeframe"]
    cool = int(cfg["cooldown_minutes"])
    min_delta = float(cfg["min_ret_change"])

    st = _mon_load_state()
    now = _now_utc()
    out = []

    # === NEW: merge DB + JSON, с дедупом в пользу БД ===
    merged = {}
    for pos in db.query(PaperPosition).all():
        merged[(pos.exchange, pos.symbol)] = {
            "exchange": pos.exchange,
            "symbol": pos.symbol,
            "qty": float(pos.qty or 0.0),
            "avg": float(pos.avg_price or 0.0),
        }
    try:
        for p in paper_get_positions():
            key = (p["exchange"], p["symbol"])
            if key in merged:
                continue
            merged[key] = {
                "exchange": p["exchange"],
                "symbol": p["symbol"],
                "qty": float(p.get("qty", 0.0)),
                "avg": float(p.get("avg_price", 0.0)),
            }
    except Exception:
        pass
    rows = list(merged.values())
    # === /NEW

    for pos in rows:
        if not pos or float(pos["qty"]) <= 0:
            continue
        ex, sym = pos["exchange"], pos["symbol"]
        # фильтры only/exclude
        only = cfg.get("only_symbols") or []
        excl = cfg.get("exclude_symbols") or []
        if only and sym not in only:
            continue
        if excl and sym in excl:
            continue

        avg = float(pos["avg"])
        last = _last_close(db, ex, sym, tf) or avg
        ret = (last / avg - 1.0) if avg > 0 else 0.0
        pnl_abs = (last - avg) * float(pos["qty"])

        kind = "flat" if ret <= cfg["flat_after"] else ("partial" if ret >= cfg["partial_at"] else None)
        if not kind or kind not in (cfg.get("types") or ["partial", "flat"]):
            continue

        key = f"{ex}:{sym}:{tf}:{kind}"
        rec = st.get(key) or {}
        last_ts = pd.to_datetime(rec.get("ts")) if rec.get("ts") else None
        last_ret = float(rec.get("ret")) if rec.get("ret") is not None else None

        ok_cooldown = True if not last_ts else (now - last_ts) >= timedelta(minutes=cool)
        ok_change = True if last_ret is None else abs(ret - last_ret) >= min_delta
        would_send = bool(ok_cooldown or ok_change)

        out.append(
            {
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "type": kind,
                "qty": float(pos["qty"]),
                "avg": avg,
                "last": last,
                "ret_pct": ret,
                "pnl_abs": pnl_abs,
                "state_key": key,
                "last_ts": (rec.get("ts") if rec else None),
                "last_ret": last_ret,
                "ok_cooldown": ok_cooldown,
                "ok_change": ok_change,
                "would_send": would_send,
            }
        )
    return {"status": "ok", "preview": out}


@app.get("/meta", tags=["Debug"])
def meta():
    return ok(version=app.version, trade_mode=_trade_guard_load().get("mode"))


@app.get("/meta/capabilities", tags=["Debug"])
def meta_capabilities(_=Depends(require_api_key)):
    """
    Возможности бэка и полезные подсказки для UI.
    - can_short/can_cover: есть ли ручки для шорта/покрытия
    - buy_usd: дефолтная сумма для быстрой покупки в UI (если есть policy.ui.buy_usd — берём её)
    - guard: режим стоп-крана
    - monitor/notify: активные настройки (чтобы UI мог при желании отрисовать статусы)
    """
    policy = load_policy() or {}
    ui_cfg = policy.get("ui") or {}
    buy_usd = float(ui_cfg.get("buy_usd", 100))  # можно переопределить в policy.json -> {"ui":{"buy_usd":150}}

    caps = {
        "can_short": True,  # у нас есть /trade/manual/short
        "can_cover": True,  # у нас есть /trade/manual/cover
        "buy_usd": buy_usd,
        "guard": _trade_guard_load(),
        "monitor": _monitor_cfg(policy),
        "notify": (policy.get("notify") or {}),
    }
    return ok(**caps)


class DatasetBuildRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 6


@app.post("/dataset/build", tags=["Dataset"])
def dataset_build(req: DatasetBuildRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    try:
        df, feature_cols = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if df.empty:
            err("dataset.empty", "пустой датасет", 409)
        info = {
            "rows": int(len(df)),
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "n_features": len(feature_cols),
            "features": feature_cols[:10] + (["..."] if len(feature_cols) > 10 else []),
        }
        Path("artifacts").mkdir(exist_ok=True)
        csv_rel = Path("artifacts") / "dataset_preview.csv"
        df.head(200).to_csv(csv_rel, encoding="utf-8")
        info["preview_csv_url"] = f"/artifacts/{csv_rel.name}"
        return ok(info=info)
    except Exception as e:
        err("dataset.build_failed", str(e), 500)


class ModelTrainRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 6


@app.post("/model/train", tags=["Model"])
def model_train(req: ModelTrainRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    try:
        df, feature_cols = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if len(df) < 200:
            return {"status": "error", "detail": "Данных слишком мало (<200 строк) для тренировки."}
        metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
        run = ModelRun(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            horizon_steps=req.horizon_steps,
            n_train=metrics["n_train"],
            n_test=metrics["n_test"],
            accuracy=metrics.get("accuracy"),
            roc_auc=metrics.get("roc_auc"),
            threshold=metrics.get("threshold"),
            total_return=metrics.get("total_return"),
            sharpe_like=metrics.get("sharpe_like"),
            model_path=model_path,
            features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return {"status": "ok", "metrics": metrics, "run_id": run.id, "model_path": model_path}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/model/train_missing", tags=["Model"])
def model_train_missing(db: Session = Depends(get_db), _=Depends(require_api_key)):
    return _train_missing_impl(db)


@app.get("/model/runs", tags=["Model"])
def model_runs(
    limit: int = 50,
    exchange: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    horizon_steps: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ModelRun)
    if exchange:
        q = q.filter(ModelRun.exchange == exchange)
    if symbol:
        q = q.filter(ModelRun.symbol == symbol)
    if timeframe:
        q = q.filter(ModelRun.timeframe == timeframe)
    if horizon_steps is not None:
        q = q.filter(ModelRun.horizon_steps == horizon_steps)
    rows = q.order_by(ModelRun.id.desc()).limit(limit).all()

    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "created_at": r.created_at,
                "exchange": r.exchange,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "horizon_steps": r.horizon_steps,
                "n_train": r.n_train,
                "n_test": r.n_test,
                "accuracy": r.accuracy,
                "roc_auc": r.roc_auc,
                "threshold": r.threshold,
                "total_return": r.total_return,
                "sharpe_like": r.sharpe_like,
                "model_path": r.model_path,
            }
        )
    return out


# --- Model Policy (SLA) ---
@app.get("/model/policy", tags=["Model"])
def model_policy_get():
    return load_model_policy()


class ModelPolicyUpdate(BaseModel):
    updates: Dict[str, Any]


@app.post("/model/policy", tags=["Model"])
def model_policy_set(req: ModelPolicyUpdate, _=Depends(require_api_key)):
    cur = load_model_policy()
    cur.update(req.updates or {})
    save_model_policy(cur)
    return {"status": "ok", "policy": load_model_policy()}


# --- Model Health (per watchlist) ---
def _age_days(dt: datetime | None) -> float | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz.utc)
    delta = _now_utc() - dt
    return max(0.0, delta.total_seconds() / 86400.0)


def _last_run_for(db: Session, ex: str, sym: str, tf: str, hz: int):
    return (
        db.query(ModelRun)
        .filter(
            ModelRun.exchange == ex,
            ModelRun.symbol == sym,
            ModelRun.timeframe == tf,
            ModelRun.horizon_steps == hz,
        )
        .order_by(ModelRun.id.desc())
        .first()
    )


def _model_needs_retrain(db: Session, ex: str, sym: str, tf: str, hz: int, policy: dict, df_len: int | None):
    last = _last_run_for(db, ex, sym, tf, hz)
    age = _age_days(last.created_at) if last else None

    if last is None:
        return True, "no_run", {"age_days": None, "roc_auc": None, "df_len": df_len}

    if age is not None and age > float(policy.get("max_age_days", 7)):
        return True, f"stale_{age:.1f}d", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}

    auc_thr = float(policy.get("retrain_if_auc_below", 0.55))
    if (last.roc_auc is not None) and (last.roc_auc < auc_thr):
        return True, f"low_auc_{last.roc_auc:.3f}", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}

    return False, "fresh", {"age_days": age, "roc_auc": last.roc_auc, "df_len": df_len}


@app.get("/model/health", tags=["Model"])
def model_health(db: Session = Depends(get_db)):
    policy = load_model_policy()
    pairs = pairs_for_jobs()
    out = []
    for ex, sym, tf, _ in pairs:
        hz = 6 if tf.endswith("h") else 12
        last = _last_run_for(db, ex, sym, tf, hz)
        age = _age_days(last.created_at) if last else None
        need, reason, meta = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=None)
        out.append(
            {
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "horizon_steps": hz,
                "last_run_id": getattr(last, "id", None),
                "last_created_at": getattr(last, "created_at", None),
                "last_roc_auc": getattr(last, "roc_auc", None),
                "age_days": age,
                "need_retrain": need,
                "reason": reason,
            }
        )
    return out


class ActiveModelSet(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    model_path: str


@app.post("/model/active", tags=["Model"])
def model_active_set(req: ActiveModelSet, _=Depends(require_api_key)):
    set_active_model(req.exchange, req.symbol, req.timeframe, req.horizon_steps, req.model_path)
    return {
        "status": "ok",
        "exchange": req.exchange,
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "horizon_steps": req.horizon_steps,
        "active_model_path": get_active_model_path(req.exchange, req.symbol, req.timeframe, req.horizon_steps),
    }


class OOSEvalRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    run_id: int | None = None
    tail_rows: int = 1800


@app.post("/model/eval_oos", tags=["Model"])
def model_eval_oos(req: OOSEvalRequest, db: Session = Depends(get_db)):
    run = None
    if req.run_id is not None:
        run = db.query(ModelRun).filter(ModelRun.id == req.run_id).first()
        if not run:
            return {"status": "error", "detail": "run_id not found"}
    else:
        path = get_active_model_path(req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if path:
            run = db.query(ModelRun).filter(ModelRun.model_path == path).order_by(ModelRun.id.desc()).first()
        if run is None:
            run = (
                db.query(ModelRun)
                .filter(
                    ModelRun.exchange == req.exchange,
                    ModelRun.symbol == req.symbol,
                    ModelRun.timeframe == req.timeframe,
                    ModelRun.horizon_steps == req.horizon_steps,
                )
                .order_by(ModelRun.id.desc())
                .first()
            )
        if run is None:
            return {"status": "error", "detail": "no suitable run found"}
    try:
        return eval_model_oos(db, run, req.horizon_steps, tail_rows=int(req.tail_rows))
    except Exception as e:
        return {"status": "error", "detail": f"oos_eval: {e.__class__.__name__}: {e}"}


class PromoteIfBetterRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    horizon_steps: int
    min_auc_gain: float = 0.005
    prefer_sharpe: bool = True
    tail_rows: int = 1800
    dry_run: bool = False


@app.post("/model/champion/promote_if_better", tags=["Model"])
def model_promote_if_better(req: PromoteIfBetterRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    return compare_and_maybe_promote(
        db,
        req.exchange,
        req.symbol,
        req.timeframe,
        req.horizon_steps,
        min_auc_gain=float(req.min_auc_gain),
        prefer_sharpe=bool(req.prefer_sharpe),
        tail_rows=int(req.tail_rows),
        dry_run=bool(req.dry_run),
    )


@app.get("/model/active", tags=["Model"])
def model_active_get(exchange: str, symbol: str, timeframe: str, horizon_steps: int, db: Session = Depends(get_db)):
    manual = get_active_model_path(exchange, symbol, timeframe, horizon_steps)
    latest = choose_latest_model_path(db, exchange, symbol, timeframe, horizon_steps)
    source = "manual" if manual else ("latest_from_runs" if latest else None)
    return {
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon_steps": horizon_steps,
        "active_manual": manual,
        "latest_from_runs": latest,
        "source": source,
    }


# ------------------ риск-политика и нотификации ------------------
@app.get("/risk/policy", tags=["Risk"])
def risk_policy_get():
    p = load_policy() or {}
    try:
        p = RiskPolicy.model_validate(p).model_dump(exclude_none=True)
    except ValidationError:
        # если файл кривой — просто вернём как есть (чтобы можно было починить POST'ом)
        pass
    return p


class RiskPolicyUpdate(BaseModel):
    updates: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "updates": {
                    "monitor": {
                        "enabled": True,
                        "timeframe": "15m",
                        "partial_at": 0.03,
                        "partial_size": 0.30,
                        "flat_after": -0.01,
                        "cooldown_minutes": 60,
                        "min_ret_change": 0.005,
                        "types": ["partial", "flat"],  # см. шаг 3
                        "only_symbols": ["ETH/USDT"],  # см. шаг 3
                        "exclude_symbols": [],  # см. шаг 3
                    }
                }
            }
        }
    )


@app.post("/risk/policy", tags=["Risk"])
def risk_policy_set(req: RiskPolicyUpdate, _=Depends(require_api_key)):
    base = load_policy() or {}
    try:
        # если база чистая — используем её
        base = RiskPolicy.model_validate(base).model_dump(exclude_none=True)
    except ValidationError:
        # если в базе мусор/старые поля — начинаем с пустой
        base = {}

    cur = _deep_merge_policy(base, req.updates or {})

    try:
        valid = RiskPolicy.model_validate(cur).model_dump(exclude_none=True)
    except ValidationError as e:
        errs = []
        for er in e.errors():
            loc = ".".join(str(x) for x in er.get("loc", []))
            msg = er.get("msg", "invalid value")
            errs.append(f"{loc}: {msg}")
        raise HTTPException(status_code=422, detail={"status": "error", "errors": errs})
    save_policy(valid)
    return {"status": "ok", "policy": valid}


@app.get("/notify/config", tags=["Notify"])
def notify_get():
    return get_notify_config(mask=True)


class NotifyUpdate(BaseModel):
    enabled: bool | None = None
    telegram_token: str | None = None
    telegram_chat_id: int | None = None
    rules: Dict[str, Any] | None = None


@app.post("/notify/config", tags=["Notify"])
def notify_set(req: NotifyUpdate, _=Depends(require_api_key)):
    cfg = get_notify_config(mask=False)
    if req.enabled is not None:
        cfg["enabled"] = bool(req.enabled)
    if req.telegram_token is not None:
        cfg.setdefault("telegram", {})["token"] = req.telegram_token.strip()
    if req.telegram_chat_id is not None:
        cfg.setdefault("telegram", {})["chat_id"] = int(req.telegram_chat_id)
    if req.rules is not None:
        cfg["rules"] = {**(cfg.get("rules") or {}), **req.rules}
    save_notify_config(cfg)
    return {"status": "ok", "config": get_notify_config(mask=True)}


@app.post("/notify/test", tags=["Notify"])
def notify_test(_=Depends(require_api_key)):
    ok, detail = send_telegram("✅ Тестовое сообщение от My Assistant")
    return {"status": "ok" if ok else "error", "detail": detail}


# ------------------ сигналы ------------------
class SignalRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 12
    model_path: str | None = Field(default=None)


def _last_close(db: Session, exchange: str, symbol: str, timeframe: str) -> float | None:
    r = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .first()
    )
    return float(r.close) if r else None


@app.post("/signal/latest", tags=["Signal"])
def signal_latest(req: SignalRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    try:
        df, _ = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if df.empty:
            return {"status": "error", "detail": "Данных нет. Сначала загрузите цены/новости."}

        row = df.iloc[-1]
        bar_dt = row.name.to_pydatetime()
        close = float(row["close"])

        if req.model_path:
            model, feature_cols, threshold, model_path = load_model_from_path(req.model_path)
        else:
            try:
                model, feature_cols, threshold, model_path = load_model_for(
                    db, req.exchange, req.symbol, req.timeframe, req.horizon_steps
                )
            except FileNotFoundError:
                model, feature_cols, threshold, model_path = load_latest_model()

        missing = [c for c in feature_cols if c not in row.index]
        if missing:
            return {"status": "error", "detail": f"В датасете отсутствуют признаки: {missing[:6]} ..."}
        X = row[feature_cols].values.reshape(1, -1)
        proba = float(model.predict_proba(X)[0, 1])
        base_signal = "buy" if proba > threshold else "flat"
        delta = proba - threshold

        policy = load_policy()
        last_evt = (
            db.query(SignalEvent)
            .filter(
                SignalEvent.exchange == req.exchange,
                SignalEvent.symbol == req.symbol,
                SignalEvent.timeframe == req.timeframe,
            )
            .order_by(SignalEvent.bar_dt.desc())
            .first()
        )
        last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
        allow, reasons, metrics = evaluate_filters(row, df, policy, req.timeframe, last_bar_ts)
        allow_vol, r2, m2 = _volatility_guard(row, df, req.timeframe, policy)
        allow = allow and allow_vol
        reasons += r2
        metrics.update(m2)

        min_gap = float((policy or {}).get("min_prob_gap", 0.02))
        if base_signal == "buy" and delta < min_gap:
            reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
            allow = False

        final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

        evt = SignalEvent(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=req.timeframe,
            horizon_steps=req.horizon_steps,
            bar_dt=bar_dt,
            close=close,
            prob_up=proba,
            threshold=threshold,
            signal=final_signal,
            model_path=model_path,
            note=json.dumps(
                {
                    "base_signal": base_signal,
                    "prob": proba,
                    "threshold": threshold,
                    "prob_gap": delta,
                    "policy": policy,
                    "metrics": metrics,
                    "reasons": reasons,
                },
                ensure_ascii=False,
            ),
        )
        db.add(evt)
        try:
            db.commit()
            db.refresh(evt)
        except Exception:
            db.rollback()

        if evt.id:
            maybe_send_signal_notification(
                final_signal,
                proba,
                threshold,
                delta,
                reasons,
                model_path,
                req.exchange,
                req.symbol,
                req.timeframe,
                bar_dt,
                close,
                source="endpoint",
            )

        return {
            "status": "ok",
            "exchange": req.exchange,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "bar_dt": bar_dt,
            "close": close,
            "prob_up": proba,
            "threshold": threshold,
            "prob_gap": delta,
            "filters_metrics": metrics,
            "reasons": reasons,
            "signal": final_signal,
            "model_path": model_path,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/signal/preview", tags=["Signal"])
def signal_preview(
    exchange: str = "bybit",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    horizon_steps: int = 12,
    model_path: str | None = None,
    db: Session = Depends(get_db),
):
    return _compute_signal_for_last_bar(db, exchange, symbol, timeframe, horizon_steps, model_path)


@app.get("/signals/recent", tags=["Signal"])
def signals_recent(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(SignalEvent).order_by(SignalEvent.bar_dt.desc(), SignalEvent.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        try:
            note = json.loads(r.note or "{}")
        except Exception:
            note = {}
        out.append(
            {
                "created_at": r.created_at,
                "bar_dt": r.bar_dt,
                "exchange": r.exchange,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "horizon_steps": r.horizon_steps,
                "close": r.close,
                "prob_up": r.prob_up,
                "threshold": r.threshold,
                "signal": r.signal,
                "model_path": r.model_path,
                "prob_gap": note.get("prob_gap"),
                "base_signal": note.get("base_signal"),
                "reasons": note.get("reasons"),
            }
        )
    return out


@app.get("/signals/outcomes/recent", tags=["Signal"])
def outcomes_recent(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for o, e in rows:
        out.append(
            {
                "id": o.id,
                "event_id": e.id,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "bar_dt": e.bar_dt,
                "resolved_at": o.resolved_at,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "max_drawdown": o.max_drawdown,
            }
        )
    return out


# ------------------ отчёт ------------------
@app.post("/report/daily", tags=["Report"])
def report_daily(db: Session = Depends(get_db), _=Depends(require_api_key)):
    pairs = [
        ("bybit", "BTC/USDT", "15m"),
        ("bybit", "ETH/USDT", "15m"),
    ]
    path = build_daily_report(db, pairs)
    return {"status": "ok", "path": str(path.resolve())}


@app.get("/report/latest", response_class=HTMLResponse, tags=["Report"])
def report_latest():
    p = Path("artifacts") / "reports" / "latest.html"
    if not p.exists():
        return HTMLResponse("<h3>Отчёт ещё не сформирован</h3>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


# ------------------ бумажная торговля ------------------
class PaperCloseRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"


@app.get("/trade/positions", tags=["Trade"])
def trade_positions(db: Session = Depends(get_db), _=Depends(require_api_key)):
    merged = {}
    try:
        rows = db.query(PaperPosition).all()
    except Exception:
        rows = []
    for p in rows:
        ex, sym = p.exchange, p.symbol
        last = _last_close(db, ex, sym, "15m") or float(p.avg_price or 0.0)
        mv = float(p.qty or 0.0) * last
        merged[(ex, sym)] = {
            "exchange": ex,
            "symbol": sym,
            "timeframe": "15m",
            "qty": float(p.qty or 0.0),
            "avg_price": float(p.avg_price or 0.0),
            "last_price": last,
            "market_value": mv,
            "source": "db",
        }

    try:
        for j in paper_get_positions():
            ex, sym, tf = j["exchange"], j["symbol"], j.get("timeframe", "15m")
            key = (ex, sym)
            if key in merged:
                continue
            last = _last_close(db, ex, sym, tf) or float(j.get("avg_price", 0.0))
            mv = float(j.get("qty", 0.0)) * last
            merged[key] = {
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "qty": float(j.get("qty", 0.0)),
                "avg_price": float(j.get("avg_price", 0.0)),
                "last_price": last,
                "market_value": mv,
                "source": "json",
            }
    except Exception:
        pass

    return list(merged.values())


@app.get("/trade/equity", tags=["Trade"])
def trade_equity(db: Session = Depends(get_db), _=Depends(require_api_key)):
    mtm = {}
    for p in paper_get_positions():
        key = f"{p['exchange']}:{p['symbol']}:{p['timeframe']}"
        mtm[key] = _last_close(db, p["exchange"], p["symbol"], p["timeframe"]) or p["avg_price"]
    return paper_get_equity(mark_to_market=mtm)


@app.get("/trade/equity/history", tags=["Trade"])
def trade_equity_history(
    timeframe: str = "15m",
    days: int = 7,
    include_json: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    return _compute_equity_history(db, timeframe=timeframe, days=int(days), include_json=bool(include_json))


@app.get("/trade/orders", tags=["Trade"])
def trade_orders():
    return paper_get_orders()


# main.py
@app.post("/trade/paper/close", tags=["Trade"])
def trade_paper_close(req: PaperCloseRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("close")
    px = _last_close(db, req.exchange, req.symbol, req.timeframe)
    if px is None:
        err("trade.no_last_price", "нет последних цен в БД", 409)
    ts = _now_utc().replace(microsecond=0).isoformat()

    db_pos = (
        db.query(PaperPosition)
        .filter(PaperPosition.exchange == req.exchange, PaperPosition.symbol == req.symbol)
        .one_or_none()
    )
    if db_pos:
        q = float(db_pos.qty or 0.0)
        if q > 0.0:
            return ok(
                **_manual_sell_db(db, req.exchange, req.symbol, req.timeframe, q, px, ts, note="api /trade/paper/close")
            )
        if q < 0.0:
            return ok(
                **_manual_cover_db(
                    db, req.exchange, req.symbol, req.timeframe, abs(q), px, ts, note="api /trade/paper/close"
                )
            )

    # иначе пробуем JSON-портфель (скорее всего закрывает только лонг)
    return ok(**paper_close_pair(req.exchange, req.symbol, req.timeframe, px, ts))


# --- ручной бумажный BUY для теста ---
class PaperOpenRequest(BaseModel):
    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"


@app.post("/trade/paper/order", tags=["Trade"])
def trade_paper_order(req: PaperOpenRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("open")
    px = _last_close(db, req.exchange, req.symbol, req.timeframe)
    if px is None:
        return {"status": "error", "detail": "нет последней цены в БД"}
    ts = _now_utc().replace(microsecond=0).isoformat()
    res = paper_open_buy_auto(req.exchange, req.symbol, req.timeframe, px, ts)
    return res


@app.post("/trade/paper/reset", tags=["Trade"])
def trade_paper_reset(_=Depends(require_api_key)):
    _trade_guard_enforce("admin")
    from src.trade import DEFAULT_STATE, _save_state

    _save_state(DEFAULT_STATE.copy())
    return {"status": "ok"}


@app.post("/trade/paper/cash", tags=["Trade"])
def trade_paper_cash_set(amount: float, _=Depends(require_api_key)):
    _trade_guard_enforce("admin")
    from src.trade import _load_state, _save_state

    st = _load_state()
    st["cash"] = float(amount)
    _save_state(st)
    return {"status": "ok", "cash": st["cash"]}


# ------------------ автоматизация (планировщик) ------------------
scheduler = BackgroundScheduler(timezone="UTC")


# --- импорт/экспорт между JSON-портфелем и БД ----
@app.post("/trade/paper/import_json_to_db", tags=["Trade"])
def trade_import_json_to_db(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """
    Импортирует открытые позиции из JSON-портфеля (src.trade) в БД (PaperPosition).
    Если позиция уже есть в БД — перезаписывает qty/avg_price.
    """
    try:
        from src.trade import paper_get_positions  # type: ignore
    except Exception as e:
        return {"status": "error", "detail": f"import: cannot access JSON state: {e}"}

    positions = paper_get_positions()
    imported = 0
    for p in positions:
        try:
            ex = p.get("exchange")
            sym = p.get("symbol")
            qty = float(p.get("qty", 0.0))
            avg = float(p.get("avg_price", 0.0))
            if not ex or not sym or qty <= 0:
                continue
            row = (
                db.query(PaperPosition).filter(PaperPosition.exchange == ex, PaperPosition.symbol == sym).one_or_none()
            )
            if row is None:
                row = PaperPosition(exchange=ex, symbol=sym, qty=qty, avg_price=avg, realized_pnl=0.0)
                db.add(row)
            else:
                row.qty = qty
                row.avg_price = avg
            row.updated_at = _now_utc().replace(tzinfo=None)
            imported += 1
        except Exception:
            db.rollback()
            continue
    db.commit()
    return {"status": "ok", "imported_positions": imported}


@app.post("/trade/paper/export_db_to_json", tags=["Trade"])
def trade_export_db_to_json(_=Depends(require_api_key)):
    """
    Экспортирует открытые позиции из БД в JSON-портфель (src.trade).
    Перезаписывает 'positions' в artifacts/paper_state.json, cash оставляет как есть.
    """
    try:
        from src.trade import _load_state, _save_state  # type: ignore
    except Exception as e:
        return {"status": "error", "detail": f"export: cannot access JSON state: {e}"}

    st = _load_state()
    out = []
    with SessionLocal() as db:
        rows = db.query(PaperPosition).all()
        for r in rows:
            if float(r.qty or 0.0) <= 0.0:
                continue
            out.append(
                {
                    "exchange": r.exchange,
                    "symbol": r.symbol,
                    "timeframe": "15m",
                    "qty": float(r.qty or 0.0),
                    "avg_price": float(r.avg_price or 0.0),
                }
            )
    st["positions"] = out
    _save_state(st)
    return {"status": "ok", "exported_positions": len(out)}


def job_build_report():
    with SessionLocal() as db:
        try:
            pairs = [
                ("bybit", "BTC/USDT", "15m"),
                ("bybit", "ETH/USDT", "15m"),
            ]
            path = build_daily_report(db, pairs)
            print(f"[scheduler] report built: {path}")
        except Exception as e:
            print(f"[scheduler] report error: {e}")


def job_fetch_news():
    with SessionLocal() as db:
        try:
            added = fetch_and_store(db)
            print(f"[scheduler] news fetched: +{added}")
        except Exception as e:
            print(f"[scheduler] news fetch error: {e}")


def job_analyze_news():
    with SessionLocal() as db:
        try:
            processed = analyze_new_articles(db, limit=200)
            print(f"[scheduler] news analyzed: {processed}")
        except Exception as e:
            print(f"[scheduler] news analyze error: {e}")


def job_discover_watchlist():
    try:
        res = discover_pairs(
            min_volume_usd=2_000_000,
            top_n_per_exchange=25,
            quotes=("USDT",),
            timeframes=("15m",),
            limit=1000,
            exchanges=("bybit",),
        )
        print(f"[scheduler] discover_watchlist: +{len(res.get('added', []))} (watchlist={res.get('total_watchlist')})")
    except Exception as e:
        print(f"[scheduler] discover_watchlist error: {e}")


def job_fetch_prices():
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, lim in pairs:
            if ex != "bybit":
                continue
            try:
                added = fetch_and_store_prices(db, ex, sym, tf, lim)
                print(f"[scheduler] prices {ex} {sym} {tf}: +{added}")
            except Exception as e:
                print(f"[scheduler] prices error {ex} {sym} {tf}: {e}")


def job_train_models():
    policy = load_model_policy()
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, _ in pairs:
            try:
                hz = 6 if tf.endswith("h") else 12
                df, feature_cols = build_dataset(db, ex, sym, tf, hz)
                if len(df) < int(policy.get("min_train_rows", 200)):
                    print(f"[scheduler] skip train {ex} {sym} {tf}: not enough data ({len(df)})")
                    continue

                need, reason, meta = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=len(df))
                if not need:
                    print(f"[scheduler] fresh model {ex} {sym} {tf} ({reason}) — skip")
                    continue

                metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
                run = ModelRun(
                    exchange=ex,
                    symbol=sym,
                    timeframe=tf,
                    horizon_steps=hz,
                    n_train=metrics["n_train"],
                    n_test=metrics["n_test"],
                    accuracy=metrics.get("accuracy"),
                    roc_auc=metrics.get("roc_auc"),
                    threshold=metrics.get("threshold"),
                    total_return=metrics.get("total_return"),
                    sharpe_like=metrics.get("sharpe_like"),
                    model_path=model_path,
                    features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
                )
                db.add(run)
                db.commit()

                if not get_active_model_path(ex, sym, tf, hz):
                    set_active_model(ex, sym, tf, hz, model_path)

                manual_active = get_active_model_path(ex, sym, tf, hz)
                if not manual_active:
                    prev = (
                        db.query(ModelRun)
                        .filter(
                            ModelRun.exchange == ex,
                            ModelRun.symbol == sym,
                            ModelRun.timeframe == tf,
                            ModelRun.horizon_steps == hz,
                            ModelRun.id < run.id,
                        )
                        .order_by(ModelRun.id.desc())
                        .first()
                    )
                    new_auc = float(metrics.get("roc_auc") or 0.0)
                    old_auc = float(getattr(prev, "roc_auc", 0.0) or 0.0)
                    promote_thr = float(policy.get("promote_if_auc_gain", 0.005))

                    if prev and new_auc >= old_auc + promote_thr:
                        set_active_model(ex, sym, tf, hz, model_path)
                        try:
                            send_telegram(
                                "🏆 PROMOTE\n"
                                f"{ex.upper()} {sym} {tf} (hz={hz})\n"
                                f"AUC: {old_auc:.3f} → {new_auc:.3f}  (Δ≥{promote_thr:.3f})\n"
                                f"📦 {model_path}"
                            )
                        except Exception:
                            pass

                try:
                    _auc = metrics.get("roc_auc")
                    _acc = metrics.get("accuracy")
                    msg = (
                        f"🧠 TRAIN {ex} {sym} {tf} (hz={hz})\n"
                        f"Причина: {reason}\n"
                        f"AUC={(f'{_auc:.3f}' if _auc is not None else 'n/a')} • "
                        f"Acc={(f'{_acc:.3f}' if _acc is not None else 'n/a')}\n"
                        f"Thr={metrics.get('threshold'):.2f} • N={metrics.get('n_train')}+{metrics.get('n_test')}\n"
                        f"📦 {model_path}"
                    )
                    send_telegram(msg)
                except Exception:
                    pass

                print(f"[scheduler] trained {ex} {sym} {tf}: {metrics} (reason={reason})")
            except Exception as e:
                db.rollback()
                print(f"[scheduler] train error {ex} {sym} {tf}: {e}")


def _cooldown_passed(db: Session, ex: str, sym: str, tf: str, minutes: int) -> bool:
    last_buy = (
        db.query(SignalEvent)
        .filter(
            SignalEvent.exchange == ex,
            SignalEvent.symbol == sym,
            SignalEvent.timeframe == tf,
            SignalEvent.signal == "buy",
        )
        .order_by(SignalEvent.bar_dt.desc())
        .first()
    )
    if not last_buy:
        return True
    last_dt = last_buy.bar_dt
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=_tz.utc)
    return last_dt <= (_now_utc() - timedelta(minutes=int(minutes)))


def job_make_signals():
    with SessionLocal() as db:
        pairs = pairs_for_jobs()
        for ex, sym, tf, _ in pairs:
            try:
                horizon = 6 if tf.endswith("h") else 12
                df, _ = build_dataset(db, ex, sym, tf, horizon)

                if df.empty:
                    try:
                        added = fetch_and_store_prices(db, ex, sym, tf, 500)
                        print(f"[scheduler] warmed prices {ex} {sym} {tf}: +{added}")
                        df, _ = build_dataset(db, ex, sym, tf, horizon)
                    except Exception as e:
                        print(f"[scheduler] warmup error {ex} {sym} {tf}: {e}")

                if df.empty:
                    print(f"[scheduler] skip {ex} {sym} {tf}: no data")
                    continue

                row = df.iloc[-1]
                bar_dt = row.name.to_pydatetime()
                close = float(row["close"])

                model, feature_cols, threshold, model_path = load_model_for(db, ex, sym, tf, horizon)
                X = row[feature_cols].values.reshape(1, -1)
                proba = float(model.predict_proba(X)[0, 1])
                base_signal = "buy" if proba > threshold else "flat"
                delta = proba - threshold

                policy = load_policy()
                min_gap = float(policy.get("min_prob_gap", 0.02))
                cool_minutes = int(policy.get("cooldown_minutes", 90))

                notify_cfg = policy.get("notify") or {}
                notify_on_buy = bool(notify_cfg.get("on_buy", True))
                notify_radar = bool(notify_cfg.get("radar", False))
                radar_gap = float(notify_cfg.get("radar_gap", 0.01))

                auto_cfg = policy.get("auto") or {}
                auto_trade_on_buy = bool(auto_cfg.get("trade_on_buy", False))
                auto_close_on_strong_flat = bool(auto_cfg.get("close_on_strong_flat", False))

                last_evt = (
                    db.query(SignalEvent)
                    .filter(SignalEvent.exchange == ex, SignalEvent.symbol == sym, SignalEvent.timeframe == tf)
                    .order_by(SignalEvent.bar_dt.desc())
                    .first()
                )
                last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore

                allow, reasons, metrics = evaluate_filters(row, df, policy, tf, last_bar_ts)
                allow_vol, r2, m2 = _volatility_guard(row, df, tf, policy)
                allow = allow and allow_vol
                reasons += r2
                metrics.update(m2)

                if base_signal == "buy" and delta < min_gap:
                    reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
                    allow = False

                final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

                evt = SignalEvent(
                    exchange=ex,
                    symbol=sym,
                    timeframe=tf,
                    horizon_steps=horizon,
                    bar_dt=bar_dt,
                    close=close,
                    prob_up=proba,
                    threshold=threshold,
                    signal=final_signal,
                    model_path=model_path,
                    note=json.dumps(
                        {
                            "base_signal": base_signal,
                            "prob": proba,
                            "threshold": threshold,
                            "prob_gap": delta,
                            "policy": policy,
                            "metrics": metrics,
                            "reasons": reasons,
                        },
                        ensure_ascii=False,
                    ),
                )

                try:
                    db.add(evt)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    print(f"[scheduler] duplicate signal {ex} {sym} {tf} @ {bar_dt} — skipped")
                    continue

                should_notify = (final_signal == "buy" and notify_on_buy) or (notify_radar and abs(delta) <= radar_gap)
                if should_notify:
                    try:
                        maybe_send_signal_notification(
                            final_signal,
                            proba,
                            threshold,
                            delta,
                            reasons,
                            model_path,
                            ex,
                            sym,
                            tf,
                            bar_dt,
                            close,
                            source="scheduler",
                        )
                    except Exception:
                        pass

                if final_signal == "buy" and auto_trade_on_buy:
                    if _cooldown_passed(db, ex, sym, tf, cool_minutes):
                        # считаем open-позиции и там и там
                        db_open = sum(1 for p in db.query(PaperPosition).all() if float(p.qty or 0) > 0)
                        json_open = 0
                        try:
                            from src.trade import paper_get_positions

                            json_open = sum(1 for p in paper_get_positions() if float(p.get("qty", 0)) > 0)
                        except Exception:
                            pass
                        open_total = db_open + json_open

                        max_open = int((load_policy() or {}).get("max_open_positions", 0) or 0)
                        if max_open > 0 and open_total >= max_open:
                            # логируем и пропускаем авто-ордер
                            print(
                                f"[scheduler] skip auto-buy {ex} {sym} {tf}: max_open_positions reached ({open_total}/{max_open})"
                            )
                            continue
                        paper_open_buy_auto(
                            ex, sym, tf, close, bar_dt.isoformat(), vol_state=metrics.get("vol_state"), last_price=close
                        )
                    else:
                        reasons.append(f"cooldown_skip({cool_minutes}m)")

                if final_signal == "flat" and auto_close_on_strong_flat:
                    if delta <= -abs(min_gap):
                        from src.trade import paper_has_open_position, paper_close_with_price

                        if paper_has_open_position(ex, sym, tf):
                            res = paper_close_with_price(ex, sym, tf, close, bar_dt.isoformat())
                            try:
                                pnl_str = ""
                                if isinstance(res, dict) and "order" in res:
                                    od = res["order"]
                                    pnl = od.get("pnl", res.get("pnl"))
                                    if pnl is not None:
                                        pnl_str = f"\nPnL = {pnl:.2f} USDT"
                                send_telegram(
                                    f"💼 CLOSE {ex} {sym} {tf}\n"
                                    f"⏱️ {bar_dt}  •  Ⓜ️ {close}\n"
                                    f"Причина: уверенный FLAT (gap {delta:.3f}){pnl_str}"
                                )
                            except Exception:
                                pass

                print(f"[scheduler] signal {ex} {sym} {tf} @ {bar_dt}: {final_signal} (p={proba:.3f}, gap={delta:.3f})")
            except Exception as e:
                db.rollback()
                print(f"[scheduler] signal error {ex} {sym} {tf}: {e}")


def job_resolve_outcomes():
    with SessionLocal() as db:
        since = _now_utc() - timedelta(days=7)
        candidates = (
            db.query(SignalEvent).filter(SignalEvent.created_at >= since).order_by(SignalEvent.bar_dt.asc()).all()
        )
        done = 0
        for evt in candidates:
            try:
                if _try_resolve_outcome_for_event(db, evt):
                    done += 1
            except Exception as e:
                print(f"[scheduler] outcome error {evt.exchange} {evt.symbol} {evt.timeframe} @ {evt.bar_dt}: {e}")
        if done:
            print(f"[scheduler] outcomes resolved: {done}")


def _monitor_cfg(policy: dict) -> dict:
    d = (policy or {}).get("monitor") or {}
    tf = (d.get("timeframe") or "15m").lower()
    return {
        "enabled": bool(d.get("enabled", True)),
        "flat_after": float(d.get("flat_after", -0.01)),
        "partial_at": float(d.get("partial_at", 0.03)),
        "partial_size": float(d.get("partial_size", 0.30)),
        "timeframe": tf,
        "cooldown_minutes": int(d.get("cooldown_minutes", _tf_minutes(tf))),
        "min_ret_change": float(d.get("min_ret_change", 0.005)),
        "types": list(d.get("types", ["partial", "flat"])),
        "only_symbols": list(d.get("only_symbols", [])),
        "exclude_symbols": list(d.get("exclude_symbols", [])),
        # новое:
        "auto_execute": bool(d.get("auto_execute", False)),
        "auto_note": str(d.get("auto_note", "monitor auto-action")),
        "dry_run": bool(d.get("dry_run", False)),
    }


def job_monitor_positions():
    policy = load_policy()
    cfg = _monitor_cfg(policy)
    if not cfg["enabled"]:
        return

    tf = cfg["timeframe"]
    cool = int(cfg["cooldown_minutes"])
    min_delta = float(cfg["min_ret_change"])

    st = _mon_load_state()
    now = _now_utc()

    with SessionLocal() as db:
        rows = db.query(PaperPosition).all()
        for pos in rows:
            try:
                if not pos or float(pos.qty or 0.0) <= 0:
                    continue
                ex, sym = pos.exchange, pos.symbol
                # фильтр по спискам
                only = cfg.get("only_symbols") or []
                excl = cfg.get("exclude_symbols") or []
                if only and sym not in only:
                    continue
                if excl and sym in excl:
                    continue
                avg = float(pos.avg_price or 0.0)
                last = _last_close(db, ex, sym, tf) or avg
                ret = (last / avg - 1.0) if avg > 0 else 0.0
                pnl_abs = (last - avg) * float(pos.qty or 0.0)
                pnl_sign = "+" if pnl_abs > 0 else ""

                # вычисляем тип алерта сначала...
                alert_type = None
                # фильтр по типу алерта
                if ret <= cfg["flat_after"]:
                    alert_type = "flat"
                    msg = (
                        f"⚠️ ПОЗИЦИЯ В МИНУСЕ — ЛУЧШЕ ЗАКРЫТЬ\n"
                        f"{ex.upper()} {sym} {tf}\n"
                        f"qty={pos.qty:.6f} • avg={avg:.6f} • last={last:.6f}\n"
                        f"PnL={ret:.2%} ({pnl_sign}{pnl_abs:.2f} USDT)\n"
                        f"/close {ex} {sym} @ {last:.2f} tf={tf}"
                    )
                elif ret >= cfg["partial_at"]:
                    alert_type = "partial"
                    part = cfg["partial_size"]
                    qty_part = float(pos.qty or 0.0) * float(part)
                    msg = (
                        f"✅ СИЛЬНЫЙ ПРОФИТ — ЗАФИКСИРОВАТЬ ЧАСТЬ ({int(part * 100)}%)\n"
                        f"{ex.upper()} {sym} {tf}\n"
                        f"qty={pos.qty:.6f} • avg={avg:.6f} • last={last:.6f}\n"
                        f"PnL={ret:.2%} ({pnl_sign}{pnl_abs:.2f} USDT)\n"
                        f"/sell {ex} {sym} {qty_part:.6f} @ {last:.2f} tf={tf}"
                    )
                else:
                    # ни один порог не сработал — пропускаем
                    continue
                # ...а уже затем проверяем, включён ли он политикой
                if alert_type not in (cfg.get("types") or ["partial", "flat"]):
                    continue

                key = f"{ex}:{sym}:{tf}:{alert_type}"
                rec = st.get(key) or {}
                last_ts = pd.to_datetime(rec.get("ts")) if rec.get("ts") else None
                last_ret = float(rec.get("ret")) if rec.get("ret") is not None else None

                ok_cooldown = True if not last_ts else (now - last_ts) >= timedelta(minutes=cool)
                ok_change = True if last_ret is None else abs(ret - last_ret) >= min_delta

                # --- авто-действия по порогам (лонг-позиции в БД) ---
                if cfg.get("auto_execute") and not cfg.get("dry_run"):
                    ts_iso = now.replace(microsecond=0).isoformat()
                    try:
                        if alert_type == "partial" and float(pos.qty or 0.0) > 0:
                            qty_part = float(pos.qty or 0.0) * float(cfg["partial_size"])
                            _manual_sell_db(db, ex, sym, tf, qty_part, float(last), ts_iso, note=cfg.get("auto_note"))
                        elif alert_type == "flat" and float(pos.qty or 0.0) > 0:
                            _manual_sell_db(
                                db, ex, sym, tf, float(pos.qty or 0.0), float(last), ts_iso, note=cfg.get("auto_note")
                            )
                    except Exception as e:
                        print(f"[monitor:auto] error {ex} {sym}: {e}")

                if ok_cooldown or ok_change:
                    try:
                        send_telegram(msg)
                    except Exception:
                        pass
                    st[key] = {"ts": now.isoformat(), "ret": ret}
            except Exception as e:
                print(f"[monitor] error {getattr(pos, 'exchange', '?')} {getattr(pos,'symbol','?')}: {e}")

    _mon_save_state(st)


def job_bootstrap():
    print("[bootstrap] start")
    try:
        try:
            res = discover_pairs(
                min_volume_usd=2_000_000,
                top_n_per_exchange=25,
                quotes=("USDT",),
                timeframes=("15m",),
                limit=1000,
                exchanges=("bybit",),
            )
            print(f"[bootstrap] discover_pairs: +{len(res.get('added', []))} (watchlist={res.get('total_watchlist')})")
        except Exception as e:
            print(f"[bootstrap] discover_pairs error: {e}")

        try:
            job_fetch_prices()
        except Exception as e:
            print(f"[bootstrap] fetch_prices error: {e}")

        try:
            with SessionLocal() as db:
                _train_missing_impl(db)
            print("[bootstrap] train_missing done")
        except Exception as e:
            print(f"[bootstrap] train_missing error: {e}")
        try:
            job_make_signals()
        except Exception as e:
            print(f"[bootstrap] make_signals error: {e}")
        print("[bootstrap] complete")
    except Exception as e:
        print(f"[bootstrap] fatal: {e}")


def job_self_audit_and_notify():
    with SessionLocal() as db:
        since = _now_utc() - timedelta(days=1)
        rows = (
            db.query(SignalOutcome, SignalEvent)
            .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
            .filter(SignalOutcome.resolved_at >= since)
            .order_by(SignalOutcome.id.desc())
            .all()
        )
        n = len(rows)
        if n == 0:
            return
        wins = sum(1 for o, _e in rows if (o.ret_h or 0.0) > 0.0)
        winrate = wins / n
        avg_ret = sum((o.ret_h or 0.0) for o, _e in rows) / n
        avg_mdd = sum((o.max_drawdown or 0.0) for o, _e in rows) / n
        best = max(rows, key=lambda t: (t[0].ret_h or -1e9))
        worst = min(rows, key=lambda t: (t[0].ret_h or 1e9))
        best_s, best_e = best
        worst_s, worst_e = worst

        hints = []
        if n >= 10 and winrate < 0.45 and avg_mdd < -0.02:
            hints.append("возможен рост порога min_prob_gap (например, 0.03)")
        if n >= 10 and avg_ret > 0.01 and winrate > 0.55:
            hints.append("можно чуть поднять buy_fraction для нормальной волатильности")

        msg = (
            "🧾 SELF-AUDIT (24h)\n"
            f"Сигналов закрыто: {n}\n"
            f"Win-rate: {winrate:.0%}\n"
            f"Avg ret@h: {avg_ret:.2%} • Avg MDD: {avg_mdd:.2%}\n"
            f"Best: {best_e.exchange} {best_e.symbol} {best_e.timeframe} → {best_s.ret_h:+.2%}\n"
            f"Worst: {worst_e.exchange} {worst_e.symbol} {worst_e.timeframe} → {worst_s.ret_h:+.2%}\n"
        )
        if hints:
            msg += "Советы: " + "; ".join(hints)

        try:
            send_telegram(msg)
        except Exception:
            pass


@app.get("/ui/summary", tags=["UI"])
def ui_summary(db: Session = Depends(get_db), _=Depends(require_api_key)):
    try:
        merged = {}
        # БД
        db_pos = db.query(PaperPosition).all()
        for p in db_pos:
            last = _last_close(db, p.exchange, p.symbol, "15m") or float(p.avg_price or 0.0)
            mv = float(p.qty or 0.0) * last
            merged[(p.exchange, p.symbol, "15m")] = {
                "exchange": p.exchange,
                "symbol": p.symbol,
                "timeframe": "15m",
                "qty": float(p.qty or 0.0),
                "avg_price": float(p.avg_price or 0.0),
                "last_price": last,
                "market_value": mv,
                "source": "db",
            }
        # JSON
        for p in paper_get_positions():
            key = (p["exchange"], p["symbol"], p.get("timeframe", "15m"))
            if key in merged:
                continue
            last = _last_close(db, p["exchange"], p["symbol"], p.get("timeframe", "15m")) or float(
                p.get("avg_price", 0.0)
            )
            mv = float(p.get("qty", 0.0)) * last
            merged[key] = {
                "exchange": p["exchange"],
                "symbol": p["symbol"],
                "timeframe": p.get("timeframe", "15m"),
                "qty": float(p.get("qty", 0.0)),
                "avg_price": float(p.get("avg_price", 0.0)),
                "last_price": last,
                "market_value": mv,
                "source": "json",
            }
        positions = list(merged.values())
    except Exception:
        positions = []

    orders_json = paper_get_orders()
    orders_db = []
    try:
        rows = db.query(PaperOrder).order_by(PaperOrder.id.desc()).limit(100).all()
        for r in rows:
            orders_db.append(
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "exchange": r.exchange,
                    "symbol": r.symbol,
                    "side": r.side,
                    "qty": float(r.qty),
                    "price": float(r.price),
                    "fee": float(r.fee),
                    "status": r.status,
                    "note": r.note,
                }
            )
    except Exception:
        pass

    sig = signals_recent(limit=30, db=db)
    try:
        cfg = _nr_cfg(load_policy())
        out = _news_radar_compute(
            db,
            cfg["window_minutes"],
            cfg["lookback_windows"],
            cfg["symbols"] or _wl_keywords_default(),
            cfg["min_new"],
            cfg["min_ratio_vs_prev"],
            cfg["min_unique_sources"],
            cfg["min_sentiment_abs"],
        )
        radar_alerts = out["alerts"][:5]
    except Exception:
        radar_alerts = []
    return {
        "positions": positions,
        "orders_json": orders_json,
        "orders_db": orders_db,
        "signals": sig,
        "radar_alerts": radar_alerts,
    }


@app.get("/ui/summary_html", response_class=HTMLResponse, tags=["UI"])
def ui_summary_html():
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MyAssistant — Summary</title>
  <style>
    body { font: 14px/1.4 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 24px; color:#111;}
    h1 { font-size: 20px; margin: 0 0 16px;}
    .grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
    @media (min-width: 1100px) { .grid { grid-template-columns: 1fr 1fr; } }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .pos-green { color: #0a7f2e; font-weight: 600; }
    .pos-red { color: #b91c1c; font-weight: 600; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .pill { display:inline-block; padding:2px 6px; border-radius:999px; background:#eef2ff; }
    .small { font-size: 12px; color:#4b5563; }
  </style>
</head>
<body>
  <h1>📊 MyAssistant — Summary</h1>
  <div id="time" class="small"></div>
  <div class="grid">
    <section>
      <h2>Открытые позиции</h2>
      <div id="positions">Загрузка…</div>
    </section>
    <section>
      <h2>Свежие сигналы</h2>
      <div id="signals">Загрузка…</div>
    </section>
    <section>
      <h2>Ордеры (DB)</h2>
      <div id="orders_db">Загрузка…</div>
    </section>
    <section>
      <h2>News Radar</h2>
      <div id="radar">Загрузка…</div>
    </section>
  </div>

<script>
let CAPS = { can_short:true, can_cover:true, buy_usd:100 };
const ALLOWED_EXCHANGES = ['bybit']; // показывать только эти биржи (lowercase)

async function loadCaps() {
  try {
    const r = await fetch('/meta/capabilities', { headers: { 'X-API-Key': localStorage.getItem('api_key') || '' }});
    if (r.ok) {
      CAPS = await r.json();
    }
  } catch (_) {}
}

async function load() {
  const r = await fetch('/ui/summary', { headers: { 'X-API-Key': localStorage.getItem('api_key') || '' }});
  if (!r.ok) {
    document.body.innerHTML = '<p style="color:#b91c1c">Ошибка загрузки /ui/summary ('+r.status+')</p>';
    return;
  }
  const j = await r.json();
  document.getElementById('time').textContent = 'Обновлено: ' + new Date().toLocaleString();

  // POSITIONS
const pos = (j.positions || [])
  .filter(p =>
    ALLOWED_EXCHANGES.includes(String(p.exchange).toLowerCase()) &&
    Number(p.qty) !== 0
  );
document.getElementById('positions').innerHTML = table(
  ['Биржа','Пара','TF','Qty','Avg','Last','MV','Actions'],
  pos.map(p => [
    p.exchange.toUpperCase(),
    p.symbol,
    p.timeframe,
    fmt(p.qty, 6),
    fmt(p.avg_price, 2),
    fmt(p.last_price, 2),
    fmt(p.market_value, 2),
    actionBtns(p.exchange, p.symbol, p.timeframe, Number(p.qty), Number(p.last_price))
  ])
);

  // SIGNALS
const sig = (j.signals || []);
const sigF = sig.filter(s => ALLOWED_EXCHANGES.includes(String(s.exchange || '').toLowerCase()));
document.getElementById('signals').innerHTML = table(
  ['DT','Биржа','Пара','TF','Close','Prob','Thr','Signal'],
  sigF.map(s => [
    new Date(s.bar_dt).toLocaleString(),
    (s.exchange||'').toUpperCase(), s.symbol, s.timeframe,
    fmt(s.close,2), fmt(s.prob_up,3), fmt(s.threshold,3), badge(s.signal||'')
  ])
);

// ORDERS (DB)
const od = (j.orders_db || []);
const odF = od.filter(o => ALLOWED_EXCHANGES.includes(String(o.exchange || '').toLowerCase()));
document.getElementById('orders_db').innerHTML = table(
  ['DT','Биржа','Пара','Side','Qty','Price','Fee','Note'],
  odF.map(o => [
    new Date(o.created_at).toLocaleString(),
    (o.exchange||'').toUpperCase(), o.symbol, (o.side||'').toUpperCase(),
    fmt(o.qty,6), fmt(o.price,2), fmt(o.fee,2), o.note||''
  ])
);

  // RADAR (синхронизация ключей с backend)
  const rd = j.radar_alerts || [];
  document.getElementById('radar').innerHTML = table(
    ['Symbol','Now','PrevAvg','Ratio','Sources','Примеры'],
    rd.map(r => [
        r.symbol,
        r.n_current,
        (r.n_prev_avg || 0).toFixed(2),
        (r.ratio || 0).toFixed(1),
        r.unique_sources,                // это число источников
        (r.examples || []).join(' • ')   // примеры заголовков
    ])
);
}

function fmt(x, d=2) { if (x===null || x===undefined || isNaN(x)) return ''; return Number(x).toFixed(d); }
function badge(s) { const c = s==='buy' ? '#065f46' : '#374151'; const bg = s==='buy' ? '#ecfdf5' : '#f3f4f6'; return `<span class="pill" style="background:${bg};color:${c}">${s}</span>`; }
function table(headers, rows) {
  let h = '<table><thead><tr>' + headers.map(x=>'<th>'+x+'</th>').join('') + '</tr></thead><tbody>';
  if (!rows.length) h += '<tr><td colspan="'+headers.length+'"><span class="small">нет данных</span></td></tr>';
  else h += rows.map(r => '<tr>' + r.map(c => '<td>'+c+'</td>').join('') + '</tr>').join('');
  return h + '</tbody></table>';
}

function actionBtns(ex, sym, tf, qty, last) {
  const amountBuy = Number((CAPS && CAPS.buy_usd) ? CAPS.buy_usd : 100);
  const buyQty = last > 0 ? (amountBuy / last) : 0;

  if (qty > 0) {
    // ЛОНГ: частичная фиксация / закрыть / докупить
    return `
      <button onclick="sellPart('${ex}','${sym}','${tf}',0.25)">Sell 25%</button>
      <button onclick="sellPart('${ex}','${sym}','${tf}',0.50)">Sell 50%</button>
      <button onclick="closeAll('${ex}','${sym}','${tf}')">Close</button>
      <button onclick="buyAmount('${ex}','${sym}','${tf}',${buyQty.toFixed(8)})">Buy +$${amountBuy}</button>
    `;
  } else if (qty < 0) {
    // ШОРТ: кнопки покрытия только если backend это умеет
    if (!(CAPS && CAPS.can_cover)) return '<span class="small">short: no cover</span>';
    const absQty = Math.abs(qty);
    return `
      <button onclick="coverPart('${ex}','${sym}','${tf}',${(absQty*0.25).toFixed(8)})">Cover 25%</button>
      <button onclick="coverPart('${ex}','${sym}','${tf}',${(absQty*0.50).toFixed(8)})">Cover 50%</button>
      <button onclick="coverPart('${ex}','${sym}','${tf}',${absQty.toFixed(8)})">Cover ALL</button>
    `;
  } else {
    // Нет позиции: показать SHORT только если можно
    const shortQty = last > 0 ? (amountBuy / last) : 0;
    const shortBtn = (CAPS && CAPS.can_short)
      ? `<button onclick="shortAmount('${ex}','${sym}','${tf}',${shortQty.toFixed(8)})">Short -$${amountBuy}</button>`
      : '';
    return `
      <button onclick="buyAmount('${ex}','${sym}','${tf}',${buyQty.toFixed(8)})">Buy +$${amountBuy}</button>
      ${shortBtn}
    `;
  }
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': localStorage.getItem('api_key') || ''
    },
    body: JSON.stringify(body || {})
  });
  const j = await r.json().catch(()=>({}));
  if (!r.ok || j.status === 'error') {
    // дружелюбная ошибка для trade.locked
    const detail = (j && j.detail) ? JSON.stringify(j.detail) : r.status;
    alert('Ошибка: ' + detail);
    throw new Error(detail);
  }
  return j;
}

async function shortAmount(ex, sym, tf, qty) {
  await apiPost('/trade/manual/short', { exchange: ex, symbol: sym, timeframe: tf, qty: Number(qty) });
  await load();
}

async function buyAmount(ex, sym, tf, qty) {
  await apiPost('/trade/manual/buy', { exchange: ex, symbol: sym, timeframe: tf, qty: Number(qty) });
  await load();
}

async function sellPart(ex, sym, tf, part) {
  const r = await fetch('/ui/summary', { headers: { 'X-API-Key': localStorage.getItem('api_key') || '' }});
  const j = await r.json();
  const p = (j.positions || []).find(x => x.exchange===ex && x.symbol===sym && x.timeframe===tf);
  if (!p || p.qty <= 0) return alert('Нет лонга для частичной продажи');

  const qty = Number(p.qty) * Number(part);
  // Через /bot/command — оставляем как универсальный путь (DB + JSON портфель)
  await apiPost('/bot/command', { text: `/sell ${ex} ${sym} ${qty.toFixed(8)} tf=${tf}` });
  await load();
}

async function closeAll(ex, sym, tf) {
  await apiPost('/bot/command', { text: `/close ${ex} ${sym} tf=${tf}` });
  await load();
}

async function coverPart(ex, sym, tf, qty) {
  await apiPost('/trade/manual/cover', { exchange: ex, symbol: sym, timeframe: tf, qty: Number(qty) });
  await load();
}

// простенький prompt для api_key
if (!localStorage.getItem('api_key')) {
  const k = prompt('Введите X-API-Key (будет сохранён локально в браузере):') || '';
  localStorage.setItem('api_key', k);
}

// сначала поднимем капабилити, затем загрузим данные
loadCaps().then(load);
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/ui/equity_html", response_class=HTMLResponse, tags=["UI"])
def ui_equity_html():
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MyAssistant — Equity</title>
  <style>
    body { font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin:24px; color:#111; }
    h1 { margin:0 0 12px; font-size:20px; }
    .row { display:flex; gap:16px; align-items:center; flex-wrap:wrap; margin-bottom:12px;}
    label { color:#374151; }
    input, select { padding:6px 8px; border:1px solid #e5e7eb; border-radius:8px; }
    .small { color:#6b7280; font-size:12px; }
    #chart { width:100%; height:380px; border:1px solid #e5e7eb; border-radius:12px; }
    .pill { display:inline-block; padding:2px 8px; border-radius:999px; background:#f3f4f6; margin-right:8px;}
  </style>
</head>
<body>
  <h1>📈 Equity / PnL</h1>
  <div class="row">
    <label>TF:
      <select id="tf">
        <option>15m</option>
        <option>1h</option>
        <option>4h</option>
        <option>1d</option>
      </select>
    </label>
    <label>Days:
      <input id="days" type="number" min="1" max="365" value="30">
    </label>
    <label><input id="incjson" type="checkbox"> include JSON orders (если не импортировано в DB)</label>
    <button id="go">Update</button>
    <span id="meta" class="small"></span>
  </div>

  <div id="stats" class="row"></div>
  <canvas id="chart"></canvas>

<script>
const H = 380;

function fmtPct(x){ return (x*100).toFixed(2) + '%'; }
function fmtUsd(x){ return (x>=0?'+':'') + x.toFixed(2) + ' USDT'; }

function drawChart(points) {
  const c = document.getElementById('chart');
  const pr = window.devicePixelRatio || 1;
  const W = c.clientWidth, Hh = c.clientHeight;
  c.width = W * pr; c.height = Hh * pr;
  const g = c.getContext('2d');
  g.scale(pr, pr);
  g.clearRect(0,0,W,Hh);
  if (!points.length) return;

  const xs = points.map(p => new Date(p.ts).getTime());
  const ys = points.map(p => p.equity);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 16;
  function X(i){ return pad + (W-2*pad) * (xs[i]-xs[0]) / (xs[xs.length-1]-xs[0] || 1); }
  function Y(v){ return (Hh-pad) - (Hh-2*pad) * ((v - minY) / ((maxY-minY)||1)); }

  // grid
  g.strokeStyle = '#e5e7eb'; g.lineWidth = 1;
  for (let k=0;k<5;k++){
    const y = pad + (Hh-2*pad) * k/4;
    g.beginPath(); g.moveTo(pad,y); g.lineTo(W-pad,y); g.stroke();
  }

  // line
  g.strokeStyle = '#111827'; g.lineWidth = 2; g.beginPath();
  g.moveTo(X(0), Y(ys[0]));
  for (let i=1;i<ys.length;i++) g.lineTo(X(i), Y(ys[i]));
  g.stroke();

  // last label
  g.fillStyle = '#111827';
  g.fillText(ys[ys.length-1].toFixed(2), W - pad - 60, pad + 12);
}

async function load(){
  const tf = document.getElementById('tf').value;
  const days = parseInt(document.getElementById('days').value || '30', 10);
  const inc = document.getElementById('incjson').checked ? 'true' : 'false';
  const r = await fetch(`/trade/equity/history?timeframe=${encodeURIComponent(tf)}&days=${days}&include_json=${inc}`, {
    headers: { 'X-API-Key': localStorage.getItem('api_key') || '' }
  });
  const j = await r.json();
  if (j.status !== 'ok') { alert('error'); return; }

  document.getElementById('meta').textContent =
  `timeframe=${j.timeframe}, ${j.start} → ${j.end} | cash=${j.cash_source} | base=${(j.equity_base||0).toFixed(2)}`;
  drawChart(j.equity || []);

  const s = j.stats || {};
  const el = document.getElementById('stats');
  el.innerHTML = `
    <span class="pill">PnL: ${fmtUsd(s.pnl_abs||0)} (${fmtPct(s.pnl_pct||0)})</span>
    <span class="pill">Max DD: ${fmtPct(s.max_drawdown||0)}</span>
    ${j.csv_url ? `<a class="pill" href="${j.csv_url}" target="_blank">CSV</a>` : ''}
  `;
}

if (!localStorage.getItem('api_key')) {
  const k = prompt('Введите X-API-Key (будет сохранён локально в браузере):') || '';
  localStorage.setItem('api_key', k);
}
document.getElementById('go').onclick = load;
window.addEventListener('resize', load);
load();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/journal/export", tags=["Journal"])
def journal_export(db: Session = Depends(get_db), _=Depends(require_api_key)):
    rows = []

    sigs = db.query(SignalEvent).order_by(SignalEvent.bar_dt.asc(), SignalEvent.id.asc()).all()
    for s in sigs:
        try:
            note = json.loads(s.note or "{}")
        except Exception:
            note = {}
        rows.append(
            {
                "type": "signal",
                "dt": s.bar_dt.isoformat() if s.bar_dt else None,
                "exchange": s.exchange,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "prob_up": s.prob_up,
                "threshold": s.threshold,
                "prob_gap": note.get("prob_gap"),
                "signal": s.signal,
                "reasons": ",".join(note.get("reasons") or []),
                "model_path": s.model_path,
            }
        )

    try:
        db_orders = db.query(PaperOrder).order_by(PaperOrder.id.asc()).all()
    except Exception:
        db_orders = []
    for o in db_orders:
        rows.append(
            {
                "type": "order_db",
                "dt": (o.created_at.isoformat() if o.created_at else None),
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": None,
                "side": o.side,
                "qty": float(o.qty or 0.0),
                "price": float(o.price or 0.0),
                "fee": float(o.fee or 0.0),
                "status": o.status,
                "note": o.note,
            }
        )

    try:
        for j in paper_get_orders():
            rows.append(
                {
                    "type": "order_json",
                    "dt": j.get("ts"),
                    "exchange": j.get("exchange"),
                    "symbol": j.get("symbol"),
                    "timeframe": j.get("timeframe"),
                    "side": j.get("side"),
                    "qty": float(j.get("qty", 0.0)),
                    "price": float(j.get("price", 0.0)),
                    "fee": None,
                    "status": "filled",
                    "note": None,
                    "pnl": j.get("pnl"),
                }
            )
    except Exception:
        pass

    outs = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.asc())
        .all()
    )
    for o, e in outs:
        rows.append(
            {
                "type": "outcome",
                "dt": (o.resolved_at.isoformat() if o.resolved_at else None),
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "max_drawdown": o.max_drawdown,
                "signal_dt": (e.bar_dt.isoformat() if e and e.bar_dt else None),
                "signal_id": e.id if e else None,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["dt"], kind="stable", na_position="last")
    Path("artifacts").mkdir(exist_ok=True)
    out_path = Path("artifacts") / "journal.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return {"status": "ok", "rows": int(len(df)), "path": str(out_path.resolve())}


@app.get("/journal/export_pretty", tags=["Journal"])
def journal_export_pretty(db: Session = Depends(get_db), _=Depends(require_api_key)):
    signals = db.query(SignalEvent).order_by(SignalEvent.bar_dt.asc(), SignalEvent.id.asc()).all()
    rows_sig = []
    for s in signals:
        try:
            note = json.loads(s.note or "{}")
        except Exception:
            note = {}
        rows_sig.append(
            {
                "dt": s.bar_dt,
                "exchange": s.exchange,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "prob_up": s.prob_up,
                "threshold": s.threshold,
                "prob_gap": note.get("prob_gap"),
                "signal": s.signal,
                "reasons": "; ".join(note.get("reasons") or []),
                "model_path": s.model_path,
            }
        )
    df_sig = pd.DataFrame(rows_sig)

    try:
        db_orders = db.query(PaperOrder).order_by(PaperOrder.id.asc()).all()
    except Exception:
        db_orders = []
    df_od = pd.DataFrame(
        [
            {
                "dt": o.created_at,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "side": o.side,
                "qty": float(o.qty or 0.0),
                "price": float(o.price or 0.0),
                "fee": float(o.fee or 0.0),
                "status": o.status,
                "note": o.note,
            }
            for o in db_orders
        ]
    )

    j_orders = []
    try:
        for j in paper_get_orders():
            j_orders.append(
                {
                    "dt": j.get("ts"),
                    "exchange": j.get("exchange"),
                    "symbol": j.get("symbol"),
                    "timeframe": j.get("timeframe"),
                    "side": j.get("side"),
                    "qty": float(j.get("qty", 0.0)),
                    "price": float(j.get("price", 0.0)),
                    "pnl": j.get("pnl"),
                }
            )
    except Exception:
        pass
    df_oj = pd.DataFrame(j_orders)

    outs = (
        db.query(SignalOutcome, SignalEvent)
        .join(SignalEvent, SignalEvent.id == SignalOutcome.signal_event_id)
        .order_by(SignalOutcome.id.asc())
        .all()
    )
    rows_out = []
    for o, e in outs:
        rows_out.append(
            {
                "resolved_at": o.resolved_at,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "timeframe": o.timeframe,
                "horizon": o.horizon_steps,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "max_drawdown": o.max_drawdown,
                "signal_dt": (e.bar_dt if e else None),
                "signal_id": (e.id if e else None),
            }
        )
    df_out = pd.DataFrame(rows_out)

    Path("artifacts").mkdir(exist_ok=True)
    xlsx_path = Path("artifacts") / "journal.xlsx"

    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm") as w:

        def _write(df, name):
            if df is None or df.empty:
                pd.DataFrame({"info": ["no data"]}).to_excel(w, index=False, sheet_name=name)
                return
            df.to_excel(w, index=False, sheet_name=name)
            ws = w.sheets[name]
            ws.freeze_panes(1, 0)
            for i, col in enumerate(df.columns):
                width = max(12, min(48, int(df[col].astype(str).str.len().quantile(0.95)) + 2))
                ws.set_column(i, i, width)

        _write(df_sig, "signals")
        _write(df_od, "orders_db")
        _write(df_oj, "orders_json")
        _write(df_out, "outcomes")

    return {"status": "ok", "path": str(xlsx_path.resolve())}


@app.post("/backup/snapshot", tags=["Backup"])
def backup_snapshot(_=Depends(require_api_key)):
    ts = _now_utc().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("artifacts") / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_zip = out_dir / f"snapshot_{ts}.zip"

    include_files = []
    for name in ["README.md", "JOURNAL.md"]:
        p = Path(name)
        if p.exists():
            include_files.append(p)

    for p in [
        Path("artifacts") / "journal.csv",
        Path("artifacts") / "journal.xlsx",
        Path("artifacts") / "paper_state.json",
        Path("artifacts") / "reports" / "latest.html",
    ]:
        if p.exists():
            include_files.append(p)

    include_dirs = [
        Path("artifacts") / "config",
        Path("artifacts") / "reports",
        Path("artifacts") / "models",
    ]

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in include_files:
            z.write(p, p.as_posix())
        for d in include_dirs:
            if d.exists():
                for root, dirs, files in os.walk(d):
                    for f in files:
                        full = Path(root) / f
                        z.write(full, full.as_posix())

    rel_url = f"/artifacts/backups/{out_zip.name}"
    return {"status": "ok", "path": str(out_zip.resolve()), "url": rel_url}


# ====== РУЧНОЙ BUY/SELL: Request/Response модели + логика ======
class ManualBuyRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: float | None = None
    note: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "bybit",
                "symbol": "ETH/USDT",
                "timeframe": "15m",
                "qty": 0.5,
                "price": 3500.25,
                "note": "test buy via API",
            }
        }
    )


class ManualSellRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: float | None = None
    note: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "bybit",
                "symbol": "ETH/USDT",
                "timeframe": "15m",
                "qty": 0.25,
                "price": 3520.00,
                "note": "manual sell via API",
            }
        }
    )


class ManualBuyResponse(BaseModel):
    status: Literal["ok", "error"]
    order: Dict[str, Any] | None = None
    trade: Dict[str, Any] | None = None
    position: Dict[str, Any] | None = None
    cash: float | None = None
    detail: str | None = None


def _manual_buy_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: str | None = None,
):
    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="buy",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=qty, price=price, fee=0.0)
    db.add(tr)

    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None:
        pos = PaperPosition(exchange=exchange, symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        db.add(pos)
        db.flush()

    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    new_qty = old_qty + float(qty)
    new_avg = (old_avg * old_qty + float(price) * float(qty)) / new_qty if new_qty != 0 else 0.0

    pos.qty = new_qty
    pos.avg_price = new_avg
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": pos.qty, "avg_price": pos.avg_price},
    }


def _manual_sell_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: str | None = None,
):
    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None or float(pos.qty or 0.0) <= 0.0:
        return {"status": "error", "detail": "нет открытой позиции для sell"}
    old_qty = float(pos.qty or 0.0)
    old_avg = float(pos.avg_price or 0.0)
    if qty > old_qty + 1e-12:
        return {"status": "error", "detail": f"qty={qty} больше чем в позиции ({old_qty})"}

    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="sell",
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=-float(qty), price=price, fee=0.0)
    db.add(tr)

    qty_to_close = float(qty)
    realized = (float(price) - old_avg) * qty_to_close
    pos.qty = old_qty - qty_to_close
    if pos.qty <= 1e-12:
        pos.qty = 0.0
        pos.avg_price = 0.0
    try:
        cur_rpnl = float(pos.realized_pnl or 0.0)
    except Exception:
        cur_rpnl = 0.0
    pos.realized_pnl = cur_rpnl + realized
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price), "realized_pnl": float(pos.realized_pnl)},
    }


def _manual_short_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: str | None = None,
):
    # qty > 0 означает "открыть/увеличить шорт" -> pos.qty уменьшится (в минус)
    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="sell",  # продаём для входа в шорт
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual short {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=-float(qty), price=price, fee=0.0)
    db.add(tr)

    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None:
        pos = PaperPosition(exchange=exchange, symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        db.add(pos)
        db.flush()

    old_qty = float(pos.qty or 0.0)  # может быть 0 или уже < 0 (шорт)
    old_avg = float(pos.avg_price or 0.0)
    add_abs = float(qty)

    new_qty = old_qty - add_abs  # уходим в минус
    base_abs = abs(old_qty)
    new_avg = (
        (old_avg * base_abs + float(price) * add_abs) / (base_abs + add_abs)
        if (base_abs + add_abs) > 0
        else float(price)
    )

    pos.qty = new_qty
    pos.avg_price = new_avg
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price)},
    }


def _manual_cover_db(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    qty: float,
    price: float,
    ts_iso: str,
    note: str | None = None,
):
    # qty > 0 означает "покрыть шорт" -> pos.qty растёт к нулю
    pos = (
        db.query(PaperPosition).filter(PaperPosition.exchange == exchange, PaperPosition.symbol == symbol).one_or_none()
    )
    if pos is None or float(pos.qty or 0.0) >= 0.0:
        return {"status": "error", "detail": "нет открытого шорта для cover"}

    old_qty = float(pos.qty or 0.0)  # отрицательное
    old_avg = float(pos.avg_price or 0.0)
    if qty > abs(old_qty) + 1e-12:
        return {"status": "error", "detail": f"qty={qty} больше чем в шорте ({abs(old_qty)})"}

    od = PaperOrder(
        exchange=exchange,
        symbol=symbol,
        side="buy",  # покупка для покрытия
        qty=qty,
        price=price,
        fee=0.0,
        status="filled",
        signal_event_id=None,
        note=note or f"manual cover {timeframe} @ {ts_iso}",
    )
    db.add(od)
    db.flush()
    tr = PaperTrade(order_id=od.id, exchange=exchange, symbol=symbol, qty=float(qty), price=price, fee=0.0)
    db.add(tr)

    # PnL для покрытия шорта: (entry_avg - cover_price) * qty_closed
    realized = (old_avg - float(price)) * float(qty)
    pos.qty = old_qty + float(qty)  # движемся к нулю
    if pos.qty >= -1e-12 and pos.qty <= 1e-12:
        pos.qty = 0.0
        pos.avg_price = 0.0

    try:
        cur_rpnl = float(pos.realized_pnl or 0.0)
    except Exception:
        cur_rpnl = 0.0
    pos.realized_pnl = cur_rpnl + realized
    pos.updated_at = _now_utc().replace(tzinfo=None)

    db.commit()
    return {
        "order": {"id": od.id, "qty": float(qty), "price": float(price)},
        "trade": {"id": tr.id},
        "position": {"qty": float(pos.qty), "avg_price": float(pos.avg_price), "realized_pnl": float(pos.realized_pnl)},
    }


@app.post("/trade/manual/buy", response_model=ManualBuyResponse, tags=["Trade"])
def trade_manual_buy(req: ManualBuyRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("open")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return {"status": "error", "detail": "нет последней цены и не задан price"}

    # 1) совершаем покупку (JSON или БД)
    try:
        from src.trade import paper_open_buy_manual  # type: ignore

        res = (
            paper_open_buy_manual(
                req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual buy via API"
            )
            or {}
        )
    except Exception:
        res = (
            _manual_buy_db(
                db,
                req.exchange,
                req.symbol,
                req.timeframe,
                float(req.qty),
                px,
                ts,
                note=req.note or "manual buy via API",
            )
            or {}
        )

    # 2) если в БД был открытый шорт — частично/полностью покрываем
    pos = (
        db.query(PaperPosition)
        .filter(PaperPosition.exchange == req.exchange, PaperPosition.symbol == req.symbol)
        .one_or_none()
    )

    if pos and float(pos.qty or 0.0) < 0:
        cover_qty = min(float(req.qty), abs(float(pos.qty)))
        if cover_qty > 0:
            _manual_cover_db(
                db, req.exchange, req.symbol, req.timeframe, cover_qty, px, ts, note=req.note or "manual cover via buy"
            )
        rem = float(req.qty) - cover_qty
        if rem > 1e-12:
            extra = (
                _manual_buy_db(
                    db, req.exchange, req.symbol, req.timeframe, rem, px, ts, note=req.note or "manual buy via API"
                )
                or {}
            )
            res.update(extra)

    return {"status": "ok", **(res if isinstance(res, dict) else {})}


@app.post("/trade/manual/sell", response_model=ManualBuyResponse, tags=["Trade"])
def trade_manual_sell(req: ManualSellRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("reduce")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return {"status": "error", "detail": "нет последней цены и не задан price"}

    # для sell пробуем сразу БД-фолбэк (он сам проверит позицию/кол-во)
    res = _manual_sell_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual sell via API"
    )
    if res.get("status") == "error":
        return res
    return {"status": "ok", **res}


class ManualShortRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: float | None = None
    note: str | None = None


class ManualCoverRequest(BaseModel):
    exchange: str
    symbol: str
    timeframe: str = "15m"
    qty: float
    price: float | None = None
    note: str | None = None


@app.post("/trade/manual/short", response_model=ManualBuyResponse, tags=["Trade"])
def trade_manual_short(req: ManualShortRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("open")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return {"status": "error", "detail": "нет последней цены и не задан price"}
    res = _manual_short_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual short via API"
    )
    return {"status": "ok", **res}


@app.post("/trade/manual/cover", response_model=ManualBuyResponse, tags=["Trade"])
def trade_manual_cover(req: ManualCoverRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    _trade_guard_enforce("close")
    ts = _now_utc().replace(microsecond=0).isoformat()
    px = float(req.price or (_last_close(db, req.exchange, req.symbol, req.timeframe) or 0.0))
    if px <= 0:
        return {"status": "error", "detail": "нет последней цены и не задан price"}
    res = _manual_cover_db(
        db, req.exchange, req.symbol, req.timeframe, float(req.qty), px, ts, note=req.note or "manual cover via API"
    )
    if res.get("status") == "error":
        return res
    return {"status": "ok", **res}


def _try_resolve_outcome_for_event(db: Session, evt: SignalEvent) -> bool:
    existing = db.query(SignalOutcome).filter(SignalOutcome.signal_event_id == evt.id).first()
    if existing:
        return False

    start_ms = _to_ms(evt.bar_dt)
    step_min = _tf_minutes(evt.timeframe)
    need_bars = int(evt.horizon_steps)
    if need_bars <= 0:
        return False
    end_ms = start_ms + need_bars * step_min * 60_000

    bars = (
        db.query(Price)
        .filter(
            Price.exchange == evt.exchange,
            Price.symbol == evt.symbol,
            Price.timeframe == evt.timeframe,
            Price.ts >= start_ms,
            Price.ts <= end_ms,
        )
        .order_by(Price.ts.asc())
        .all()
    )
    if len(bars) < need_bars + 1:
        return False

    entry = float(bars[0].close)
    exit_ = float(bars[need_bars].close)

    # нетто: учитываем комиссию и проскальзывание (per side)
    try:
        pol = load_policy()
    except Exception:
        pol = {}
    fee_bps = float((pol.get("fee_bps") or 8.0))  # по умолчанию 0.08% на сторону
    slip_bps = float((pol.get("slip_bps") or 5.0))  # по умолчанию 0.05% на сторону
    per_side = (fee_bps + slip_bps) / 10_000.0

    # покупаем дороже (entry * (1+...)), продаём дешевле (exit * (1-...))
    entry_eff = entry * (1.0 + per_side)
    exit_eff = exit_ * (1.0 - per_side)

    ret_h = exit_eff / entry_eff - 1.0

    # MDD считаем от эффективного входа (на пути торгов не совершается, поэтому путь брутто)
    path = [float(b.close) for b in bars[: need_bars + 1]]
    min_on_path = min(path)
    max_drawdown = min(min_on_path / entry_eff - 1.0, 0.0)

    out = SignalOutcome(
        signal_event_id=evt.id,
        exchange=evt.exchange,
        symbol=evt.symbol,
        timeframe=evt.timeframe,
        horizon_steps=evt.horizon_steps,
        entry_price=entry,
        exit_price=exit_,
        ret_h=ret_h,
        max_drawdown=max_drawdown,
    )
    db.add(out)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


# ------------------ automation API ------------------
@app.get("/automation/status", tags=["Automation"])
def automation_status(_=Depends(require_api_key)):
    jobs = scheduler.get_jobs()
    return [
        {
            "id": j.id,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            "trigger": str(j.trigger),
        }
        for j in jobs
    ]


class AutomationInput(BaseModel):
    job: str | None = None
    action: str | None = None
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    horizon_steps: int | None = None
    model_path: str | None = None


@app.post("/automation/run", tags=["Automation"])
def automation_run(req: AutomationInput, _=Depends(require_api_key)):
    if (req.action or "").lower() == "signal_once":
        ex = (req.exchange or "bybit").strip()
        sym = (req.symbol or "BTC/USDT").strip()
        tf = (req.timeframe or "15m").strip()
        hz = req.horizon_steps or (6 if tf.endswith("h") else 12)

        with SessionLocal() as db:
            df, _ = build_dataset(db, ex, sym, tf, hz)
            if df.empty:
                return {"status": "error", "detail": "Данных нет. Сначала загрузите цены/новости."}
            row = df.iloc[-1]
            bar_dt = row.name.to_pydatetime()
            close = float(row["close"])

            if req.model_path:
                model, feature_cols, threshold, model_path = load_model_from_path(req.model_path)
            else:
                try:
                    model, feature_cols, threshold, model_path = load_model_for(db, ex, sym, tf, hz)
                except FileNotFoundError:
                    model, feature_cols, threshold, model_path = load_latest_model()

            missing = [c for c in feature_cols if c not in row.index]
            if missing:
                return {"status": "error", "detail": f"В датасете отсутствуют признаки: {missing[:6]} ..."}

            X = row[feature_cols].values.reshape(1, -1)
            proba = float(model.predict_proba(X)[0, 1])
            base_signal = "buy" if proba > threshold else "flat"
            delta = proba - threshold

            policy = load_policy()
            min_gap = float(policy.get("min_prob_gap", 0.02))

            notify_cfg = policy.get("notify") or {}
            notify_on_buy = bool(notify_cfg.get("on_buy", True))
            notify_radar = bool(notify_cfg.get("radar", False))
            radar_gap = float(notify_cfg.get("radar_gap", 0.01))

            auto_cfg = policy.get("auto") or {}
            auto_trade_on_buy = bool(auto_cfg.get("trade_on_buy", False))
            cool_minutes = int(policy.get("cooldown_minutes", 90))

            last_evt = (
                db.query(SignalEvent)
                .filter(SignalEvent.exchange == ex, SignalEvent.symbol == sym, SignalEvent.timeframe == tf)
                .order_by(SignalEvent.bar_dt.desc())
                .first()
            )
            last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
            allow, reasons, metrics = evaluate_filters(row, df, policy, tf, last_bar_ts)
            allow_vol, r2, m2 = _volatility_guard(row, df, tf, policy)
            allow = allow and allow_vol
            reasons += r2
            metrics.update(m2)

            if base_signal == "buy" and delta < min_gap:
                reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
                allow = False

            final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

            evt = SignalEvent(
                exchange=ex,
                symbol=sym,
                timeframe=tf,
                horizon_steps=hz,
                bar_dt=bar_dt,
                close=close,
                prob_up=proba,
                threshold=threshold,
                signal=final_signal,
                model_path=model_path,
                note=json.dumps(
                    {
                        "base_signal": base_signal,
                        "prob": proba,
                        "threshold": threshold,
                        "prob_gap": delta,
                        "policy": policy,
                        "metrics": metrics,
                        "reasons": reasons,
                    },
                    ensure_ascii=False,
                ),
            )
            db.add(evt)
            try:
                db.commit()
                db.refresh(evt)
            except Exception:
                db.rollback()

            should_notify = (final_signal == "buy" and notify_on_buy) or (notify_radar and abs(delta) <= radar_gap)
            if evt.id and should_notify:
                maybe_send_signal_notification(
                    final_signal,
                    proba,
                    threshold,
                    delta,
                    reasons,
                    model_path,
                    ex,
                    sym,
                    tf,
                    bar_dt,
                    close,
                    source="endpoint",
                )

            if final_signal == "buy" and auto_trade_on_buy:
                try:
                    _trade_guard_enforce("open")
                except HTTPException as e:
                    # просто отметим причину, чтобы было видно в ответе
                    reasons.append(f"trade_guard:{getattr(e, 'detail', e)}")
                else:
                    if _cooldown_passed(db, ex, sym, tf, cool_minutes):
                        # авто-ордер по текущей цене
                        paper_open_buy_auto(ex, sym, tf, close, bar_dt.isoformat())
                    else:
                        reasons.append(f"cooldown_skip({cool_minutes}m)")

            return {
                "status": "ok",
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "bar_dt": bar_dt,
                "close": close,
                "prob_up": proba,
                "threshold": threshold,
                "prob_gap": delta,
                "signal": final_signal,
            }

    if (req.action or "").lower() == "discover_watchlist":
        res = discover_pairs(exchanges=("bybit",))
        return {"status": "ok", "added": res.get("added", []), "total_watchlist": res.get("total_watchlist")}

    if (req.action or "").lower() == "scan_watchlist":
        results = []
        pairs = pairs_for_jobs()
        with SessionLocal() as db:
            for ex, sym, tf, _ in pairs:
                try:
                    hz = req.horizon_steps or (6 if tf.endswith("h") else 12)
                    df, _ = build_dataset(db, ex, sym, tf, hz)
                    if df.empty:
                        results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": "no_data"})
                        continue
                    row = df.iloc[-1]
                    bar_dt = row.name.to_pydatetime()
                    close = float(row["close"])

                    model, feature_cols, threshold, model_path = load_model_for(db, ex, sym, tf, hz)
                    missing = [c for c in feature_cols if c not in row.index]
                    if missing:
                        results.append(
                            {
                                "exchange": ex,
                                "symbol": sym,
                                "timeframe": tf,
                                "status": f"error: missing features {missing[:6]}...",
                            }
                        )
                        continue
                    X = row[feature_cols].values.reshape(1, -1)
                    proba = float(model.predict_proba(X)[0, 1])
                    base_signal = "buy" if proba > threshold else "flat"
                    delta = proba - threshold

                    policy = load_policy()
                    last_evt = (
                        db.query(SignalEvent)
                        .filter(SignalEvent.exchange == ex, SignalEvent.symbol == sym, SignalEvent.timeframe == tf)
                        .order_by(SignalEvent.bar_dt.desc())
                        .first()
                    )
                    last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
                    allow, reasons, _ = evaluate_filters(row, df, policy, tf, last_bar_ts)
                    allow_vol, r2, _m2 = _volatility_guard(row, df, tf, policy)
                    allow = allow and allow_vol
                    reasons += r2
                    if base_signal == "buy" and delta < policy.get("min_prob_gap", 0.02):
                        reasons.append(f"prob_gap {delta:.3f} < {policy.get('min_prob_gap', 0.02)}")
                        allow = False
                    final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

                    # уведомления по правилам из policy.notify
                    notify_cfg = policy.get("notify") or {}
                    notify_on_buy = bool(notify_cfg.get("on_buy", True))
                    notify_radar = bool(notify_cfg.get("radar", False))
                    radar_gap = float(notify_cfg.get("radar_gap", 0.01))
                    should_notify = (final_signal == "buy" and notify_on_buy) or (
                        notify_radar and abs(delta) <= radar_gap
                    )
                    if should_notify:
                        maybe_send_signal_notification(
                            final_signal,
                            proba,
                            threshold,
                            delta,
                            reasons,
                            model_path,
                            ex,
                            sym,
                            tf,
                            bar_dt,
                            close,
                            source="endpoint",
                        )

                    results.append(
                        {
                            "exchange": ex,
                            "symbol": sym,
                            "timeframe": tf,
                            "bar_dt": bar_dt,
                            "close": close,
                            "prob_up": proba,
                            "threshold": threshold,
                            "prob_gap": delta,
                            "signal": final_signal,
                        }
                    )
                except Exception as e:
                    results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"error: {e}"})
        return {"status": "ok", "scanned": results}

    if (req.action or "").lower() == "train_missing":
        with SessionLocal() as db:
            return _train_missing_impl(db)

    mapping = {
        "discover_watchlist": job_discover_watchlist,
        "fetch_news": job_fetch_news,
        "analyze_news": job_analyze_news,
        "fetch_prices": job_fetch_prices,
        "train_models": job_train_models,
        "build_report": job_build_report,
        "make_signals": job_make_signals,
        "news_radar": job_news_radar,
    }
    if not req.job or req.job not in mapping:
        return {"status": "error", "detail": f"unknown job '{req.job}'"}
    try:
        mapping[req.job]()
        return {"status": "ok", "detail": f"job '{req.job}' executed"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ------------------ watchlist ------------------
@app.get("/watchlist", tags=["Watchlist"])
def watchlist_get(_=Depends(require_api_key)):
    return {"pairs": list_watchlist()}


class WatchlistSet(BaseModel):
    pairs: list[dict]


@app.post("/watchlist", tags=["Watchlist"])
def watchlist_set_api(req: WatchlistSet, _=Depends(require_api_key)):
    set_watchlist(req.pairs or [])
    return {"status": "ok", "pairs": list_watchlist()}


class WatchlistItem(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    limit: int = 500


@app.post("/watchlist/add", tags=["Watchlist"])
def watchlist_add(item: WatchlistItem, _=Depends(require_api_key)):
    wl_add_pair(item.exchange, item.symbol, item.timeframe, item.limit)
    return {"status": "ok", "pairs": list_watchlist()}


@app.post("/watchlist/remove", tags=["Watchlist"])
def watchlist_remove(item: WatchlistItem, _=Depends(require_api_key)):
    wl_remove_pair(item.exchange, item.symbol, item.timeframe)
    return {"status": "ok", "pairs": list_watchlist()}


class DiscoverParams(BaseModel):
    min_volume_usd: float = 2_000_000
    top_n_per_exchange: int = 25
    quotes: list[str] = ["USDT"]
    timeframes: list[str] = ["15m"]
    limit: int = 1000
    exchanges: list[str] = ["bybit"]


@app.post("/watchlist/discover", tags=["Watchlist"])
def watchlist_discover(req: DiscoverParams, _=Depends(require_api_key)):
    res = discover_pairs(
        min_volume_usd=req.min_volume_usd,
        top_n_per_exchange=req.top_n_per_exchange,
        quotes=tuple(req.quotes),
        timeframes=tuple(req.timeframes),
        limit=req.limit,
        exchanges=tuple(req.exchanges),
    )
    return {"status": "ok", **res}


@app.post("/watchlist/purge_exchange", tags=["Watchlist"])
def watchlist_purge_exchange(exchange: str, _=Depends(require_api_key)):
    exchange = exchange.lower().strip()
    cur = list_watchlist()
    kept = [p for p in cur if p.get("exchange", "").lower() != exchange]
    set_watchlist(kept)
    return {"status": "ok", "removed_exchange": exchange, "pairs": kept}


@app.get("/healthz", tags=["Debug"])
def healthz(db: Session = Depends(get_db)):
    db_ok = True
    try:
        # безопасный пинг БД
        db.execute(_sa_text("SELECT 1"))
    except Exception:
        db_ok = False
    jobs = scheduler.get_jobs()
    return {
        "ok": db_ok and bool(jobs is not None),
        "db_ok": db_ok,
        "scheduler": {"jobs": len(jobs), "locked": _SCHED_LOCK_OWNED},
    }


# ------------------ боты-команды ------------------
class BotCommand(BaseModel):
    text: str


@app.post("/bot/command", tags=["Trade"])
def bot_command(cmd: BotCommand, db: Session = Depends(get_db), _=Depends(require_api_key)):
    # --- NEWS INGEST SHORTCUT ---
    t = (cmd.text or "").strip()
    if t.lower().startswith("#news"):
        # беру всё после '#news' либо весь текст, если без пробела
        payload = t[5:].strip() or t
        try:
            res = _ingest_impl([payload])  # локальный вызов обработчика
        except Exception as e:
            return {"status": "error", "detail": f"ingest: {e}"}
        try:
            send_telegram(f"📰 NEWS INGESTED\nadded={res.get('added_pairs')} triggers={res.get('triggers')}")
        except Exception:
            pass
        return {"status": "ok", **res}

    try:
        action, ex, sym, qty, price, tf = _parse_trade_cmd(cmd.text)
    except Exception as e:
        return {"status": "error", "detail": f"parse: {e}"}

    ts = _now_utc().isoformat()

    # подтащим цену, если не задана
    if price is None:
        price = _last_close(db, ex, sym, tf)
        if price is None:
            return {"status": "error", "detail": "нет последней цены и не задан @ price"}

    # Kill-switch
    if action == "buy":
        _trade_guard_enforce("open")
    elif action == "sell":
        _trade_guard_enforce("reduce")
    elif action == "close":
        _trade_guard_enforce("close")

    # BUY
    if action == "buy":
        try:
            from src.trade import paper_open_buy_manual  # type: ignore

            res = paper_open_buy_manual(ex, sym, tf, float(qty), float(price), ts, note="bot /buy")
        except Exception:
            res = _manual_buy_db(db, ex, sym, tf, float(qty), float(price), ts, note="bot /buy")
        try:
            send_telegram(f"✍️ MANUAL BUY\n{ex.upper()} {sym} {tf}\nqty={qty} @ {price}\n{ts}")
        except Exception:
            pass
        return {"status": "ok", **res}

    # SELL
    if action == "sell":
        try:
            from src.trade import paper_open_sell_manual  # type: ignore

            res = paper_open_sell_manual(ex, sym, tf, float(qty), float(price), ts, note="bot /sell")
        except Exception:
            res = _manual_sell_db(db, ex, sym, tf, float(qty), float(price), ts, note="bot /sell")
        try:
            send_telegram(f"✍️ MANUAL SELL\n{ex.upper()} {sym} {tf}\nqty={qty} @ {price}\n{ts}")
        except Exception:
            pass
        return {"status": "ok", **res}

    # CLOSE
    if action == "close":
        # Пытаемся закрыть там, где реально есть позиция: DB -> JSON
        db_pos = db.query(PaperPosition).filter(PaperPosition.exchange == ex, PaperPosition.symbol == sym).one_or_none()
        db_qty = float(getattr(db_pos, "qty", 0.0) or 0.0)

        # Если передан qty > 0 — закрываем частично там, где есть позиция
        if qty is not None and float(qty) > 0:
            close_qty = float(qty)
            if db_qty > 1e-12:
                res = _manual_sell_db(db, ex, sym, tf, min(close_qty, db_qty), float(price), ts, note="bot /close qty")
            elif db_qty < -1e-12:
                res = _manual_cover_db(
                    db, ex, sym, tf, min(close_qty, abs(db_qty)), float(price), ts, note="bot /close qty"
                )
            else:
                return {"status": "error", "detail": "нет открытой позиции для close"}
            try:
                send_telegram(f"💼 CLOSE\n{ex.upper()} {sym} {tf}\nqty={close_qty} • @ {price}\n{ts}")
            except Exception:
                pass
            return {"status": "ok", **res}

        # Полное закрытие
        if db_qty > 1e-12:
            res = _manual_sell_db(db, ex, sym, tf, db_qty, float(price), ts, note="bot /close")
        elif db_qty < -1e-12:
            res = _manual_cover_db(db, ex, sym, tf, abs(db_qty), float(price), ts, note="bot /close")
        else:
            return {"status": "error", "detail": "нет открытой позиции для close"}
        try:
            send_telegram(f"💼 CLOSE\n{ex.upper()} {sym} {tf}\n@ {price}\n{ts}")
        except Exception:
            pass
        return {"status": "ok", **res}

    return {"status": "error", "detail": f"unknown action '{action}'"}


# ==== Equity history helpers ====


def _last_price_at_or_before(
    db: Session, exchange: str, symbol: str, timeframe: str, ts_dt: datetime
) -> Optional[float]:
    """Цена закрытия последнего бара <= ts_dt для указанного TF."""
    try:
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=_tz.utc)
        ts_ms = _to_ms(ts_dt)
        r = (
            db.query(Price)
            .filter(
                Price.exchange == exchange,
                Price.symbol == symbol,
                Price.timeframe == timeframe,
                Price.ts <= ts_ms,
            )
            .order_by(Price.ts.desc())
            .first()
        )
        return float(r.close) if r else None
    except Exception:
        return None


def _compute_equity_history(
    db: Session,
    timeframe: str = "15m",
    days: int = 7,
    include_json: bool = False,
):
    """
    Строит историю equity за заданное окно.
    Логика:
      1) Берём стартовый cash из JSON-состояния (если доступен).
      2) Собираем ВСЕ ордера (БД + опционально JSON), сортируем по времени.
      3) Применяем ордера, которые были ДО since -> получаем стартовое состояние на начало окна.
      4) Для ордеров, которые ПОСЛЕ since, считаем точки equity на моменте ордера.
      5) Добавляем финальную точку 'сейчас' (mark-to-market).
      6) Если ордеров нет совсем — считаем текущее equity из открытых позиций (БД + опц. JSON) и возвращаем одну точку.
    """
    now = _now_utc()
    since = now - timedelta(days=int(days))

    # --- параметры из policy: комиссии и проскальзывание (на сторону) ---
    try:
        pol = load_policy()
    except Exception:
        pol = {}
    fee_bps = float((pol.get("fee_bps") or 8.0))  # 0.08% по умолчанию на сторону
    slip_bps = float((pol.get("slip_bps") or 5.0))  # 0.05% по умолчанию на сторону
    per_side = (fee_bps + slip_bps) / 10_000.0  # доля на сторону

    # --- стартовый кэш из JSON-состояния (если доступен) ---
    cash_source = "json_state"
    try:
        from src.trade import _load_state  # type: ignore

        st = _load_state()
        init_cash = float(st.get("cash", 0.0) or 0.0)
    except Exception:
        cash_source = "assumed_0"
        init_cash = 0.0

    # --- собираем ордера: БД (+ опционально JSON) ---
    orders: list[dict] = []

    # БД-ордера (ТОЛЬКО собираем события)
    try:
        for o in db.query(PaperOrder).order_by(PaperOrder.created_at.asc()).all():
            if not o.created_at:
                continue
            ts = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=_tz.utc)
            orders.append(
                {
                    "ts": ts,
                    "exchange": o.exchange,
                    "symbol": o.symbol,
                    "side": (o.side or "").lower(),
                    "qty": float(o.qty or 0.0),
                    "price": float(o.price or 0.0),
                    "source": "db",
                }
            )
    except Exception:
        pass

    # JSON-ордера (если не импортированы в БД и вы хотите учесть их напрямую)
    if include_json:
        try:
            for j in paper_get_orders():
                ts_pd = pd.to_datetime(j.get("ts"))
                if pd.isna(ts_pd):
                    continue
                ts = ts_pd.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_tz.utc)
                orders.append(
                    {
                        "ts": ts,
                        "exchange": j.get("exchange"),
                        "symbol": j.get("symbol"),
                        "side": (j.get("side") or "").lower(),
                        "qty": float(j.get("qty") or 0.0),
                        "price": float(j.get("price") or 0.0),
                        "source": "json",
                    }
                )
        except Exception:
            pass

    # Хронологический порядок обязателен для корректной эволюции cash/positions
    orders.sort(key=lambda r: r["ts"])

    # --- если ордеров совсем нет: вернём одну точку «сейчас» на основе открытых позиций ---
    if not orders:
        positions: dict[tuple[str, str], float] = {}
        # Позиции из БД
        try:
            for p in db.query(PaperPosition).all():
                qty = float(p.qty or 0.0)
                if abs(qty) > 0:
                    positions[(p.exchange, p.symbol)] = positions.get((p.exchange, p.symbol), 0.0) + qty
        except Exception:
            pass
        # Позиции из JSON (если не импортированы в БД)
        if include_json:
            try:
                for jpos in paper_get_positions():
                    key = (jpos["exchange"], jpos["symbol"])
                    qty = float(jpos.get("qty", 0.0))
                    if abs(qty) > 0 and key not in positions:
                        positions[key] = positions.get(key, 0.0) + qty
            except Exception:
                pass

        mv = 0.0
        for (ex, sym), qty in positions.items():
            px = _last_close(db, ex, sym, timeframe) or 0.0
            mv += qty * px

        equity_now = init_cash + mv
        return {
            "status": "ok",
            "timeframe": timeframe,
            "start": since.isoformat(),
            "end": now.isoformat(),
            "cash_source": cash_source,
            "equity": [{"ts": now.isoformat(), "equity": float(equity_now)}],
            "equity_base": float(equity_now),  # база = текущему значению, чтобы PnL = 0
            "base_cash": float(init_cash),
            "stats": {"pnl_abs": 0.0, "pnl_pct": 0.0, "max_drawdown": 0.0},
            "csv_url": None,
        }

    # --- основная ветка: есть ордера ---
    cash = float(init_cash)
    positions: dict[tuple[str, str], float] = {}  # (exchange, symbol) -> qty
    points: list[dict] = []

    def _portfolio_value_at(ts: datetime) -> float:
        total = 0.0
        for (ex, sym), qty in positions.items():
            if abs(qty) <= 0:
                continue
            px = _last_price_at_or_before(db, ex, sym, timeframe, ts)
            if px is None:
                # fallback: последняя цена по TF, если нет цены строго <= ts
                px = _last_close(db, ex, sym, timeframe) or 0.0
            total += qty * float(px)
        return total

    def _apply(side: str, qty: float, price: float, ex: str, sym: str) -> None:
        nonlocal cash, positions
        if side == "buy":
            # покупка дороже на (fee+slip)
            cash -= float(price) * float(qty) * (1.0 + per_side)
            positions[(ex, sym)] = positions.get((ex, sym), 0.0) + float(qty)
        elif side == "sell":
            # продажа дешевле на (fee+slip)
            cash += float(price) * float(qty) * (1.0 - per_side)
            positions[(ex, sym)] = positions.get((ex, sym), 0.0) - float(qty)

    # 1) прогреваем состояние на момент since (применяем все ордера ДО окна)
    for ev in orders:
        if ev["ts"] >= since:
            break
        _apply(
            ev["side"],
            float(ev["qty"] or 0.0),
            float(ev["price"] or 0.0),
            ev["exchange"],
            ev["symbol"],
        )
        # остальные стороны игнорируем (на кэш/позиции не влияют)

    # Точка-база на начало окна
    base_equity = cash + _portfolio_value_at(since)
    points.append({"ts": since.isoformat(), "equity": float(base_equity)})

    # 2) точки по событиям ВНУТРИ окна
    for ev in orders:
        ts = ev["ts"]
        if ts < since:
            continue
        _apply(
            ev["side"],
            float(ev["qty"] or 0.0),
            float(ev["price"] or 0.0),
            ev["exchange"],
            ev["symbol"],
        )
        equity_t = cash + _portfolio_value_at(ts)
        points.append({"ts": ts.isoformat(), "equity": float(equity_t)})

    # 3) финальная точка "сейчас"
    equity_now = cash + _portfolio_value_at(now)
    points.append({"ts": now.isoformat(), "equity": float(equity_now)})

    # =========================
    # POST-PROCESS: clamp + dedup + sort + robust stats
    # =========================

    def _as_utc_dt(x):
        if isinstance(x, datetime):
            dt = x
        else:
            dt = pd.to_datetime(x).to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt

    # 1) отфильтруем точки за пределами окна [since, now] и
    #    оставим по одному значению на каждый ts (последнее по времени обработки)
    ts_to_equity: dict[datetime, float] = {}
    for p in points:
        t = _as_utc_dt(p["ts"])
        if t < since or t > now:
            continue
        ts_to_equity[t] = float(p["equity"])  # overwrite = берём последнее

    # гарантируем наличие граничных точек начала/конца окна
    ts_to_equity[since] = float(ts_to_equity.get(since, base_equity))
    ts_to_equity[now] = float(cash + _portfolio_value_at(now))

    # 2) отсортируем и соберём обратно
    ts_sorted = sorted(ts_to_equity.keys())
    points_sorted = [{"ts": t.isoformat(), "equity": ts_to_equity[t]} for t in ts_sorted]

    # 3) метрики на отсортированной серии
    eq_vals = [p["equity"] for p in points_sorted]
    if eq_vals:
        e0 = eq_vals[0]
        en = eq_vals[-1]
        pnl_abs = en - e0
        denom = abs(e0) if e0 != 0 else 1.0
        pnl_pct = pnl_abs / denom

        # Max Drawdown считаем на индексе, нормированном к 1 в начале,
        # чтобы корректно работать и при отрицательной базе.
        index = [1.0 + (v - e0) / denom for v in eq_vals]
        peak = index[0]
        max_dd = 0.0
        for i in index:
            if i > peak:
                peak = i
            dd = (i / peak) - 1.0
            if dd < max_dd:
                max_dd = dd
    else:
        e0 = en = pnl_abs = pnl_pct = 0.0
        max_dd = 0.0

    # Если «кэш из состояния» некорректный (<=0), не вводим в заблуждение base_cash'ем.
    base_cash_out = float(init_cash) if init_cash > 0 else 0.0

    # --- сохраняем CSV для UI/отладки ---
    Path("artifacts").mkdir(exist_ok=True)
    df = pd.DataFrame(points_sorted)
    csv_name = f"equity_history_{timeframe}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = Path("artifacts") / csv_name
    try:
        df.to_csv(csv_path, index=False, encoding="utf-8")
        csv_url = f"/artifacts/{csv_name}"
    except Exception:
        csv_url = None

    return {
        "status": "ok",
        "timeframe": timeframe,
        "start": since.isoformat(),
        "end": now.isoformat(),
        "cash_source": cash_source,
        "equity": points_sorted,
        "equity_base": float(e0),
        "base_cash": base_cash_out,
        "stats": {
            "pnl_abs": float(pnl_abs),
            "pnl_pct": float(pnl_pct),
            "max_drawdown": float(max_dd),
        },
        "fees_bps": float(fee_bps),
        "slippage_bps": float(slip_bps),
        "per_side": float(per_side),
        "csv_url": csv_url,
    }


# ------------------ старт/стоп планировщика ------------------
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # 1) Если есть psutil — используем самый надежный путь
        try:
            import psutil  # type: ignore

            return psutil.pid_exists(pid)
        except Exception:
            pass

        # 2) Windows: пробуем открыть дескриптор процесса
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False

        # 3) POSIX: классический probe сигналом 0
        os.kill(pid, 0)
        return True
    except Exception:
        return False


_SCHED_LOCK_PATH = Path("artifacts/state/scheduler.lock")
_SCHED_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
_SCHED_LOCK_OWNED = False


def _acquire_scheduler_lock() -> bool:
    """
    Пытаемся атомарно создать lock-файл.
    Если он есть — проверяем, жив ли pid. Если нет — чистим и пробуем снова.
    """
    global _SCHED_LOCK_OWNED
    try:
        fd = os.open(str(_SCHED_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        _SCHED_LOCK_OWNED = True
        return True
    except FileExistsError:
        try:
            pid = int((_SCHED_LOCK_PATH.read_text() or "0").strip() or "0")
        except Exception:
            pid = 0
        if pid and _pid_alive(pid):
            return False
        try:
            _SCHED_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            return False
        return _acquire_scheduler_lock()
    except Exception:
        return False


def _release_scheduler_lock():
    global _SCHED_LOCK_OWNED
    if _SCHED_LOCK_OWNED:
        try:
            _SCHED_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        _SCHED_LOCK_OWNED = False


@app.on_event("startup")
def on_startup():
    if not _acquire_scheduler_lock():
        print("[scheduler] lock is held by another process — skipping scheduler init")
        return
    # === индексы/уникальные ключи (создаём, если ещё нет) ===
    try:
        from src.db import ensure_runtime_indexes, SessionLocal

        with SessionLocal() as s:
            eng = s.get_bind()
        if eng is not None:
            ensure_runtime_indexes(eng)
            print("[db] indexes ensured")
    except Exception as e:
        print(f"[db] ensure indexes error: {e}")

    scheduler.add_job(
        job_discover_watchlist, CronTrigger(hour=0, minute=10), id="discover_watchlist", replace_existing=True
    )
    scheduler.add_job(
        job_fetch_news,
        IntervalTrigger(minutes=30),
        id="news_fetch",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_analyze_news,
        IntervalTrigger(minutes=30),
        id="news_analyze",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=_now_utc(),
    )
    scheduler.add_job(job_fetch_prices, IntervalTrigger(minutes=15), id="prices_fetch", replace_existing=True)
    scheduler.add_job(job_train_models, CronTrigger(hour=0, minute=35), id="train_models", replace_existing=True)
    scheduler.add_job(job_build_report, CronTrigger(hour=0, minute=50), id="build_report", replace_existing=True)
    scheduler.add_job(job_make_signals, IntervalTrigger(minutes=15), id="make_signals", replace_existing=True)
    scheduler.add_job(job_resolve_outcomes, IntervalTrigger(minutes=5), id="resolve_outcomes", replace_existing=True)
    scheduler.add_job(job_monitor_positions, IntervalTrigger(minutes=5), id="monitor_positions", replace_existing=True)
    scheduler.add_job(job_bootstrap, id="bootstrap_once", next_run_time=_now_utc(), replace_existing=True)
    scheduler.add_job(job_self_audit_and_notify, CronTrigger(hour=1, minute=10), id="self_audit", replace_existing=True)
    scheduler.add_job(
        job_news_radar,
        IntervalTrigger(minutes=10),
        id="news_radar",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    try:
        scheduler.start()
        print("[scheduler] started (primary)")
    except Exception as e:
        print(f"[scheduler] start error: {e}")
        _release_scheduler_lock()


@app.on_event("shutdown")
def on_shutdown():
    try:
        scheduler.shutdown()
        print("[scheduler] shutdown")
    except Exception:
        pass
    finally:
        _release_scheduler_lock()

    # аккуратно утилизируем движок БД
    try:
        with SessionLocal() as s:
            eng = s.get_bind()
        if eng is not None:
            eng.dispose()
            print("[db] engine disposed")
    except Exception as e:
        print(f"[db] dispose error: {e}")


# ------------------ train-missing core ------------------
def _train_missing_impl(db: Session) -> dict:
    policy = load_model_policy()
    pairs = pairs_for_jobs()
    results = []
    for ex, sym, tf, _ in pairs:
        hz = 6 if tf.endswith("h") else 12
        try:
            df, feature_cols = build_dataset(db, ex, sym, tf, hz)
            if len(df) < int(policy.get("min_train_rows", 200)):
                results.append(
                    {"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"skip:not_enough_data({len(df)})"}
                )
                continue

            need, reason, _ = _model_needs_retrain(db, ex, sym, tf, hz, policy, df_len=len(df))
            if not need:
                results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"skip:{reason}"})
                continue

            metrics, model_path = train_xgb_and_save(df, feature_cols, artifacts_dir="artifacts")
            run = ModelRun(
                exchange=ex,
                symbol=sym,
                timeframe=tf,
                horizon_steps=hz,
                n_train=metrics["n_train"],
                n_test=metrics["n_test"],
                accuracy=metrics.get("accuracy"),
                roc_auc=metrics.get("roc_auc"),
                threshold=metrics.get("threshold"),
                total_return=metrics.get("total_return"),
                sharpe_like=metrics.get("sharpe_like"),
                model_path=model_path,
                features_json=json.dumps({"features": feature_cols}, ensure_ascii=False),
            )
            db.add(run)
            db.commit()

            if not get_active_model_path(ex, sym, tf, hz):
                set_active_model(ex, sym, tf, hz, model_path)

            results.append(
                {
                    "exchange": ex,
                    "symbol": sym,
                    "timeframe": tf,
                    "status": "trained",
                    "reason": reason,
                    "model_path": model_path,
                    "metrics": metrics,
                }
            )
        except Exception as e:
            results.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": f"error:{e}"})
    return {"status": "ok", "results": results}


class IngestBody(BaseModel):
    source: str = "manual"
    texts: list[str]


def _ingest_impl(texts: list[str]) -> dict:
    """
    Простейший приёмник внешних текстов. Делает три вещи:
    1) выдёргивает листинги вида 'XXX/USDT' и добавляет в watchlist,
    2) ловит брейкауты типа 'BTC пробивает 112000',
    3) запускает синк цен и анализ новостей.
    """
    added: list[str] = []
    triggers: list[tuple[str, float]] = []

    for t in texts:
        # 1) листинги
        for m in re.findall(r"\b([A-Z0-9]{2,15})/USDT\b", (t or "").upper()):
            pair = f"{m}/USDT"
            try:
                wl_add_pair("bybit", pair, "15m", 1000)
                added.append(pair)
            except Exception:
                # не падаем на дублях
                pass

        # 2) брейкауты (очень грубо)
        m2 = re.search(r"\b(BTC|ETH)\b.*?(\d{3,6})(?:[.,](\d{2}))?", (t or "").upper())
        if m2:
            sym = m2.group(1) + "/USDT"
            price = float(m2.group(2).replace(",", ""))
            triggers.append((sym, price))

    # 3) запуск обновления: цены+новости
    try:
        from src.automation import job_prices_sync, job_news_analyze

        job_prices_sync()
        job_news_analyze()
    except Exception:
        pass

    if added or triggers:
        try:
            send_telegram(f"[INGEST] added={added} triggers={triggers}")
        except Exception:
            pass

    return {"added_pairs": added, "triggers": triggers}


@router.post("/news/ingest", tags=["News"])
def ingest_manual(b: IngestBody, _=Depends(require_api_key)):
    return _ingest_impl(b.texts)


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo:
        dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    return dt


def _compute_signal_for_last_bar(db: Session, ex: str, sym: str, tf: str, hz: int, model_path: str | None):
    df, _ = build_dataset(db, ex, sym, tf, hz)
    if df.empty:
        return {"status": "error", "detail": "Данных нет."}

    row = df.iloc[-1]
    bar_dt = row.name.to_pydatetime()
    close = float(row["close"])

    if model_path:
        model, feature_cols, threshold, model_path = load_model_from_path(model_path)
    else:
        try:
            model, feature_cols, threshold, model_path = load_model_for(db, ex, sym, tf, hz)
        except FileNotFoundError:
            model, feature_cols, threshold, model_path = load_latest_model()

    missing = [c for c in feature_cols if c not in row.index]
    if missing:
        return {"status": "error", "detail": f"В датасете отсутствуют признаки: {missing[:6]} ..."}

    X = row[feature_cols].values.reshape(1, -1)
    proba = float(model.predict_proba(X)[0, 1])
    base_signal = "buy" if proba > threshold else "flat"
    delta = proba - threshold

    policy = load_policy()
    min_gap = float((policy or {}).get("min_prob_gap", 0.02))
    last_evt = (
        db.query(SignalEvent)
        .filter(SignalEvent.exchange == ex, SignalEvent.symbol == sym, SignalEvent.timeframe == tf)
        .order_by(SignalEvent.bar_dt.desc())
        .first()
    )
    last_bar_ts = pd.Timestamp(last_evt.bar_dt) if last_evt else None  # type: ignore
    allow, reasons, metrics = evaluate_filters(row, df, policy, tf, last_bar_ts)
    allow_vol, r2, m2 = _volatility_guard(row, df, tf, policy)
    allow = allow and allow_vol
    reasons += r2
    metrics.update(m2)

    if base_signal == "buy" and delta < min_gap:
        reasons.append(f"prob_gap {delta:.3f} < {min_gap}")
        allow = False

    final_signal = "buy" if (base_signal == "buy" and allow) else "flat"

    return {
        "status": "ok",
        "exchange": ex,
        "symbol": sym,
        "timeframe": tf,
        "bar_dt": bar_dt,
        "close": close,
        "prob_up": proba,
        "threshold": threshold,
        "prob_gap": delta,
        "signal": final_signal,
        "reasons": reasons,
        "metrics": metrics,
        "model_path": model_path,
    }


# ---------- DB (read-only) ----------
@app.get("/db/info", tags=["DB"])
def db_info(_=Depends(require_api_key)):
    with SessionLocal() as s:
        eng = s.get_bind()
        url = str(getattr(eng, "url", None)) if eng else None
        dialect = getattr(getattr(eng, "dialect", None), "name", None) if eng else None
        insp = _sa_inspect(eng) if eng else None
        tables = sorted(insp.get_table_names()) if insp else []
    return {"url": url, "dialect": dialect, "tables": tables}


@app.get("/db/tables", tags=["DB"])
def db_tables(_=Depends(require_api_key), db: Session = Depends(get_db)):
    eng = db.get_bind()
    insp = _sa_inspect(eng)
    out = []
    for name in insp.get_table_names():
        cnt = db.execute(_sa_text(f'SELECT COUNT(1) AS c FROM "{name}"')).scalar()
        out.append({"name": name, "rows": int(cnt or 0)})
    return {"status": "ok", "tables": out}


@app.get("/db/table", tags=["DB"])
def db_table(name: str, limit: int = 100, db: Session = Depends(get_db), _=Depends(require_api_key)):
    eng = db.get_bind()
    insp = _sa_inspect(eng)
    names = set(insp.get_table_names())
    if name not in names:
        raise HTTPException(status_code=404, detail=f"unknown table '{name}'")

    pk_cols = (insp.get_pk_constraint(name) or {}).get("constrained_columns") or []
    if pk_cols:
        order_col = pk_cols[0]
    else:
        cols = insp.get_columns(name)
        order_col = cols[0]["name"] if cols else None

    if order_col:
        sql = _sa_text(f'SELECT * FROM "{name}" ORDER BY "{order_col}" DESC LIMIT :lim')
    else:
        sql = _sa_text(f'SELECT * FROM "{name}" LIMIT :lim')

    rows = db.execute(sql, {"lim": int(limit)}).mappings().all()
    return {"status": "ok", "name": name, "rows": rows}


# ---------- Мониторинг: запустить сейчас ----------
@app.post("/monitor/run_now", tags=["Trade"])
def monitor_run_now(_=Depends(require_api_key)):
    job_monitor_positions()
    return {"status": "ok", "detail": "monitor executed"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=os.getenv("RELOAD", "1") == "1")
