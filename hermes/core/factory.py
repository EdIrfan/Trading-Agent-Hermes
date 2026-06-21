"""Build a wired Orchestrator from a Config.

Centralizes construction so the CLI stays thin and tests can swap pieces. The
brain choice is the important one: use the real TradingAgents brain only when
an ANTHROPIC_API_KEY is present (and not forced off), otherwise fall back to the
MockBrain so the loop still runs.
"""

from __future__ import annotations

from hermes.brain.base import Brain
from hermes.brain.mock import MockBrain
from hermes.core.config import Config
from hermes.core.orchestrator import Orchestrator
from hermes.data.market import MarketData, build_market_data
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager


def choose_brain(config: Config, *, force_mock: bool = False) -> Brain:
    """Real brain when a key is available and not forced off; else MockBrain."""
    if force_mock or not config.secret("ANTHROPIC_API_KEY"):
        return MockBrain()
    from hermes.brain.tradingagents import TradingAgentsBrain

    return TradingAgentsBrain(config)


def build_broker(config: Config, market: MarketData):
    if config.broker == "paper":
        from hermes.broker.paper import PaperBroker

        return PaperBroker(
            market, fee_rate=config.taker_fee_rate, slippage_rate=config.slippage_rate
        )
    raise ValueError(
        f"Broker '{config.broker}' is not implemented yet. "
        "Only 'paper' (DEV) exists; BinanceBroker (PROD) is a later phase."
    )


def build_orchestrator(
    config: Config,
    *,
    force_mock: bool = False,
    market: MarketData | None = None,
) -> Orchestrator:
    config.ensure_state_dirs()
    market = market or build_market_data(config)
    brain = choose_brain(config, force_mock=force_mock)
    broker = build_broker(config, market)
    risk = RiskManager(config)
    portfolio = Portfolio.load(
        config.portfolio_path,
        starting_cash=config.starting_cash,
        quote_currency=config.quote_currency,
    )
    ledger = Ledger(config.ledger_path)
    return Orchestrator(
        config=config, market=market, brain=brain, broker=broker,
        risk=risk, portfolio=portfolio, ledger=ledger,
    )
