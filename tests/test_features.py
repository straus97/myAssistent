"""
Тесты для src/features.py (генерация фичей и датасета).
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, MagicMock
from src.features import (
    _rsi,
    _bbands,
    load_prices_df,
    load_news_df,
    build_dataset,
    PANDAS_FREQ,
    TAGS,
)


# --- Fixtures ---


@pytest.fixture
def mock_db_session():
    """Создаёт мок для SQLAlchemy Session."""
    return Mock()


@pytest.fixture
def sample_prices():
    """Генерирует тестовые OHLCV данные."""
    np.random.seed(42)
    n = 200
    ts_start = pd.Timestamp("2023-01-01", tz="UTC")
    timestamps = [int((ts_start + pd.Timedelta(hours=i)).timestamp() * 1000) for i in range(n)]

    close = 50000.0
    data = []
    for ts in timestamps:
        open_price = close + np.random.randn() * 100
        high = max(open_price, close) + abs(np.random.randn()) * 50
        low = min(open_price, close) - abs(np.random.randn()) * 50
        volume = np.random.uniform(1000, 5000)

        data.append({
            "ts": ts,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
        close += np.random.randn() * 200

    return data


@pytest.fixture
def sample_news():
    """Генерирует тестовые новости."""
    ts_start = pd.Timestamp("2023-01-01", tz="UTC")
    data = []
    for i in range(50):
        dt = ts_start + pd.Timedelta(hours=i * 2)
        sentiment = np.random.uniform(-1, 1)
        tags = np.random.choice(["btc", "eth", "regulation", "hack"], size=2, replace=False)
        data.append({
            "dt": dt,
            "sentiment": sentiment,
            "tags": " ".join(tags),
        })
    return data


# --- Тесты _rsi ---


def test_rsi_basic():
    """Проверяет базовый расчёт RSI."""
    prices = pd.Series([50, 51, 52, 51, 53, 54, 53, 55, 54, 56, 57, 56, 58, 57, 59, 60, 59, 61, 60, 62])
    rsi = _rsi(prices, window=14)

    # RSI должен быть в диапазоне 0..100
    assert (rsi >= 0).all() and (rsi <= 100).all()
    # Первые значения могут быть NaN или 0
    assert len(rsi) == len(prices)


def test_rsi_constant_prices():
    """Проверяет RSI при постоянных ценах (RS=0)."""
    prices = pd.Series([100.0] * 20)
    rsi = _rsi(prices, window=14)

    # При постоянных ценах RSI должен быть 0 (или близко к 0)
    assert all(rsi.fillna(0) <= 1)


def test_rsi_uptrend():
    """Проверяет RSI при сильном восходящем тренде."""
    prices = pd.Series(range(50, 100))  # постоянный рост
    rsi = _rsi(prices, window=14)

    # RSI должен быть высоким (>70) при сильном росте
    assert rsi.iloc[-1] > 70


def test_rsi_downtrend():
    """Проверяет RSI при сильном нисходящем тренде."""
    prices = pd.Series(range(100, 50, -1))  # постоянное падение
    rsi = _rsi(prices, window=14)

    # RSI должен быть низким (<30) при сильном падении
    assert rsi.iloc[-1] < 30


def test_rsi_window_parameter():
    """Проверяет работу RSI с разными window."""
    prices = pd.Series([50 + i * 0.5 + np.random.randn() for i in range(50)])
    rsi_14 = _rsi(prices, window=14)
    rsi_20 = _rsi(prices, window=20)

    assert len(rsi_14) == len(prices)
    assert len(rsi_20) == len(prices)
    # Значения могут отличаться
    assert not rsi_14.equals(rsi_20)


# --- Тесты _bbands ---


def test_bbands_basic():
    """Проверяет базовый расчёт Bollinger Bands."""
    prices = pd.Series([100 + np.random.randn() * 2 for _ in range(50)])
    mid, upper, lower = _bbands(prices, window=20, nstd=2.0)

    assert len(mid) == len(prices)
    assert len(upper) == len(prices)
    assert len(lower) == len(prices)

    # Upper > Mid > Lower (там где не NaN)
    valid_mask = ~(mid.isna() | upper.isna() | lower.isna())
    assert (upper[valid_mask] >= mid[valid_mask]).all()
    assert (mid[valid_mask] >= lower[valid_mask]).all()


def test_bbands_constant_prices():
    """Проверяет BB при постоянных ценах (std=0)."""
    prices = pd.Series([100.0] * 50)
    mid, upper, lower = _bbands(prices, window=20, nstd=2.0)

    # При std=0 все полосы должны совпадать с ценой
    valid_mask = ~mid.isna()
    assert (mid[valid_mask] == 100.0).all()
    assert (upper[valid_mask] == 100.0).all()
    assert (lower[valid_mask] == 100.0).all()


def test_bbands_window_parameter():
    """Проверяет BB с разными окнами."""
    prices = pd.Series([100 + np.random.randn() * 5 for _ in range(100)])
    mid_20, upper_20, lower_20 = _bbands(prices, window=20, nstd=2.0)
    mid_10, upper_10, lower_10 = _bbands(prices, window=10, nstd=2.0)

    # Меньшее окно должно быстрее реагировать
    assert not mid_20.equals(mid_10)


def test_bbands_nstd_parameter():
    """Проверяет BB с разными nstd."""
    prices = pd.Series([100 + np.random.randn() * 5 for _ in range(50)])
    mid, upper_2, lower_2 = _bbands(prices, window=20, nstd=2.0)
    _, upper_3, lower_3 = _bbands(prices, window=20, nstd=3.0)

    # Больший nstd → шире полосы
    valid_mask = ~upper_2.isna()
    assert (upper_3[valid_mask] >= upper_2[valid_mask]).all()
    assert (lower_3[valid_mask] <= lower_2[valid_mask]).all()


# --- Тесты load_prices_df ---


def test_load_prices_df(mock_db_session, sample_prices):
    """Проверяет загрузку OHLCV данных из БД."""
    # Мокаем результаты запроса
    mock_rows = []
    for row in sample_prices:
        mock_row = Mock()
        mock_row.ts = row["ts"]
        mock_row.open = row["open"]
        mock_row.high = row["high"]
        mock_row.low = row["low"]
        mock_row.close = row["close"]
        mock_row.volume = row["volume"]
        mock_rows.append(mock_row)

    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.all.return_value = mock_rows
    mock_db_session.query.return_value = query_mock

    df = load_prices_df(mock_db_session, "binance", "BTC/USDT", "1h")

    assert len(df) == len(sample_prices)
    assert "open" in df.columns
    assert "close" in df.columns
    assert "volume" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None  # UTC


def test_load_prices_df_empty(mock_db_session):
    """Проверяет загрузку при отсутствии данных."""
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.all.return_value = []
    mock_db_session.query.return_value = query_mock

    df = load_prices_df(mock_db_session, "binance", "BTC/USDT", "1h")

    assert df.empty


# --- Тесты load_news_df ---


def test_load_news_df(mock_db_session, sample_news):
    """Проверяет загрузку новостей из БД."""
    # Мокаем Article и ArticleAnnotation
    mock_rows = []
    for news in sample_news:
        art = Mock()
        art.published_at = news["dt"]
        ann = Mock()
        ann.sentiment = news["sentiment"]
        ann.tags = news["tags"]
        mock_rows.append((art, ann))

    query_mock = MagicMock()
    query_mock.join.return_value = query_mock
    query_mock.all.return_value = mock_rows
    mock_db_session.query.return_value = query_mock

    df = load_news_df(mock_db_session)

    assert len(df) == len(sample_news)
    assert "sentiment" in df.columns
    assert "news_count" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)

    # Проверяем one-hot теги
    for tag in TAGS:
        assert f"tag_{tag}" in df.columns


def test_load_news_df_empty(mock_db_session):
    """Проверяет загрузку при отсутствии новостей."""
    query_mock = MagicMock()
    query_mock.join.return_value = query_mock
    query_mock.all.return_value = []
    mock_db_session.query.return_value = query_mock

    df = load_news_df(mock_db_session)

    assert df.empty


def test_load_news_df_tag_extraction(mock_db_session):
    """Проверяет извлечение тегов."""
    art = Mock()
    art.published_at = pd.Timestamp("2023-01-01", tz="UTC")
    ann = Mock()
    ann.sentiment = 0.5
    ann.tags = "btc ethereum regulation"

    query_mock = MagicMock()
    query_mock.join.return_value = query_mock
    query_mock.all.return_value = [(art, ann)]
    mock_db_session.query.return_value = query_mock

    df = load_news_df(mock_db_session)

    assert df.iloc[0]["tag_btc"] == 1
    assert df.iloc[0]["tag_eth"] == 1  # ethereum → eth
    assert df.iloc[0]["tag_regulation"] == 1
    assert df.iloc[0]["tag_hack"] == 0


# --- Тесты build_dataset ---


def test_build_dataset(mock_db_session, sample_prices, sample_news):
    """Проверяет полное построение датасета."""
    # Мокаем load_prices_df
    mock_price_rows = []
    for row in sample_prices:
        mock_row = Mock()
        for k, v in row.items():
            setattr(mock_row, k, v)
        mock_price_rows.append(mock_row)

    # Мокаем load_news_df
    mock_news_rows = []
    for news in sample_news:
        art = Mock()
        art.published_at = news["dt"]
        ann = Mock()
        ann.sentiment = news["sentiment"]
        ann.tags = news["tags"]
        mock_news_rows.append((art, ann))

    # Настройка моков для двух разных query
    def query_side_effect(model):
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.join.return_value = query_mock

        # Price query
        if "Price" in str(model):
            query_mock.all.return_value = mock_price_rows
        # Article/Annotation query
        else:
            query_mock.all.return_value = mock_news_rows

        return query_mock

    mock_db_session.query.side_effect = query_side_effect

    df, feature_cols = build_dataset(
        mock_db_session,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        horizon_steps=6
    )

    # Проверяем структуру
    assert len(df) > 0
    assert "y" in df.columns
    assert "future_ret" in df.columns

    # Проверяем фичи
    assert "ret_1" in feature_cols
    assert "ret_3" in feature_cols
    assert "rsi_14" in feature_cols
    assert "bb_pct_20_2" in feature_cols
    assert "bb_width_20_2" in feature_cols
    assert "news_cnt_6" in feature_cols
    assert "sent_mean_24" in feature_cols

    # Проверяем теговые фичи
    for tag in TAGS:
        assert f"tag_{tag}_6" in feature_cols
        assert f"tag_{tag}_24" in feature_cols

    # Проверяем, что нет NaN в финальном датасете
    for col in feature_cols + ["y", "future_ret"]:
        assert not df[col].isna().any()


def test_build_dataset_no_prices(mock_db_session):
    """Проверяет ошибку при отсутствии цен."""
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.all.return_value = []
    mock_db_session.query.return_value = query_mock

    with pytest.raises(ValueError, match="Нет цен в БД"):
        build_dataset(mock_db_session, "binance", "BTC/USDT", "1h")


def test_build_dataset_no_news(mock_db_session, sample_prices):
    """Проверяет построение датасета без новостей."""
    # Только цены, без новостей
    mock_price_rows = []
    for row in sample_prices:
        mock_row = Mock()
        for k, v in row.items():
            setattr(mock_row, k, v)
        mock_price_rows.append(mock_row)

    def query_side_effect(model):
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.join.return_value = query_mock

        if "Price" in str(model):
            query_mock.all.return_value = mock_price_rows
        else:
            query_mock.all.return_value = []  # Нет новостей

        return query_mock

    mock_db_session.query.side_effect = query_side_effect

    df, feature_cols = build_dataset(mock_db_session, "binance", "BTC/USDT", "1h")

    # Должны быть заполнены нулями
    assert df["news_cnt_6"].sum() == 0
    assert df["sent_mean_24"].sum() == 0


def test_build_dataset_different_timeframes():
    """Проверяет поддержку разных таймфреймов."""
    for tf, freq in PANDAS_FREQ.items():
        assert freq in ["1min", "5min", "15min", "1h", "4h", "1D"]


def test_build_dataset_horizon_steps(mock_db_session, sample_prices):
    """Проверяет влияние horizon_steps на future_ret."""
    mock_price_rows = []
    for row in sample_prices:
        mock_row = Mock()
        for k, v in row.items():
            setattr(mock_row, k, v)
        mock_price_rows.append(mock_row)

    def query_side_effect(model):
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.join.return_value = query_mock
        query_mock.all.return_value = mock_price_rows if "Price" in str(model) else []
        return query_mock

    mock_db_session.query.side_effect = query_side_effect

    df_h6, _ = build_dataset(mock_db_session, "binance", "BTC/USDT", "1h", horizon_steps=6)
    df_h12, _ = build_dataset(mock_db_session, "binance", "BTC/USDT", "1h", horizon_steps=12)

    # Разные горизонты → разные future_ret
    assert len(df_h6) != len(df_h12)  # Разное количество строк (из-за shift)


# --- Тесты feature engineering ---


def test_feature_ret_calculation():
    """Проверяет расчёт ret_1, ret_3, ret_6, ret_12."""
    prices = pd.Series([100, 102, 101, 103, 104, 105, 106, 107, 108, 109, 110])
    ret_1 = prices.pct_change(1)
    ret_3 = prices.pct_change(3)

    assert len(ret_1) == len(prices)
    assert len(ret_3) == len(prices)
    assert abs(ret_1.iloc[1] - 0.02) < 1e-6  # (102-100)/100


def test_feature_vol_norm():
    """Проверяет нормализацию объёма."""
    volumes = pd.Series([1000, 1100, 1200, 1300, 1400, 1500] * 10)
    vol_mean = volumes.rolling(24).mean()
    vol_std = volumes.rolling(24).std()
    vol_norm = (volumes - vol_mean) / (vol_std + 1e-9)

    assert len(vol_norm) == len(volumes)
    # После нормализации среднее должно быть близко к 0
    assert abs(vol_norm.iloc[30:].mean()) < 0.5


def test_feature_bb_pct():
    """Проверяет расчёт bb_pct (положение в полосах)."""
    prices = pd.Series([100 + np.random.randn() * 2 for _ in range(50)])
    mid, upper, lower = _bbands(prices, window=20, nstd=2.0)
    bb_pct = ((prices - lower) / (upper - lower)).clip(0, 1)

    valid_mask = ~bb_pct.isna()
    assert (bb_pct[valid_mask] >= 0).all()
    assert (bb_pct[valid_mask] <= 1).all()


def test_feature_bb_width():
    """Проверяет расчёт bb_width (относительная ширина полос)."""
    prices = pd.Series([100 + np.random.randn() * 5 for _ in range(50)])
    mid, upper, lower = _bbands(prices, window=20, nstd=2.0)
    bb_width = ((upper - lower) / mid.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).clip(-10, 10)

    valid_mask = ~bb_width.isna()
    assert (bb_width[valid_mask] >= -10).all()
    assert (bb_width[valid_mask] <= 10).all()


# --- Тесты целевой переменной ---


def test_target_variable_y():
    """Проверяет бинаризацию целевой переменной."""
    future_ret = pd.Series([0.01, -0.02, 0.03, -0.01, 0.0, 0.05])
    y = (future_ret > 0).astype(int)

    assert list(y) == [1, 0, 1, 0, 0, 1]


def test_target_future_ret_shift():
    """Проверяет расчёт future_ret через shift."""
    close = pd.Series([100, 102, 101, 103, 104])
    future_ret = close.shift(-2) / close - 1.0

    # future_ret[0] = (101 - 100) / 100 = 0.01
    # future_ret[1] = (103 - 102) / 102 ≈ 0.0098
    # future_ret[-2:] = NaN

    assert abs(future_ret.iloc[0] - 0.01) < 1e-6
    assert future_ret.isna().iloc[-2:].all()

