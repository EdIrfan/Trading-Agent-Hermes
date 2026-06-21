from hermes.brain.base import rating_to_action
from hermes.core.config import Config
from hermes.core.models import Decision, Side
from hermes.data.symbols import parse_symbol
from hermes.portfolio.portfolio import Portfolio, Position
from hermes.risk.manager import RiskManager

SYM = parse_symbol("BTC/USDT")
PRICES = {"BTC": 50000.0}


def _config(**over):
    base = {
        "strategy": "fixed_notional",
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "trade_notional": 100.0,
        "max_position_notional": 2000.0,
        "min_order_notional": 10.0,
        "taker_fee_rate": 0.001,
    }
    base.update(over)
    return Config(environment="test", raw={}, secrets={}, **base)


def _decision(rating):
    return Decision(symbol="BTC/USDT", rating=rating, action=rating_to_action(rating))


def _pf(cash=10000.0, qty=0.0):
    pos = {"BTC": Position(quantity=qty, avg_cost=50000.0)} if qty else {}
    return Portfolio(starting_cash=10000.0, cash=cash, positions=pos)


def test_buy_is_fixed_dollars():
    res = RiskManager(_config()).decide_order(_decision("Buy"), _pf(), SYM, PRICES)
    assert res.order is not None and res.order.side is Side.BUY
    assert round(res.order.quantity, 8) == round(100 / 50000, 8)  # $100 -> 0.002 BTC


def test_overweight_also_buys_fixed():
    res = RiskManager(_config()).decide_order(_decision("Overweight"), _pf(), SYM, PRICES)
    assert round(res.order.quantity, 8) == round(100 / 50000, 8)


def test_hold_does_nothing():
    assert RiskManager(_config()).decide_order(_decision("Hold"), _pf(), SYM, PRICES).order is None


def test_underweight_trims_one_trade():
    res = RiskManager(_config()).decide_order(_decision("Underweight"), _pf(qty=0.01), SYM, PRICES)
    assert res.order is not None and res.order.side is Side.SELL
    assert round(res.order.quantity, 8) == round(100 / 50000, 8)  # trims $100


def test_sell_closes_whole_position():
    res = RiskManager(_config()).decide_order(_decision("Sell"), _pf(qty=0.01), SYM, PRICES)
    assert res.order is not None and res.order.side is Side.SELL
    assert res.order.quantity == 0.01  # closes the full 0.01 BTC


def test_per_coin_cap_blocks_further_buys():
    # Holding $2000 (0.04 BTC) == cap -> no more buying.
    res = RiskManager(_config()).decide_order(_decision("Buy"), _pf(qty=0.04), SYM, PRICES)
    assert res.order is None


def test_no_cash_skips_buy():
    res = RiskManager(_config()).decide_order(_decision("Buy"), _pf(cash=5.0), SYM, PRICES)
    assert res.order is None
