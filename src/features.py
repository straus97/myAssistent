# src/features.py
from typing import List, Tuple
from datetime import timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from .db import Price, Article, ArticleAnnotation

# Соответствие таймфреймов pandas
PANDAS_FREQ = {
    "1m": "1T", "5m": "5T", "15m": "15T", "1h": "1H", "4h": "4H", "1d": "1D"
}

# Набор тегов, которые будем агрегировать
TAGS = ["btc","eth","etf","sec","hack","regulation","listing","adoption","bullish","bearish","halving"]

def load_prices_df(db: Session, exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    rows = (
        db.query(Price)
        .filter(Price.exchange==exchange, Price.symbol==symbol, Price.timeframe==timeframe)
        .order_by(Price.ts.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume
    } for r in rows])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("dt").sort_index()
    return df

def load_news_df(db: Session) -> pd.DataFrame:
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .all()
    )
    data = []
    for art, ann in rows:
        if art.published_at is None:
            continue
        dt = art.published_at
        # Приводим к UTC-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        tags = (ann.tags or "")
        data.append({
            "dt": dt,
            "sentiment": ann.sentiment if ann.sentiment is not None else 0.0,
            "tags": tags.lower()
        })
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).set_index("dt").sort_index()
    # one-hot по тегам
    for t in TAGS:
        df[f"tag_{t}"] = df["tags"].str.contains(fr"\b{t}\b", case=False, na=False).astype(int)
    df["news_count"] = 1
    return df

def build_dataset(
    db: Session,
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    horizon_steps: int = 6  # предсказываем рост через 6 баров (для 1h ~ 6 часов)
) -> Tuple[pd.DataFrame, List[str]]:
    freq = PANDAS_FREQ.get(timeframe, "1H")
    px = load_prices_df(db, exchange, symbol, timeframe)
    if px.empty:
        raise ValueError("Нет цен в БД. Сначала вызови /prices/fetch.")
    news = load_news_df(db)

    # --- ценовые фичи ---
    df = px.copy()
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["vol_norm"] = (df["volume"] - df["volume"].rolling(24).mean()) / (df["volume"].rolling(24).std() + 1e-9)

    # --- новости: агрегируем по таймфрейму свечи ---
    if news is not None and not news.empty:
        agg_dict = {"sentiment":"mean", "news_count":"sum"}
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
        # если новостей ещё нет — заполняем нулями
        for w in [6, 24]:
            df[f"news_cnt_{w}"] = 0.0
            df[f"sent_mean_{w}"] = 0.0
            for t in TAGS:
                df[f"tag_{t}_{w}"] = 0.0

    # --- целевая переменная: будущая доходность ---
    df["future_ret"] = df["close"].shift(-horizon_steps) / df["close"] - 1.0
    df["y"] = (df["future_ret"] > 0).astype(int)

    # формируем список признаков
    feature_cols = [
        "ret_1", "ret_3", "ret_6", "vol_norm",
        "news_cnt_6", "news_cnt_24", "sent_mean_6", "sent_mean_24",
    ] + [f"tag_{t}_{6}" for t in TAGS] + [f"tag_{t}_{24}" for t in TAGS]

    # убираем строки с NaN (в начале ряда и в конце, где нет future_ret)
    df = df.dropna(subset=feature_cols + ["future_ret", "y"])
    return df, feature_cols
