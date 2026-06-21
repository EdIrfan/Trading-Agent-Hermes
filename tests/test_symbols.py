from hermes.data.symbols import parse_symbol


def test_parses_ccxt_symbol():
    s = parse_symbol("BTC/USDT")
    assert (s.base, s.quote) == ("BTC", "USDT")
    assert s.binance == "BTCUSDT"
    assert s.yahoo == "BTC-USD"  # USDT collapses to USD for the brain


def test_parses_compact_and_yahoo_forms():
    assert parse_symbol("ETHUSDT").ccxt == "ETH/USDT"
    assert parse_symbol("BTC-USD").binance == "BTCUSD"
    assert parse_symbol("solusdc").yahoo == "SOL-USD"


def test_non_usd_quote_preserved():
    s = parse_symbol("BTC/EUR")
    assert s.yahoo == "BTC-EUR"
