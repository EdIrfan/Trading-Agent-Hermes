"""End-to-end DEV loop with no network and no API key.

Wires FakeMarketData + MockBrain + PaperBroker + a temp-dir portfolio/ledger and
asserts one cycle paper-buys the whole basket toward its target weights, moves
cash into the positions, and records the fills. This is the smoke test that the
pipeline holds together before the real brain and live feed are connected.
"""

from hermes.brain.mock import MockBrain
from hermes.broker.paper import PaperBroker
from hermes.core.config import Config
from hermes.core.orchestrator import Orchestrator
from hermes.data.fake import FakeMarketData
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager

BASES = ["BTC", "ETH", "SOL", "BNB"]


def _config(state_root):
    return Config(
        environment="test",
        raw={},
        secrets={},
        state_root=state_root,
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
        starting_cash=10000.0,
        candle_lookback=30,
        taker_fee_rate=0.001,
        slippage_rate=0.0005,
        max_total_exposure=0.80,
        max_position_pct=0.40,
        sleeve_fill={"Buy": 1.0, "Overweight": 0.70, "Hold": None,
                     "Underweight": 0.35, "Sell": 0.0},
        min_order_notional=10.0,
        rebalance_threshold_pct=0.05,
    )


def _orchestrator(config, brain):
    config.ensure_state_dirs()
    market = FakeMarketData(base_price=60000.0)
    return Orchestrator(
        config=config,
        market=market,
        brain=brain,
        broker=PaperBroker(market, fee_rate=config.taker_fee_rate,
                           slippage_rate=config.slippage_rate),
        risk=RiskManager(config),
        portfolio=Portfolio.load(config.portfolio_path, starting_cash=10000.0,
                                 quote_currency="USDT"),
        ledger=Ledger(config.ledger_path),
    )


def test_buy_cycle_fills_whole_basket(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=False)

    # Every coin got a Buy and a fill (each targets a 20% sleeve).
    assert len(cycle.fills) == 4
    for base in BASES:
        assert orch.portfolio.quantity(base) > 0
    assert orch.portfolio.cash < 10000.0
    assert len(Ledger(config.ledger_path).all_fills()) == 4
    assert list(config.decisions_dir.glob("*.json"))

    # ~80% of value across the basket (max_total_exposure), ~20% cash.
    prices = {a.base: a.price for a in cycle.assets}
    crypto_weight = sum(orch.portfolio.weight(b, prices) for b in BASES)
    assert 0.78 < crypto_weight < 0.82


def test_dry_run_places_nothing(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=True)

    assert all(a.order is not None for a in cycle.assets)   # intent computed
    assert not cycle.fills                                  # nothing executed
    assert orch.portfolio.cash == 10000.0
    assert not Ledger(config.ledger_path).all_fills()


def test_hold_is_a_noop(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Hold"))

    cycle = orch.run_cycle(dry_run=False)

    assert not cycle.fills
    for base in BASES:
        assert orch.portfolio.quantity(base) == 0
