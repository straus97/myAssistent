"""
Тесты для src/risk.py (фильтры сигналов, волатильность, guard).
"""
import pytest
import tempfile
import shutil
import json
from pathlib import Path
import pandas as pd
import numpy as np
from src.risk import (
    CFG_DIR,
    POLICY_PATH,
    DEFAULT_POLICY,
    load_policy,
    save_policy,
    _ema,
    evaluate_filters,
)


# --- Fixtures ---


@pytest.fixture
def temp_config_dir():
    """Создаёт временную директорию для конфигов."""
    tmp_dir = tempfile.mkdtemp()
    tmp_cfg = Path(tmp_dir) / "config"
    tmp_cfg.mkdir(parents=True, exist_ok=True)

    # Патчим CFG_DIR и POLICY_PATH
    import src.risk as risk_module
    original_cfg_dir = risk_module.CFG_DIR
    original_policy_path = risk_module.POLICY_PATH

    risk_module.CFG_DIR = tmp_cfg
    risk_module.POLICY_PATH = tmp_cfg / "policy.json"

    yield tmp_cfg

    # Восстанавливаем и удаляем
    risk_module.CFG_DIR = original_cfg_dir
    risk_module.POLICY_PATH = original_policy_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def clean_policy(temp_config_dir):
    """Обеспечивает чистую policy для каждого теста."""
    policy_path = temp_config_dir / "policy.json"
    if policy_path.exists():
        policy_path.unlink()
    return policy_path


@pytest.fixture
def sample_price_df():
    """Создаёт тестовый датафрейм с OHLCV данными."""
    np.random.seed(42)
    n = 100
    close = 50000.0
    data = []

    for i in range(n):
        open_price = close + np.random.randn() * 100
        high = max(open_price, close) + abs(np.random.randn()) * 50
        low = min(open_price, close) - abs(np.random.randn()) * 50
        volume = np.random.uniform(1000, 5000)

        data.append({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
        close += np.random.randn() * 200

    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=n, freq="1h")
    return df


# --- Тесты load_policy ---


def test_load_policy_creates_default(clean_policy):
    """Проверяет создание дефолтной policy."""
    policy = load_policy()

    assert "min_prob_gap" in policy
    assert "cooldown_minutes" in policy
    assert "volatility_thresholds" in policy
    assert "filters" in policy
    assert clean_policy.exists()


def test_load_policy_existing(clean_policy):
    """Проверяет загрузку существующей policy."""
    custom_policy = {"min_prob_gap": 0.05, "cooldown_minutes": 120}
    clean_policy.write_text(json.dumps(custom_policy), encoding="utf-8")

    policy = load_policy()

    assert policy["min_prob_gap"] == 0.05
    assert policy["cooldown_minutes"] == 120
    # Должны быть дополнены дефолтами
    assert "filters" in policy


def test_load_policy_corrupted_file(clean_policy):
    """Проверяет обработку повреждённого файла."""
    clean_policy.write_text("invalid json {{{", encoding="utf-8")

    policy = load_policy()

    # Должен вернуть дефолтную политику
    assert policy == DEFAULT_POLICY


# --- Тесты save_policy ---


def test_save_policy(clean_policy):
    """Проверяет сохранение policy."""
    custom_policy = {"min_prob_gap": 0.03}
    save_policy(custom_policy)

    assert clean_policy.exists()
    loaded = json.loads(clean_policy.read_text(encoding="utf-8"))
    assert loaded["min_prob_gap"] == 0.03
    # Должны быть добавлены дефолты
    assert "cooldown_minutes" in loaded


def test_save_policy_merge_with_defaults(clean_policy):
    """Проверяет слияние с дефолтами."""
    custom_policy = {"cooldown_minutes": 60}
    save_policy(custom_policy)

    loaded = json.loads(clean_policy.read_text(encoding="utf-8"))
    assert loaded["cooldown_minutes"] == 60
    assert loaded["min_prob_gap"] == DEFAULT_POLICY["min_prob_gap"]


# --- Тесты _ema ---


def test_ema_basic():
    """Проверяет базовый расчёт EMA."""
    prices = pd.Series([100, 102, 101, 103, 104, 105, 106, 107, 108, 109])
    ema = _ema(prices, span=5)

    assert len(ema) == len(prices)
    # EMA должен сглаживать колебания
    assert not ema.isna().all()


def test_ema_uptrend():
    """Проверяет EMA на восходящем тренде."""
    prices = pd.Series(range(100, 150))  # рост
    ema_fast = _ema(prices, span=10)
    ema_slow = _ema(prices, span=20)

    # Fast EMA должна быть выше Slow EMA на восходящем тренде
    assert ema_fast.iloc[-1] > ema_slow.iloc[-1]


def test_ema_downtrend():
    """Проверяет EMA на нисходящем тренде."""
    prices = pd.Series(range(150, 100, -1))  # падение
    ema_fast = _ema(prices, span=10)
    ema_slow = _ema(prices, span=20)

    # Fast EMA должна быть ниже Slow EMA на нисходящем тренде
    assert ema_fast.iloc[-1] < ema_slow.iloc[-1]


def test_ema_constant_prices():
    """Проверяет EMA при постоянных ценах."""
    prices = pd.Series([100.0] * 50)
    ema = _ema(prices, span=20)

    # EMA должна равняться цене
    valid_mask = ~ema.isna()
    assert (ema[valid_mask] == 100.0).all()


def test_ema_span_parameter():
    """Проверяет влияние параметра span."""
    prices = pd.Series([100 + np.random.randn() * 5 for _ in range(100)])
    ema_10 = _ema(prices, span=10)
    ema_50 = _ema(prices, span=50)

    # Разные span → разные значения
    assert not ema_10.equals(ema_50)
    # Меньший span → быстрее реагирует
    # Проверим, что ema_10 имеет меньше NaN в начале
    assert ema_10.isna().sum() < ema_50.isna().sum()


# --- Тесты evaluate_filters ---


def test_evaluate_filters_all_pass(sample_price_df, clean_policy):
    """Проверяет прохождение всех фильтров."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["min_rel_volume"] = 0.0  # отключаем
    policy["filters"]["max_bar_change"] = 1.0  # отключаем
    policy["filters"]["require_uptrend"] = False

    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    assert allow is True
    assert len(reasons) == 0
    assert "volume" in metrics
    assert "bar_change" in metrics
    assert "ema_fast" in metrics
    assert "trend_up" in metrics


def test_evaluate_filters_low_volume(sample_price_df, clean_policy):
    """Проверяет фильтр низкого объёма."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["min_rel_volume"] = 100.0  # очень высокий порог

    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    assert allow is False
    assert any("low_volume_rel" in r for r in reasons)
    assert "volume_rel" in metrics


def test_evaluate_filters_bar_too_large(sample_price_df, clean_policy):
    """Проверяет фильтр перегретого бара."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["max_bar_change"] = 0.001  # очень малый порог

    # Создаём сильное движение
    df_modified = sample_price_df.copy()
    df_modified.iloc[-1, df_modified.columns.get_loc("close")] = df_modified.iloc[-1]["open"] * 1.05  # +5%

    row = df_modified.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, df_modified, policy, "1h", row.name)

    assert allow is False
    assert any("bar_too_large" in r for r in reasons)
    assert abs(metrics["bar_change"]) > 0.001


def test_evaluate_filters_no_uptrend(sample_price_df, clean_policy):
    """Проверяет фильтр отсутствия uptrend."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["require_uptrend"] = True

    # Создаём downtrend
    df_down = pd.DataFrame({
        "close": range(100, 50, -1),  # падение
        "volume": [1000] * 50,
        "open": range(101, 51, -1),
    })
    df_down.index = pd.date_range("2023-01-01", periods=50, freq="1h")

    row = df_down.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, df_down, policy, "1h", row.name)

    assert allow is False
    assert "no_uptrend" in reasons
    assert metrics["trend_up"] is False


def test_evaluate_filters_uptrend_pass(sample_price_df, clean_policy):
    """Проверяет прохождение фильтра uptrend."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["require_uptrend"] = True
    policy["filters"]["min_rel_volume"] = 0.0
    policy["filters"]["max_bar_change"] = 1.0

    # Создаём явный uptrend
    df_up = pd.DataFrame({
        "close": range(50, 150),  # рост
        "volume": [1000] * 100,
        "open": range(49, 149),
    })
    df_up.index = pd.date_range("2023-01-01", periods=100, freq="1h")

    row = df_up.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, df_up, policy, "1h", row.name)

    assert allow is True
    assert metrics["trend_up"] is True


def test_evaluate_filters_multiple_reasons(sample_price_df, clean_policy):
    """Проверяет накопление нескольких причин отказа."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["min_rel_volume"] = 100.0  # fail
    policy["filters"]["max_bar_change"] = 0.001  # fail
    policy["filters"]["require_uptrend"] = True  # может fail

    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    assert allow is False
    assert len(reasons) >= 1  # Хотя бы одна причина


def test_evaluate_filters_metrics_structure(sample_price_df, clean_policy):
    """Проверяет структуру возвращаемых метрик."""
    policy = DEFAULT_POLICY.copy()
    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    # Обязательные поля
    assert "volume" in metrics
    assert "volume_mean50" in metrics
    assert "volume_rel" in metrics
    assert "bar_change" in metrics
    assert "ema_fast" in metrics
    assert "ema_slow" in metrics
    assert "trend_up" in metrics

    # Типы
    assert isinstance(metrics["volume"], (int, float))
    assert isinstance(metrics["bar_change"], (int, float))
    assert isinstance(metrics["trend_up"], bool)


def test_evaluate_filters_custom_ema_params(sample_price_df, clean_policy):
    """Проверяет кастомные параметры EMA."""
    policy = DEFAULT_POLICY.copy()
    policy["filters"]["ema_fast"] = 10
    policy["filters"]["ema_slow"] = 30

    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    # Должны использоваться кастомные значения
    assert "ema_fast" in metrics
    assert "ema_slow" in metrics


# --- Тесты волатильности (из DEFAULT_POLICY) ---


def test_volatility_thresholds_structure():
    """Проверяет структуру порогов волатильности."""
    thresholds = DEFAULT_POLICY["volatility_thresholds"]

    for tf in ["15m", "1h", "4h", "1d"]:
        assert tf in thresholds
        assert "dead" in thresholds[tf]
        assert "hot" in thresholds[tf]
        # dead < hot
        assert thresholds[tf]["dead"] < thresholds[tf]["hot"]


def test_volatility_thresholds_scaling():
    """Проверяет масштабирование порогов по таймфреймам."""
    thresholds = DEFAULT_POLICY["volatility_thresholds"]

    # Большие таймфреймы → большие пороги
    assert thresholds["15m"]["hot"] < thresholds["1h"]["hot"]
    assert thresholds["1h"]["hot"] < thresholds["4h"]["hot"]
    assert thresholds["4h"]["hot"] < thresholds["1d"]["hot"]


# --- Тесты auto/notify/monitor настроек ---


def test_auto_settings_structure():
    """Проверяет структуру auto настроек."""
    auto = DEFAULT_POLICY["auto"]

    assert "trade_on_buy" in auto
    assert "close_on_strong_flat" in auto
    assert "buy_fraction" in auto
    assert "max_positions_per_symbol" in auto

    # buy_fraction по vol states
    buy_frac = auto["buy_fraction"]
    assert "dead" in buy_frac
    assert "normal" in buy_frac
    assert "hot" in buy_frac


def test_notify_settings_structure():
    """Проверяет структуру notify настроек."""
    notify = DEFAULT_POLICY["notify"]

    assert "on_buy" in notify
    assert "radar" in notify
    assert "radar_gap" in notify
    assert isinstance(notify["on_buy"], bool)


def test_monitor_settings_structure():
    """Проверяет структуру monitor настроек."""
    monitor = DEFAULT_POLICY["monitor"]

    assert "enabled" in monitor
    assert "flat_after" in monitor
    assert "partial_at" in monitor
    assert "partial_size" in monitor
    assert "timeframe" in monitor

    # Логические проверки
    assert monitor["flat_after"] < 0  # убыток
    assert monitor["partial_at"] > 0  # прибыль
    assert 0 < monitor["partial_size"] < 1  # доля


def test_news_radar_settings_structure():
    """Проверяет структуру news_radar настроек."""
    radar = DEFAULT_POLICY["news_radar"]

    assert "enabled" in radar
    assert "window_minutes" in radar
    assert "lookback_windows" in radar
    assert "min_new" in radar
    assert "min_ratio_vs_prev" in radar
    assert "min_unique_sources" in radar
    assert "symbols" in radar
    assert "cooldown_minutes" in radar

    # symbols должен быть словарём
    assert isinstance(radar["symbols"], dict)
    assert "BTC/USDT" in radar["symbols"]


# --- Тесты filters настроек ---


def test_filters_settings_structure():
    """Проверяет структуру filters настроек."""
    filters = DEFAULT_POLICY["filters"]

    assert "min_rel_volume" in filters
    assert "max_bar_change" in filters
    assert "ema_fast" in filters
    assert "ema_slow" in filters
    assert "require_uptrend" in filters

    # Типы
    assert isinstance(filters["min_rel_volume"], (int, float))
    assert isinstance(filters["max_bar_change"], (int, float))
    assert isinstance(filters["ema_fast"], int)
    assert isinstance(filters["ema_slow"], int)
    assert isinstance(filters["require_uptrend"], bool)

    # Логика
    assert filters["ema_fast"] < filters["ema_slow"]


# --- Интеграционные тесты ---


def test_policy_round_trip(clean_policy):
    """Интеграционный тест: save -> load -> verify."""
    custom_policy = {
        "min_prob_gap": 0.04,
        "cooldown_minutes": 180,
        "volatility_thresholds": {
            "1h": {"dead": 0.005, "hot": 0.025},
        },
    }

    save_policy(custom_policy)
    loaded = load_policy()

    assert loaded["min_prob_gap"] == 0.04
    assert loaded["cooldown_minutes"] == 180
    assert loaded["volatility_thresholds"]["1h"]["dead"] == 0.005


def test_evaluate_filters_with_real_policy(sample_price_df, clean_policy):
    """Интеграционный тест: load_policy -> evaluate_filters."""
    policy = load_policy()

    row = sample_price_df.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, sample_price_df, policy, "1h", row.name)

    # Должен работать с дефолтной policy
    assert isinstance(allow, bool)
    assert isinstance(reasons, list)
    assert isinstance(metrics, dict)


def test_filters_edge_case_nan_volume(sample_price_df, clean_policy):
    """Граничный случай: NaN в объёме."""
    policy = DEFAULT_POLICY.copy()

    df_nan = sample_price_df.copy()
    df_nan.iloc[-1, df_nan.columns.get_loc("volume")] = float("nan")

    row = df_nan.iloc[-1]
    allow, reasons, metrics = evaluate_filters(row, df_nan, policy, "1h", row.name)

    # Не должен падать, должен обработать NaN
    assert isinstance(allow, bool)
    assert "volume_rel" in metrics


def test_filters_edge_case_zero_price(sample_price_df, clean_policy):
    """Граничный случай: нулевая цена."""
    policy = DEFAULT_POLICY.copy()

    df_zero = sample_price_df.copy()
    df_zero.iloc[-1, df_zero.columns.get_loc("close")] = 0.0

    row = df_zero.iloc[-1]
    # Не должен падать
    try:
        allow, reasons, metrics = evaluate_filters(row, df_zero, policy, "1h", row.name)
        assert isinstance(allow, bool)
    except Exception as e:
        pytest.fail(f"evaluate_filters failed with zero price: {e}")


def test_filters_insufficient_data(clean_policy):
    """Граничный случай: недостаточно данных для расчёта."""
    policy = DEFAULT_POLICY.copy()

    # Всего 5 баров (меньше, чем нужно для EMA 50)
    df_small = pd.DataFrame({
        "close": [100, 101, 102, 103, 104],
        "volume": [1000, 1100, 1200, 1300, 1400],
        "open": [99, 100, 101, 102, 103],
    })
    df_small.index = pd.date_range("2023-01-01", periods=5, freq="1h")

    row = df_small.iloc[-1]
    # Не должен падать, должен обработать недостаток данных
    try:
        allow, reasons, metrics = evaluate_filters(row, df_small, policy, "1h", row.name)
        assert isinstance(allow, bool)
    except Exception as e:
        pytest.fail(f"evaluate_filters failed with insufficient data: {e}")

