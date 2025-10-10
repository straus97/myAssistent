from __future__ import annotations
from typing import List, Tuple
from datetime import timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from .db import Price, Article, ArticleAnnotation

# Соответствие таймфреймов pandas (без устаревших 'T'/'H')
PANDAS_FREQ = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}

# Набор тегов, которые будем агрегировать
TAGS = ["btc", "eth", "etf", "sec", "hack", "regulation", "listing", "adoption", "bullish", "bearish", "halving"]

# --- технические индикаторы (без внешних зависимостей) ---


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """RSI по Уайлдеру через EWM(alpha=1/window). Возвращает 0..100."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)


def _bbands(series: pd.Series, window: int = 20, nstd: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Полосы Боллинджера: (mid, upper, lower).
    std считаем с ddof=0, min_periods=window.
    """
    mid = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std(ddof=0)
    upper = mid + nstd * std
    lower = mid - nstd * std
    return mid, upper, lower


def load_prices_df(db: Session, exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    rows = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [{"ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume} for r in rows]
    )
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("dt").sort_index()
    return df


def load_news_df(db: Session) -> pd.DataFrame:
    rows = (
        db.query(Article, ArticleAnnotation).join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id).all()
    )
    data = []
    for art, ann in rows:
        if art.published_at is None:
            continue
        dt = art.published_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        tags = ann.tags or ""
        data.append({"dt": dt, "sentiment": ann.sentiment if ann.sentiment is not None else 0.0, "tags": tags.lower()})
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).set_index("dt").sort_index()
    # one-hot по тегам
    for t in TAGS:
        df[f"tag_{t}"] = df["tags"].str.contains(rf"\b{t}\b", case=False, na=False).astype(int)
    df["news_count"] = 1
    return df


def build_dataset(
    db: Session, exchange: str = "binance", symbol: str = "BTC/USDT", timeframe: str = "1h", horizon_steps: int = 6
) -> Tuple[pd.DataFrame, List[str]]:
    """Строит фичи и целевую переменную для заданной пары/ТФ/горизонта."""
    freq = PANDAS_FREQ.get(timeframe, "1h")

    px = load_prices_df(db, exchange, symbol, timeframe)
    if px.empty:
        raise ValueError("Нет цен в БД. Сначала вызови /prices/fetch.")
    news = load_news_df(db)

    # --- ценовые фичи ---
    df = px.copy()
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["ret_12"] = df["close"].pct_change(12)
    df["vol_norm"] = (df["volume"] - df["volume"].rolling(24).mean()) / (df["volume"].rolling(24).std() + 1e-9)

    # --- технические фичи ---
    # RSI(14)
    df["rsi_14"] = _rsi(df["close"], window=14)

    # Bollinger Bands (20, 2)
    mid, upper, lower = _bbands(df["close"], window=20, nstd=2.0)
    # относительная ширина (без деления на 0 и бесконечностей)
    df["bb_width_20_2"] = (
        ((upper - lower) / mid.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).clip(lower=-10, upper=10)
    )
    # положение цены внутри полос (0..1)
    df["bb_pct_20_2"] = ((df["close"] - lower) / (upper - lower)).clip(0, 1)

    # --- новости: агрегируем по таймфрейму свечи ---
    if news is not None and not news.empty:
        agg_dict = {"sentiment": "mean", "news_count": "sum"}
        for t in TAGS:
            agg_dict[f"tag_{t}"] = "sum"

        news_bin = news.resample(freq).agg(agg_dict).fillna(0)

        # роллинг-окна по новостям (6 и 24 бина)
        for w in [6, 24]:
            df[f"news_cnt_{w}"] = news_bin["news_count"].reindex(df.index, fill_value=0).rolling(w).sum()
            df[f"sent_mean_{w}"] = news_bin["sentiment"].reindex(df.index, fill_value=0).rolling(w).mean()
            for t in TAGS:
                df[f"tag_{t}_{w}"] = news_bin[f"tag_{t}"].reindex(df.index, fill_value=0).rolling(w).sum()
    else:
        for w in [6, 24]:
            df[f"news_cnt_{w}"] = 0.0
            df[f"sent_mean_{w}"] = 0.0
            for t in TAGS:
                df[f"tag_{t}_{w}"] = 0.0

    # --- целевая переменная ---
    df["future_ret"] = df["close"].shift(-horizon_steps) / df["close"] - 1.0
    df["y"] = (df["future_ret"] > 0).astype(int)

    feature_cols = (
        [
            "ret_1",
            "ret_3",
            "ret_6",
            "ret_12",
            "vol_norm",
            # новые технические признаки:
            "rsi_14",
            "bb_pct_20_2",
            "bb_width_20_2",
            # новости:
            "news_cnt_6",
            "news_cnt_24",
            "sent_mean_6",
            "sent_mean_24",
        ]
        + [f"tag_{t}_{6}" for t in TAGS]
        + [f"tag_{t}_{24}" for t in TAGS]
    )

    df = df.dropna(subset=feature_cols + ["future_ret", "y"])
    return df, feature_cols
