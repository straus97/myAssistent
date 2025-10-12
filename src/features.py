from __future__ import annotations
from typing import List, Tuple
from datetime import timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from .db import Price, Article, ArticleAnnotation
from .onchain import get_onchain_features
from .macro import get_macro_features
from .social import get_social_features

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


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD (Moving Average Convergence Divergence)
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Average True Range (ATR) - волатильность
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    return atr


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Average Directional Index (ADX) - сила тренда (0-100)
    Высокие значения (>25) = сильный тренд
    """
    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    pos_dm = pd.Series(pos_dm, index=high.index)
    neg_dm = pd.Series(neg_dm, index=low.index)
    
    # Smoothed indicators
    atr = tr.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    pos_di = 100 * (pos_dm.ewm(alpha=1/window, adjust=False, min_periods=window).mean() / atr)
    neg_di = 100 * (neg_dm.ewm(alpha=1/window, adjust=False, min_periods=window).mean() / atr)
    
    # ADX
    dx = 100 * ((pos_di - neg_di).abs() / (pos_di + neg_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    
    return adx.fillna(0)


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_window: int = 14, d_window: int = 3) -> tuple[pd.Series, pd.Series]:
    """
    Stochastic Oscillator - перекупленность/перепроданность
    Returns: (%K, %D)
    %K > 80 = overbought, %K < 20 = oversold
    """
    lowest_low = low.rolling(window=k_window, min_periods=k_window).min()
    highest_high = high.rolling(window=k_window, min_periods=k_window).max()
    
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan))
    d_percent = k_percent.rolling(window=d_window, min_periods=d_window).mean()
    
    return k_percent.fillna(50), d_percent.fillna(50)


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Williams %R - momentum indicator (-100 to 0)
    Values > -20 = overbought, < -80 = oversold
    """
    highest_high = high.rolling(window=window, min_periods=window).max()
    lowest_low = low.rolling(window=window, min_periods=window).min()
    
    williams = -100 * ((highest_high - close) / (highest_high - lowest_low).replace(0, np.nan))
    return williams.fillna(-50)


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> pd.Series:
    """
    Commodity Channel Index (CCI)
    Typical values: +100 to -100, but can exceed
    > +100 = overbought, < -100 = oversold
    """
    typical_price = (high + low + close) / 3
    sma = typical_price.rolling(window=window, min_periods=window).mean()
    mad = (typical_price - sma).abs().rolling(window=window, min_periods=window).mean()
    
    cci = (typical_price - sma) / (0.015 * mad.replace(0, np.nan))
    return cci.fillna(0)


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

    # --- ценовые фичи (returns) ---
    df = px.copy()
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["ret_12"] = df["close"].pct_change(12)
    df["ret_24"] = df["close"].pct_change(24)  # Новая фича
    df["vol_norm"] = (df["volume"] - df["volume"].rolling(24).mean()) / (df["volume"].rolling(24).std() + 1e-9)

    # --- технические фичи ---
    # RSI(14)
    df["rsi_14"] = _rsi(df["close"], window=14)

    # Bollinger Bands (20, 2)
    mid, upper, lower = _bbands(df["close"], window=20, nstd=2.0)
    df["bb_width_20_2"] = (
        ((upper - lower) / mid.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).clip(lower=-10, upper=10)
    )
    df["bb_pct_20_2"] = ((df["close"] - lower) / (upper - lower)).clip(0, 1)
    
    # MACD (12, 26, 9)
    macd_line, signal_line, macd_hist = _macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = macd_hist
    
    # ATR (14) - волатильность
    df["atr_14"] = _atr(df["high"], df["low"], df["close"], window=14)
    df["atr_pct"] = df["atr_14"] / df["close"]  # Нормализованная ATR
    
    # ADX (14) - сила тренда
    df["adx_14"] = _adx(df["high"], df["low"], df["close"], window=14)
    
    # Stochastic Oscillator (14, 3)
    stoch_k, stoch_d = _stochastic(df["high"], df["low"], df["close"], k_window=14, d_window=3)
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d
    
    # Williams %R (14)
    df["williams_r"] = _williams_r(df["high"], df["low"], df["close"], window=14)
    
    # CCI (20)
    df["cci_20"] = _cci(df["high"], df["low"], df["close"], window=20)
    
    # EMA crossovers (дополнительные фичи для трендов)
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_cross_9_21"] = (df["ema_9"] - df["ema_21"]) / df["close"]  # Normalized
    df["ema_cross_21_50"] = (df["ema_21"] - df["ema_50"]) / df["close"]  # Normalized

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

    # --- on-chain метрики ---
    # Получаем последние значения (обновляются раз в день для всех строк)
    try:
        asset = symbol.split("/")[0] if "/" in symbol else "BTC"
        onchain_feats = get_onchain_features(asset)  # Новый бесплатный API!
        for key, value in onchain_feats.items():
            df[key] = value
    except Exception as e:
        print(f"[OnChain] Warning: {e}")
        # Placeholder values если API недоступен
        # Новые on-chain фичи (CoinGecko + Blockchain.info + CoinGlass)
        onchain_keys = [
            "onchain_market_cap", "onchain_volume_24h", "onchain_circulating_supply",
            "onchain_price_change_24h", "onchain_price_change_7d", "onchain_price_change_30d",
            "onchain_hash_rate", "onchain_difficulty", "onchain_tx_count_24h",
            "onchain_funding_rate", "onchain_liquidations_24h",
            "onchain_long_liquidations", "onchain_short_liquidations"
        ]
        for key in onchain_keys:
            df[key] = 0.0
    
    # --- макроэкономические данные ---
    try:
        macro_feats = get_macro_features()
        for key, value in macro_feats.items():
            df[key] = value
    except Exception as e:
        print(f"[Macro] Warning: {e}")
        # Новые macro фичи (Fear & Greed + Yahoo Finance)
        macro_keys = [
            "macro_fear_greed", "macro_fear_greed_norm", "macro_dxy",
            "macro_gold_price", "macro_oil_price", "macro_fed_rate",
            "macro_treasury_10y", "macro_treasury_2y", "macro_yield_spread"
        ]
        for key in macro_keys:
            df[key] = 0.0
    
    # --- social signals ---
    try:
        social_feats = get_social_features()
        for key, value in social_feats.items():
            df[key] = value
    except Exception as e:
        print(f"[Social] Warning: {e}")
        # Новые social фичи (Reddit public JSON + Google Trends)
        social_keys = [
            "social_reddit_posts", "social_reddit_sentiment", "social_reddit_avg_score",
            "social_google_trends", "social_twitter_mentions", "social_twitter_sentiment"
        ]
        for key in social_keys:
            df[key] = 0.0

    # --- LAG FEATURES (критично для временных рядов!) ---
    # Лаги основных индикаторов
    df["ret_1_lag1"] = df["ret_1"].shift(1)
    df["ret_1_lag2"] = df["ret_1"].shift(2)
    df["ret_1_lag4"] = df["ret_1"].shift(4)
    df["ret_1_lag24"] = df["ret_1"].shift(24)
    
    df["rsi_14_lag1"] = df["rsi_14"].shift(1)
    df["rsi_14_lag4"] = df["rsi_14"].shift(4)
    
    df["bb_pct_20_2_lag1"] = df["bb_pct_20_2"].shift(1)
    df["vol_norm_lag1"] = df["vol_norm"].shift(1)
    df["vol_norm_lag4"] = df["vol_norm"].shift(4)
    
    # Momentum features (изменение за период)
    df["ret_momentum_4"] = df["ret_1"].rolling(4).sum()
    df["ret_momentum_12"] = df["ret_1"].rolling(12).sum()
    df["rsi_change_4"] = df["rsi_14"] - df["rsi_14"].shift(4)
    
    # --- TIME FEATURES (цикличность) ---
    # Извлекаем временные компоненты из индекса
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek  # 0=Monday, 6=Sunday
    df["day_of_month"] = df.index.day
    df["month"] = df.index.month
    
    # Циклическое кодирование (sin/cos) для hour и day_of_week
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    
    # Бинарные флаги
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_month_start"] = (df["day_of_month"] <= 7).astype(int)
    df["is_month_end"] = (df["day_of_month"] >= 24).astype(int)
    
    # --- ДОПОЛНИТЕЛЬНЫЕ ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ ---
    # Volume-weighted indicators
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / (df["volume_sma_20"] + 1e-9)
    
    # Price action
    df["high_low_ratio"] = df["high"] / (df["low"] + 1e-9)
    df["close_open_ratio"] = df["close"] / (df["open"] + 1e-9)
    
    # Volatility expansion/contraction
    df["atr_change"] = df["atr_14"] - df["atr_14"].shift(4)
    df["bb_width_change"] = df["bb_width_20_2"] - df["bb_width_20_2"].shift(4)
    
    # Trend strength
    df["ema_distance"] = (df["close"] - df["ema_50"]) / (df["ema_50"] + 1e-9)
    df["ema_slope_21"] = (df["ema_21"] - df["ema_21"].shift(4)) / (df["ema_21"].shift(4) + 1e-9)
    
    # Mean reversion indicators
    df["price_to_sma_20"] = df["close"] / (df["close"].rolling(20).mean() + 1e-9)
    df["rsi_overbought"] = (df["rsi_14"] > 70).astype(int)
    df["rsi_oversold"] = (df["rsi_14"] < 30).astype(int)

    # --- целевая переменная ---
    df["future_ret"] = df["close"].shift(-horizon_steps) / df["close"] - 1.0
    df["y"] = (df["future_ret"] > 0).astype(int)

    # список колонок-фич (РАСШИРЕННЫЙ до 110+!)
    feature_cols = (
        [
            # Ценовые фичи (базовые)
            "ret_1", "ret_3", "ret_6", "ret_12", "ret_24", "vol_norm",
            # Lag features (14 новых)
            "ret_1_lag1", "ret_1_lag2", "ret_1_lag4", "ret_1_lag24",
            "rsi_14_lag1", "rsi_14_lag4",
            "bb_pct_20_2_lag1", "vol_norm_lag1", "vol_norm_lag4",
            "ret_momentum_4", "ret_momentum_12", "rsi_change_4",
            # Time features (12 новых)
            "hour", "day_of_week", "day_of_month", "month",
            "hour_sin", "hour_cos", "dow_sin", "dow_cos",
            "is_weekend", "is_month_start", "is_month_end",
            # Технические индикаторы (базовые)
            "rsi_14", "bb_pct_20_2", "bb_width_20_2",
            "macd", "macd_signal", "macd_hist",
            "atr_14", "atr_pct", "adx_14",
            "stoch_k", "stoch_d", "williams_r", "cci_20",
            "ema_9", "ema_21", "ema_50", "ema_cross_9_21", "ema_cross_21_50",
            # Дополнительные технические (12 новых)
            "volume_sma_20", "volume_ratio",
            "high_low_ratio", "close_open_ratio",
            "atr_change", "bb_width_change",
            "ema_distance", "ema_slope_21",
            "price_to_sma_20", "rsi_overbought", "rsi_oversold",
            # Новостные фичи
            "news_cnt_6", "news_cnt_24", "sent_mean_6", "sent_mean_24",
        ]
        + [f"tag_{t}_{6}" for t in TAGS]
        + [f"tag_{t}_{24}" for t in TAGS]
        # On-chain фичи (CoinGecko + Blockchain.info + CoinGlass)
        + [
            "onchain_market_cap", "onchain_volume_24h", "onchain_circulating_supply",
            "onchain_price_change_24h", "onchain_price_change_7d", "onchain_price_change_30d",
            "onchain_hash_rate", "onchain_difficulty", "onchain_tx_count_24h",
            "onchain_funding_rate", "onchain_liquidations_24h",
            "onchain_long_liquidations", "onchain_short_liquidations",
        ]
        # Макро фичи (Fear & Greed + Yahoo Finance)
        + [
            "macro_fear_greed", "macro_fear_greed_norm", "macro_dxy",
            "macro_gold_price", "macro_oil_price", "macro_fed_rate",
            "macro_treasury_10y", "macro_treasury_2y", "macro_yield_spread",
        ]
        # Social фичи (Reddit public JSON + Google Trends)
        + [
            "social_reddit_posts", "social_reddit_sentiment", "social_reddit_avg_score",
            "social_google_trends", "social_twitter_mentions", "social_twitter_sentiment",
        ]
    )

    # Добавляем колонку timestamp ПЕРЕД dropna (из индекса)
    df = df.reset_index()
    df = df.rename(columns={"dt": "timestamp"})
    
    # Теперь dropna (timestamp уже не индекс, не будет потерян)
    df = df.dropna(subset=feature_cols + ["future_ret", "y"])
    
    # Устанавливаем timestamp обратно как индекс (важно для работы с временными рядами)
    df = df.set_index("timestamp")
    
    print(f"[Features] Dataset built: {len(df)} rows x {len(feature_cols)} features")
    print(f"[Features] Base: 6 price, Lag: 12, Time: 11, Technical: 37, News: {2 + len(TAGS)*2}, OnChain: 13, Macro: 9, Social: 6")
    print(f"[Features] Total dynamic features: ~65, Total features: {len(feature_cols)}")
    return df, feature_cols


def build_dataset_for_rl(
    prices_df: pd.DataFrame,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """
    Построение датасета для RL-окружения (без целевой переменной).
    
    Args:
        prices_df: DataFrame с OHLCV (колонки: open, high, low, close, volume, timestamp)
        exchange: Биржа (для логирования)
        symbol: Символ (для логирования)
        timeframe: Таймфрейм (для логирования)
    
    Returns:
        DataFrame с фичами (close + все технические/новостные/onchain/macro/social)
    """
    print(f"[RL] Building dataset for {exchange} {symbol} {timeframe}")
    
    # Используем build_dataset с фиктивной БД (None)
    # Но поскольку build_dataset требует БД, создадим упрощённую версию
    
    df = prices_df.copy()
    
    # Проверка обязательных колонок
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Установка timestamp как индекс
    if "timestamp" in df.columns and df.index.name != "timestamp":
        df = df.set_index("timestamp")
    
    # --- Ценовые фичи ---
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["ret_12"] = df["close"].pct_change(12)
    df["ret_24"] = df["close"].pct_change(24)
    df["vol_norm"] = df["volume"] / df["volume"].rolling(24).mean()
    
    # --- Технические индикаторы ---
    df["rsi_14"] = _rsi(df["close"], 14)
    mid, upper, lower = _bbands(df["close"], 20, 2.0)
    df["bb_pct_20_2"] = (df["close"] - lower) / (upper - lower)
    df["bb_width_20_2"] = (upper - lower) / mid
    
    macd, macd_signal, macd_hist = _macd(df["close"])
    df["macd"] = macd
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist
    
    df["atr_14"] = _atr(df["high"], df["low"], df["close"], 14)
    df["atr_pct"] = df["atr_14"] / df["close"]
    df["adx_14"] = _adx(df["high"], df["low"], df["close"], 14)
    
    stoch_k, stoch_d = _stochastic(df["high"], df["low"], df["close"])
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d
    
    df["williams_r"] = _williams_r(df["high"], df["low"], df["close"])
    df["cci_20"] = _cci(df["high"], df["low"], df["close"])
    
    df["ema_9"] = df["close"].ewm(span=9).mean()
    df["ema_21"] = df["close"].ewm(span=21).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()
    df["ema_cross_9_21"] = (df["ema_9"] > df["ema_21"]).astype(float)
    df["ema_cross_21_50"] = (df["ema_21"] > df["ema_50"]).astype(float)
    
    # --- Новостные фичи (заглушки, т.к. нет БД) ---
    df["news_cnt_6"] = 0.0
    df["news_cnt_24"] = 0.0
    df["sent_mean_6"] = 0.0
    df["sent_mean_24"] = 0.0
    
    for tag in TAGS:
        df[f"tag_{tag}_6"] = 0.0
        df[f"tag_{tag}_24"] = 0.0
    
    # --- On-chain фичи (заглушки, опционально можно загружать) ---
    # Новые on-chain фичи (CoinGecko + Blockchain.info + CoinGlass)
    onchain_keys = [
        "onchain_market_cap", "onchain_volume_24h", "onchain_circulating_supply",
        "onchain_price_change_24h", "onchain_price_change_7d", "onchain_price_change_30d",
        "onchain_hash_rate", "onchain_difficulty", "onchain_tx_count_24h",
        "onchain_funding_rate", "onchain_liquidations_24h",
        "onchain_long_liquidations", "onchain_short_liquidations",
    ]
    for key in onchain_keys:
        df[key] = 0.0
    
    # --- Макро фичи (заглушки) ---
    # Новые macro фичи (Fear & Greed + Yahoo Finance)
    macro_keys = [
        "macro_fear_greed", "macro_fear_greed_norm", "macro_dxy",
        "macro_gold_price", "macro_oil_price", "macro_fed_rate",
        "macro_treasury_10y", "macro_treasury_2y", "macro_yield_spread",
    ]
    for key in macro_keys:
        df[key] = 0.0
    
    # --- Social фичи (заглушки) ---
    # Новые social фичи (Reddit public JSON + Google Trends)
    social_keys = [
        "social_reddit_posts", "social_reddit_sentiment", "social_reddit_avg_score",
        "social_google_trends", "social_twitter_mentions", "social_twitter_sentiment",
    ]
    for key in social_keys:
        df[key] = 0.0
    
    # Удаление NaN (из-за pct_change, EMA и т.д.)
    df = df.dropna()
    
    print(f"[RL] Dataset ready: {len(df)} rows, {len(df.columns)} columns")
    
    return df