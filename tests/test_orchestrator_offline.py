"""End-to-end DEV loop with no network and no API key.

Wires FakeMarketData + MockBrain + PaperBroker + a temp-dir portfolio/ledger and
asserts one cycle paper-buys BTC, moves cash into the position, and records the
fill. This is the smoke test that the whole pipeline holds together before the
real brain and live feed are connected.
"""

from hermes.brain.mock import MockBrain
from hermes.broker.paper import PaperBroker
from hermes.core.config import Config
from hermes.core.orchestrator import Orchestrator
from hermes.data.fake import FakeMarketData
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager


def _config(state_root):
    return Config(
        environment="test",
        raw={},
        secrets={},
        state_root=state_root,
        symbol="BTC/USDT",
        starting_cash=10000.0,
        candle_lookback=30,
        taker_fee_rate=0.001,
        slippage_rate=0.0005,
        target_weights={"Buy": 0.8, "Overweight": 0.6, "Hold": None,
                        "Underweight": 0.3, "Sell": 0.0},
        max_position_pct=0.8,
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


def test_buy_cycle_executes_and_records(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=False)

    assert cycle.decision.rating == "Buy"
    assert cycle.order is not None and cycle.fill is not None
    assert orch.portfolio.quantity("BTC") > 0
    assert orch.portfolio.cash < 10000.0
    # Fill recorded to the ledger and a decision file written.
    assert len(Ledger(config.ledger_path).all_fills()) == 1
    assert list(config.decisions_dir.glob("*.json"))
    # ~80% of value in BTC after the buy. Slightly over target because slippage
    # and fees shrink total value while the position is sized off the mid price.
    weight = orch.portfolio.weight("BTC", {"BTC": cycle.price})
    assert 0.79 < weight < 0.81


def test_dry_run_places_nothing(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=True)

    assert cycle.order is not None      # intent was computed
    assert cycle.fill is None           # but nothing executed
    assert orch.portfolio.quantity("BTC") == 0
    assert orch.portfolio.cash == 10000.0
    assert not Ledger(config.ledger_path).all_fills()


def test_hold_is_a_noop(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Hold"))

    cycle = orch.run_cycle(dry_run=False)

    assert cycle.order is None
    assert orch.portfolio.quantity("BTC") == 0
