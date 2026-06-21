"""End-to-end DEV loop with no network and no API key.

Wires FakeMarketData + MockBrain + PaperBroker + a temp-dir portfolio/ledger and
asserts one cycle takes a fixed-dollar buy in each coin, moves cash into the
positions, and records the fills. The smoke test that the pipeline holds
together before the real brain and live feed are connected.
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
        symbol_exchanges={},          # all on the fake feed in tests
        starting_cash=10000.0,
        candle_lookback=30,
        taker_fee_rate=0.001,
        slippage_rate=0.0005,
        strategy="fixed_notional",
        trade_notional=100.0,
        max_position_notional=2000.0,
        min_order_notional=10.0,
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


def test_buy_cycle_takes_fixed_dollar_trades(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=False)

    # Every coin got a Buy and a ~$100 fill.
    assert len(cycle.fills) == 4
    for base in BASES:
        assert orch.portfolio.quantity(base) > 0
    # ~$400 deployed (+fees) -> cash a little under 9600.
    assert 9590 < orch.portfolio.cash < 9601
    assert len(Ledger(config.ledger_path).all_fills()) == 4
    assert list(config.decisions_dir.glob("*.json"))
    # Each position is about $100 at the fill price.
    prices = {a.base: a.price for a in cycle.assets}
    for base in BASES:
        assert 95 < orch.portfolio.quantity(base) * prices[base] < 102


def test_dry_run_places_nothing(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Buy"))

    cycle = orch.run_cycle(dry_run=True)

    assert all(a.order is not None for a in cycle.assets)
    assert not cycle.fills
    assert orch.portfolio.cash == 10000.0
    assert not Ledger(config.ledger_path).all_fills()


def test_hold_is_a_noop(tmp_path):
    config = _config(tmp_path)
    orch = _orchestrator(config, MockBrain("Hold"))

    cycle = orch.run_cycle(dry_run=False)

    assert not cycle.fills
    for base in BASES:
        assert orch.portfolio.quantity(base) == 0
