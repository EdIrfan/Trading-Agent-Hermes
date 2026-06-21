from hermes.brain.base import rating_to_action
from hermes.core.config import Config
from hermes.core.models import Action, Decision, Side
from hermes.data.symbols import parse_symbol
from hermes.portfolio.portfolio import Portfolio, Position
from hermes.risk.manager import RiskManager


def _config(**over):
    base = {
        "target_weights": {"Buy": 0.8, "Overweight": 0.6, "Hold": None,
                           "Underweight": 0.3, "Sell": 0.0},
        "max_position_pct": 0.8, "min_order_notional": 10.0,
        "rebalance_threshold_pct": 0.05, "taker_fee_rate": 0.001,
    }
    base.update(over)
    return Config(environment="test", raw={}, secrets={}, **base)


def _decision(rating):
    return Decision(symbol="BTC/USDT", rating=rating, action=rating_to_action(rating))


SYM = parse_symbol("BTC/USDT")


def test_buy_from_flat_targets_weight():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    res = rm.decide_order(_decision("Buy"), pf, SYM, price=50000)
    assert res.order is not None and res.order.side is Side.BUY
    # Target 80% of 10000 = 8000 notional -> 0.16 BTC.
    assert round(res.order.quantity, 6) == round(8000 / 50000, 6)


def test_hold_does_nothing():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    assert rm.decide_order(_decision("Hold"), pf, SYM, price=50000).order is None


def test_sell_reduces_toward_target():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=2000.0,
                   positions={"BTC": Position(quantity=0.16, avg_cost=50000)})
    # value = 2000 + 0.16*50000 = 10000; current weight 0.8. Sell -> target 0.
    res = rm.decide_order(_decision("Sell"), pf, SYM, price=50000)
    assert res.order is not None and res.order.side is Side.SELL
    assert round(res.order.quantity, 6) == 0.16


def test_within_threshold_skips():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=2050.0,
                   positions={"BTC": Position(quantity=0.159, avg_cost=50000)})
    # ~79.5% vs 80% target -> within 5% threshold -> no order.
    assert rm.decide_order(_decision("Buy"), pf, SYM, price=50000).order is None


def test_max_position_cap_clamps_target():
    rm = RiskManager(_config(max_position_pct=0.5))
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    res = rm.decide_order(_decision("Buy"), pf, SYM, price=50000)
    # Buy targets 80% but the 50% cap clamps it -> 5000 notional -> 0.1 BTC.
    assert round(res.order.quantity, 6) == round(5000 / 50000, 6)


def test_action_mapping():
    assert rating_to_action("Buy") is Action.BUY
    assert rating_to_action("Overweight") is Action.BUY
    assert rating_to_action("Hold") is Action.HOLD
    assert rating_to_action("Underweight") is Action.SELL
    assert rating_to_action("Sell") is Action.SELL
