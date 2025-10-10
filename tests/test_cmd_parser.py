import pytest
from src.cmd_parser import _parse_trade_cmd

@pytest.mark.parametrize("text,expected", [
    ("/buy binance ETH/USDT 0.5 @ 3500.25 tf=15m",
     ("buy", "binance", "ETH/USDT", 0.5, 3500.25, "15m")),
    ("/sell bybit BTC/USDT 0.01 tf=1h",
     ("sell", "bybit", "BTC/USDT", 0.01, None, "1h")),
    ("/close binance ETH/USDT @ 3520 tf=4h",
     ("close", "binance", "ETH/USDT", None, 3520.0, "4h")),
    ("/close bybit BTC/USDT 0.003 @ 62000 tf=15m",
     ("close", "bybit", "BTC/USDT", 0.003, 62000.0, "15m")),
    ("/buy okx SOL/USDT 10", ("buy", "okx", "SOL/USDT", 10.0, None, "15m")),
])
def test_ok(text, expected):
    assert _parse_trade_cmd(text) == expected

@pytest.mark.parametrize("text", [
    "", "hello", "/foo", "/buy binance", "/sell bybit BTC/USDT",
    "/close binance"  # не хватает символа
])
def test_errors(text):
    with pytest.raises(Exception):
        _parse_trade_cmd(text)