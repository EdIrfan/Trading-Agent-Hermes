"""Build a wired Orchestrator from a Config.

Centralizes construction so the CLI stays thin and tests can swap pieces. The
brain choice is the important one: use the real TradingAgents brain only when
an ANTHROPIC_API_KEY is present (and not forced off), otherwise fall back to the
MockBrain so the loop still runs.
"""

from __future__ import annotations

import os

from hermes.brain.base import Brain
from hermes.brain.mock import MockBrain
from hermes.core.config import Config
from hermes.core.orchestrator import Orchestrator
from hermes.data.market import MarketData, build_market_data
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager

# Which env var holds each LLM provider's API key (mirrors TradingAgents'
# tradingagents/llm_clients/api_key_env.py).
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def llm_key_env(provider: str) -> str:
    return _PROVIDER_KEY_ENV.get(provider.lower(), "")


def choose_brain(config: Config, *, force_mock: bool = False) -> Brain:
    """Real brain when the provider's API key is available; else MockBrain.

    The key lives in ``.env.<env>`` (loaded into ``config.secrets``). The
    TradingAgents framework / LangChain read it from ``os.environ``, so we export
    it here before constructing the real brain.
    """
    key_env = llm_key_env(config.llm_provider)
    key = config.secret(key_env) if key_env else None
    if force_mock or not key:
        return MockBrain()
    os.environ[key_env] = key  # export so the framework can authenticate
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
