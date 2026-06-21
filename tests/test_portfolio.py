from hermes.core.models import Fill, Side
from hermes.portfolio.portfolio import Portfolio


def _buy(qty, price, fee=0.0):
    return Fill(symbol="BTC/USDT", side=Side.BUY, quantity=qty, price=price, fee=fee)


def _sell(qty, price, fee=0.0):
    return Fill(symbol="BTC/USDT", side=Side.SELL, quantity=qty, price=price, fee=fee)


def test_buy_updates_cash_and_cost_basis():
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    pf.apply_fill(_buy(0.1, 50000, fee=5.0))
    assert pf.quantity("BTC") == 0.1
    assert pf.cash == 10000.0 - 5000.0 - 5.0
    assert pf.positions["BTC"].avg_cost == 50000


def test_realized_pnl_on_sell():
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    pf.apply_fill(_buy(0.1, 50000))
    pf.apply_fill(_sell(0.1, 55000))
    assert round(pf.realized_pnl, 6) == 500.0  # (55000-50000)*0.1
    assert pf.quantity("BTC") == 0.0


def test_value_and_weight_mark_to_market():
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    pf.apply_fill(_buy(0.1, 50000))  # 5000 in BTC, 5000 cash
    prices = {"BTC": 60000}
    assert pf.value(prices) == 5000.0 + 0.1 * 60000
    assert round(pf.weight("BTC", prices), 4) == round((0.1 * 60000) / pf.value(prices), 4)


def test_roundtrip_serialization():
    pf = Portfolio(starting_cash=10000.0, cash=10000.0)
    pf.apply_fill(_buy(0.05, 50000, fee=2.5))
    restored = Portfolio.from_dict(pf.to_dict())
    assert restored.cash == pf.cash
    assert restored.positions["BTC"].avg_cost == pf.positions["BTC"].avg_cost
