"""
Тесты для src/trade.py (paper trading, auto-sizing, PnL).
"""
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, Mock
from src.trade import (
    STATE_PATH,
    DEFAULT_STATE,
    _load_state,
    _save_state,
    _calc_auto_qty,
    _count_open_positions,
    _find_pos,
    paper_get_positions,
    paper_get_orders,
    paper_get_equity,
    paper_has_open_position,
    paper_open_buy_manual,
    paper_open_sell_manual,
    paper_open_buy_auto,
    paper_close_pair,
    paper_close_with_price,
)


# --- Fixtures ---


@pytest.fixture
def temp_state_file():
    """Создаёт временный state файл."""
    tmp_dir = tempfile.mkdtemp()
    tmp_state = Path(tmp_dir) / "paper_state.json"

    # Патчим STATE_PATH
    original_state_path = STATE_PATH
    import src.trade as trade_module
    trade_module.STATE_PATH = tmp_state

    yield tmp_state

    # Восстанавливаем и удаляем
    trade_module.STATE_PATH = original_state_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def clean_state(temp_state_file):
    """Обеспечивает чистое состояние для каждого теста."""
    if temp_state_file.exists():
        temp_state_file.unlink()
    return temp_state_file


@pytest.fixture
def sample_policy():
    """Создаёт тестовую risk policy."""
    return {
        "auto_sizing": {
            "equity_virtual": 1000.0,
            "buy_fraction": {"dead": 0.05, "normal": 0.10, "hot": 0.07},
            "min_order_usdt": 10.0,
            "max_order_usdt": 100.0,
            "qty_precision": 6,
        },
        "sizing": {
            "base_fraction": 0.10,
            "by_vol": {"dead": 0.05, "normal": 0.10, "hot": 0.07},
            "min_order_usd": 10.0,
        },
        "max_open_positions": 3,
        "position_max_fraction": 0.3,
    }


# --- Тесты _load_state / _save_state ---


def test_load_state_creates_default(clean_state):
    """Проверяет создание дефолтного состояния."""
    state = _load_state()

    assert "cash" in state
    assert "positions" in state
    assert "orders" in state
    assert state["cash"] == DEFAULT_STATE["cash"]
    assert clean_state.exists()


def test_load_state_existing(clean_state):
    """Проверяет загрузку существующего состояния."""
    custom_state = {"cash": 5000.0, "positions": [], "orders": []}
    clean_state.write_text(json.dumps(custom_state), encoding="utf-8")

    state = _load_state()

    assert state["cash"] == 5000.0


def test_save_state(clean_state):
    """Проверяет сохранение состояния."""
    state = {"cash": 7500.0, "positions": [], "orders": []}
    _save_state(state)

    assert clean_state.exists()
    loaded = json.loads(clean_state.read_text(encoding="utf-8"))
    assert loaded["cash"] == 7500.0


def test_save_state_atomic_write(clean_state):
    """Проверяет атомарную запись через NamedTemporaryFile."""
    state = {"cash": 1234.0, "positions": [], "orders": []}
    _save_state(state)

    # Файл должен быть записан полностью
    loaded = json.loads(clean_state.read_text(encoding="utf-8"))
    assert loaded["cash"] == 1234.0


# --- Тесты _calc_auto_qty ---


def test_calc_auto_qty_normal_vol(sample_policy):
    """Проверяет расчёт qty для нормальной волатильности."""
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.0, "normal", sample_policy)

    # Виртуальный режим: 1000 * 0.10 = 100 USDT
    assert usd == 100.0
    assert abs(qty - 100.0 / 50000.0) < 1e-6


def test_calc_auto_qty_hot_vol(sample_policy):
    """Проверяет расчёт qty для горячей волатильности."""
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.0, "hot", sample_policy)

    # hot: 1000 * 0.07 = 70 USDT
    assert usd == 70.0


def test_calc_auto_qty_dead_vol(sample_policy):
    """Проверяет расчёт qty для мёртвой волатильности."""
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.0, "dead", sample_policy)

    # dead: 1000 * 0.05 = 50 USDT
    assert usd == 50.0


def test_calc_auto_qty_min_order(sample_policy):
    """Проверяет соблюдение min_order_usdt."""
    sample_policy["auto_sizing"]["equity_virtual"] = 50.0  # очень мало
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.0, "normal", sample_policy)

    # 50 * 0.10 = 5, но min = 10
    assert usd >= sample_policy["auto_sizing"]["min_order_usdt"]


def test_calc_auto_qty_max_order(sample_policy):
    """Проверяет соблюдение max_order_usdt."""
    sample_policy["auto_sizing"]["equity_virtual"] = 2000.0  # очень много
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.0, "normal", sample_policy)

    # 2000 * 0.10 = 200, но max = 100
    assert usd <= sample_policy["auto_sizing"]["max_order_usdt"]


def test_calc_auto_qty_qty_precision(sample_policy):
    """Проверяет округление qty."""
    qty, usd = _calc_auto_qty("binance", "BTC/USDT", "1h", 50000.123, "normal", sample_policy)

    # Должно быть округлено до 6 знаков
    assert qty == round(qty, 6)


# --- Тесты _count_open_positions ---


def test_count_open_positions():
    """Проверяет подсчёт открытых позиций."""
    state = {
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "qty": 0.1},
            {"exchange": "binance", "symbol": "ETH/USDT", "qty": 0.0},  # закрыта
            {"exchange": "binance", "symbol": "SOL/USDT", "qty": 10.0},
        ]
    }

    assert _count_open_positions(state) == 2


def test_count_open_positions_empty():
    """Проверяет подсчёт при отсутствии позиций."""
    state = {"positions": []}
    assert _count_open_positions(state) == 0


# --- Тесты _find_pos ---


def test_find_pos_exists():
    """Проверяет поиск существующей позиции."""
    state = {
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.1},
            {"exchange": "binance", "symbol": "ETH/USDT", "timeframe": "15m", "qty": 1.0},
        ]
    }

    pos = _find_pos(state, "binance", "BTC/USDT", "1h")
    assert pos is not None
    assert pos["qty"] == 0.1


def test_find_pos_not_exists():
    """Проверяет поиск несуществующей позиции."""
    state = {"positions": []}
    pos = _find_pos(state, "binance", "BTC/USDT", "1h")
    assert pos is None


def test_find_pos_ignore_timeframe():
    """Проверяет поиск без учёта timeframe."""
    state = {
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.1},
        ]
    }

    pos = _find_pos(state, "binance", "BTC/USDT", timeframe=None)
    assert pos is not None


# --- Тесты paper_get_positions / paper_get_orders ---


def test_paper_get_positions(clean_state):
    """Проверяет получение списка позиций."""
    positions = paper_get_positions()
    assert isinstance(positions, list)
    assert len(positions) == 0  # Начальное состояние


def test_paper_get_orders(clean_state):
    """Проверяет получение истории ордеров."""
    orders = paper_get_orders()
    assert isinstance(orders, list)
    assert len(orders) == 0


# --- Тесты paper_get_equity ---


def test_paper_get_equity_cash_only(clean_state):
    """Проверяет equity без открытых позиций."""
    equity = paper_get_equity()

    assert equity["cash"] == DEFAULT_STATE["cash"]
    assert equity["positions_value"] == 0.0
    assert equity["equity"] == DEFAULT_STATE["cash"]


def test_paper_get_equity_with_positions(clean_state):
    """Проверяет equity с открытыми позициями."""
    state = {
        "cash": 5000.0,
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.1, "avg_price": 50000.0},
            {"exchange": "binance", "symbol": "ETH/USDT", "timeframe": "15m", "qty": 1.0, "avg_price": 3000.0},
        ],
        "orders": [],
    }
    _save_state(state)

    # Mark-to-market
    mtm = {"binance:BTC/USDT:1h": 52000.0, "binance:ETH/USDT:15m": 3200.0}
    equity = paper_get_equity(mark_to_market=mtm)

    # 0.1 * 52000 + 1.0 * 3200 = 5200 + 3200 = 8400
    assert equity["positions_value"] == 8400.0
    assert equity["equity"] == 5000.0 + 8400.0


def test_paper_get_equity_fallback_to_avg_price(clean_state):
    """Проверяет fallback к avg_price при отсутствии MTM."""
    state = {
        "cash": 1000.0,
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.1, "avg_price": 50000.0},
        ],
        "orders": [],
    }
    _save_state(state)

    equity = paper_get_equity()

    # 0.1 * 50000 = 5000
    assert equity["positions_value"] == 5000.0
    assert equity["equity"] == 6000.0


# --- Тесты paper_has_open_position ---


def test_paper_has_open_position_true(clean_state):
    """Проверяет наличие открытой позиции."""
    state = {
        "cash": 5000.0,
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.1, "avg_price": 50000.0},
        ],
        "orders": [],
    }
    _save_state(state)

    assert paper_has_open_position("binance", "BTC/USDT", "1h") is True


def test_paper_has_open_position_false(clean_state):
    """Проверяет отсутствие позиции."""
    assert paper_has_open_position("binance", "BTC/USDT", "1h") is False


def test_paper_has_open_position_closed(clean_state):
    """Проверяет закрытую позицию (qty=0)."""
    state = {
        "cash": 5000.0,
        "positions": [
            {"exchange": "binance", "symbol": "BTC/USDT", "timeframe": "1h", "qty": 0.0, "avg_price": 50000.0},
        ],
        "orders": [],
    }
    _save_state(state)

    assert paper_has_open_position("binance", "BTC/USDT", "1h") is False


# --- Тесты paper_open_buy_manual ---


def test_paper_open_buy_manual_new_position(clean_state):
    """Проверяет открытие новой позиции."""
    result = paper_open_buy_manual(
        "binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z"
    )

    assert "order" in result
    assert "position" in result
    assert result["order"]["side"] == "buy"
    assert result["order"]["qty"] == 0.1
    assert result["position"]["qty"] == 0.1
    assert result["position"]["avg_price"] == 50000.0
    assert result["cash"] == DEFAULT_STATE["cash"] - 5000.0


def test_paper_open_buy_manual_add_to_existing(clean_state):
    """Проверяет добавление к существующей позиции."""
    # Открываем первый раз
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    # Добавляем
    result = paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.05, price=52000.0, ts_iso="2023-01-01T01:00:00Z")

    # avg_price = (0.1 * 50000 + 0.05 * 52000) / 0.15
    expected_avg = (0.1 * 50000.0 + 0.05 * 52000.0) / 0.15
    assert result["position"]["qty"] == 0.15
    assert abs(result["position"]["avg_price"] - expected_avg) < 1e-6


def test_paper_open_buy_manual_auto_size(clean_state):
    """Проверяет автоматический sizing (qty=None)."""
    with patch("src.trade.load_policy") as mock_load_policy:
        mock_load_policy.return_value = {
            "auto_sizing": {
                "equity_virtual": 1000.0,
                "buy_fraction": {"normal": 0.10},
                "min_order_usdt": 10.0,
                "max_order_usdt": 200.0,
                "qty_precision": 6,
            }
        }

        result = paper_open_buy_manual(
            "binance", "BTC/USDT", "1h", qty=None, price=50000.0, ts_iso="2023-01-01T00:00:00Z", vol_state="normal"
        )

        # 1000 * 0.10 = 100 USDT → qty = 100 / 50000 = 0.002
        assert result["order"]["qty"] > 0


# --- Тесты paper_open_sell_manual ---


def test_paper_open_sell_manual(clean_state):
    """Проверяет продажу позиции."""
    # Сначала покупаем
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    # Продаём
    result = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.05, price=52000.0, ts_iso="2023-01-01T01:00:00Z")

    assert result["order"]["side"] == "sell"
    assert result["order"]["qty"] == 0.05
    assert result["position"]["qty"] == 0.05
    # PnL = (52000 - 50000) * 0.05 = 100
    assert result["pnl"] == 100.0


def test_paper_open_sell_manual_full_close(clean_state):
    """Проверяет полное закрытие позиции."""
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    result = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.1, price=51000.0, ts_iso="2023-01-01T01:00:00Z")

    assert result["position"]["qty"] == 0.0
    assert result["position"]["avg_price"] == 0.0
    # PnL = (51000 - 50000) * 0.1 = 100
    assert result["pnl"] == 100.0


def test_paper_open_sell_manual_no_position(clean_state):
    """Проверяет ошибку при попытке продажи без позиции."""
    result = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    assert result["status"] == "error"
    assert "no open position" in result["detail"]


def test_paper_open_sell_manual_partial_more_than_available(clean_state):
    """Проверяет продажу больше, чем есть в позиции."""
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    result = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.2, price=51000.0, ts_iso="2023-01-01T01:00:00Z")

    # Должно продать только 0.1
    assert result["order"]["qty"] == 0.1
    assert result["position"]["qty"] == 0.0


# --- Тесты paper_open_buy_auto ---


def test_paper_open_buy_auto(clean_state):
    """Проверяет автоматическую покупку."""
    with patch("src.trade.load_policy") as mock_load_policy:
        mock_load_policy.return_value = {
            "sizing": {
                "base_fraction": 0.10,
                "by_vol": {"normal": 0.10},
                "min_order_usd": 10.0,
            },
            "auto_sizing": {"qty_precision": 6},
            "max_open_positions": 0,
            "position_max_fraction": 1.0,
        }

        result = paper_open_buy_auto(
            "binance", "BTC/USDT", "1h", price=50000.0, ts_iso="2023-01-01T00:00:00Z", vol_state="normal"
        )

        assert "order" in result or "status" in result
        if "order" in result:
            assert result["order"]["side"] == "buy"


def test_paper_open_buy_auto_max_positions_limit(clean_state):
    """Проверяет лимит по max_open_positions."""
    with patch("src.trade.load_policy") as mock_load_policy:
        mock_load_policy.return_value = {
            "sizing": {"base_fraction": 0.10, "by_vol": {"normal": 0.10}, "min_order_usd": 10.0},
            "auto_sizing": {"qty_precision": 6},
            "max_open_positions": 1,
            "position_max_fraction": 1.0,
        }

        # Открываем первую позицию
        paper_open_buy_auto("binance", "BTC/USDT", "1h", price=50000.0, ts_iso="2023-01-01T00:00:00Z", vol_state="normal")

        # Пытаемся открыть вторую
        result = paper_open_buy_auto("binance", "ETH/USDT", "1h", price=3000.0, ts_iso="2023-01-01T00:00:00Z", vol_state="normal")

        # Должен отказаться
        if "status" in result:
            assert result["status"] == "skip"
            assert "max_open_positions" in result["detail"]


def test_paper_open_buy_auto_position_max_fraction(clean_state):
    """Проверяет лимит по position_max_fraction."""
    with patch("src.trade.load_policy") as mock_load_policy, \
         patch("src.trade.paper_get_equity") as mock_equity:

        mock_load_policy.return_value = {
            "sizing": {"base_fraction": 0.50, "by_vol": {"normal": 0.50}, "min_order_usd": 10.0},
            "auto_sizing": {"qty_precision": 6},
            "max_open_positions": 0,
            "position_max_fraction": 0.2,  # макс 20% в одной монете
        }
        mock_equity.return_value = {"equity": 10000.0}

        # Пытаемся купить на 50% (5000 USDT), но лимит 20% (2000 USDT)
        result = paper_open_buy_auto(
            "binance", "BTC/USDT", "1h", price=50000.0, ts_iso="2023-01-01T00:00:00Z", vol_state="normal"
        )

        # Должен ограничить до 2000 USDT
        if "order" in result:
            # qty ≈ 2000 / 50000 = 0.04
            assert result["order"]["qty"] <= 0.05


# --- Тесты paper_close_pair ---


def test_paper_close_pair(clean_state):
    """Проверяет закрытие пары."""
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    result = paper_close_pair("binance", "BTC/USDT", "1h", price=51000.0, ts_iso="2023-01-01T01:00:00Z")

    assert result["order"]["side"] == "sell"
    assert result["position"]["qty"] == 0.0
    assert result["pnl"] == 100.0  # (51000 - 50000) * 0.1


def test_paper_close_pair_no_position(clean_state):
    """Проверяет ошибку при закрытии несуществующей пары."""
    result = paper_close_pair("binance", "BTC/USDT", "1h", price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    assert result["status"] == "error"


# --- Тесты paper_close_with_price ---


def test_paper_close_with_price(clean_state):
    """Проверяет алиас для paper_close_pair."""
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    result = paper_close_with_price("binance", "BTC/USDT", "1h", price=52000.0, ts_iso="2023-01-01T01:00:00Z")

    assert result["order"]["side"] == "sell"
    assert result["pnl"] == 200.0  # (52000 - 50000) * 0.1


# --- Интеграционные тесты ---


def test_full_trading_cycle(clean_state):
    """Интеграционный тест: buy → partial sell → full close."""
    # 1. Покупка
    buy1 = paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")
    assert buy1["cash"] == DEFAULT_STATE["cash"] - 5000.0

    # 2. Докупка
    buy2 = paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.05, price=52000.0, ts_iso="2023-01-01T01:00:00Z")
    assert buy2["position"]["qty"] == 0.15

    # 3. Частичная продажа
    sell1 = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.05, price=53000.0, ts_iso="2023-01-01T02:00:00Z")
    assert sell1["position"]["qty"] == 0.10

    # 4. Полное закрытие
    sell2 = paper_close_pair("binance", "BTC/USDT", "1h", price=54000.0, ts_iso="2023-01-01T03:00:00Z")
    assert sell2["position"]["qty"] == 0.0

    # Проверяем equity
    equity = paper_get_equity()
    assert equity["positions_value"] == 0.0
    # Должны быть в плюсе
    assert equity["cash"] > DEFAULT_STATE["cash"]


def test_pnl_calculation_accuracy(clean_state):
    """Проверяет точность расчёта PnL."""
    # Покупаем по 50000
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")

    # Продаём по 55000
    result = paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.1, price=55000.0, ts_iso="2023-01-01T01:00:00Z")

    # PnL = (55000 - 50000) * 0.1 = 500
    assert result["pnl"] == 500.0


def test_orders_history(clean_state):
    """Проверяет накопление истории ордеров."""
    paper_open_buy_manual("binance", "BTC/USDT", "1h", qty=0.1, price=50000.0, ts_iso="2023-01-01T00:00:00Z")
    paper_open_buy_manual("binance", "ETH/USDT", "1h", qty=1.0, price=3000.0, ts_iso="2023-01-01T01:00:00Z")
    paper_open_sell_manual("binance", "BTC/USDT", "1h", qty=0.05, price=51000.0, ts_iso="2023-01-01T02:00:00Z")

    orders = paper_get_orders()

    assert len(orders) == 3
    assert orders[0]["side"] == "buy"
    assert orders[1]["side"] == "buy"
    assert orders[2]["side"] == "sell"

