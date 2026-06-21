from hermes.brain.base import rating_to_action
from hermes.core.config import Config
from hermes.core.models import Action, Decision, Side
from hermes.data.symbols import parse_symbol
from hermes.portfolio.portfolio import Portfolio, Position
from hermes.risk.manager import RiskManager

SYM = parse_symbol("BTC/USDT")


def _config(**over):
    base = {
        "strategy": "target_weight",
        "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
        "max_total_exposure": 0.80,   # / 4 coins -> 0.20 sleeve each
        "max_position_pct": 0.40,
        "sleeve_fill": {"Buy": 1.0, "Overweight": 0.70, "Hold": None,
                        "Underweight": 0.35, "Sell": 0.0},
        "min_order_notional": 10.0,
        "rebalance_threshold_pct": 0.05,
        "taker_fee_rate": 0.001,
    }
    base.update(over)
    return Config(environment="test", raw={}, secrets={}, **base)


def _decision(rating):
    return Decision(symbol="BTC/USDT", rating=rating, action=rating_to_action(rating))


def test_buy_from_flat_targets_sleeve():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    res = rm.decide_order(_decision("Buy"), pf, SYM, {"BTC": 50000})
    assert res.order is not None and res.order.side is Side.BUY
    # Sleeve 20% of 10000 = 2000 notional -> 0.04 BTC.
    assert round(res.order.quantity, 6) == round(2000 / 50000, 6)


def test_overweight_partially_fills_sleeve():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    res = rm.decide_order(_decision("Overweight"), pf, SYM, {"BTC": 50000})
    # 0.7 * 20% = 14% -> 1400 notional.
    assert round(res.order.quantity, 6) == round(1400 / 50000, 6)


def test_hold_does_nothing():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    assert rm.decide_order(_decision("Hold"), pf, SYM, {"BTC": 50000}).order is None


def test_sell_reduces_to_zero():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=8000.0, cash=8000.0,
                   positions={"BTC": Position(quantity=0.04, avg_cost=50000)})
    # value = 8000 + 0.04*50000 = 10000; weight 20%. Sell -> target 0.
    res = rm.decide_order(_decision("Sell"), pf, SYM, {"BTC": 50000})
    assert res.order is not None and res.order.side is Side.SELL
    assert round(res.order.quantity, 6) == 0.04


def test_within_threshold_skips():
    rm = RiskManager(_config())
    pf = Portfolio(starting_cash=10000.0, cash=8050.0,
                   positions={"BTC": Position(quantity=0.039, avg_cost=50000)})
    # ~19.5% vs 20% target -> within 5% dead-band -> no order.
    assert rm.decide_order(_decision("Buy"), pf, SYM, {"BTC": 50000}).order is None


def test_per_coin_cap_clamps_target():
    rm = RiskManager(_config(max_position_pct=0.10))
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    res = rm.decide_order(_decision("Buy"), pf, SYM, {"BTC": 50000})
    # Sleeve would be 20% but the 10% per-coin cap clamps it -> 1000 -> 0.02 BTC.
    assert round(res.order.quantity, 6) == round(1000 / 50000, 6)


def test_action_mapping():
    assert rating_to_action("Buy") is Action.BUY
    assert rating_to_action("Overweight") is Action.BUY
    assert rating_to_action("Hold") is Action.HOLD
    assert rating_to_action("Underweight") is Action.SELL
    assert rating_to_action("Sell") is Action.SELL
