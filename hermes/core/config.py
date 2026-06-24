"""Load per-environment configuration: config/<env>.yaml + .env.<env>.

Selecting an environment (`dev` / `prod`) chooses a YAML file and an env file.
This is the single switch that makes DEV and PROD differ (decision in
docs/context/environments.md). Secrets come only from the env file; everything
else from the YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from hermes.data.symbols import SymbolMap, parse_symbol

# Hermes/ project root (two levels up from this file: hermes/core/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_symbols() -> list[str]:
    return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "HYPE/USDT"]


def _default_symbol_exchanges() -> dict[str, str]:
    # Per-coin exchange overrides. HYPE (Hyperliquid) is not on Binance spot,
    # so its price comes from Bybit; everything else uses the default exchange.
    return {"HYPE/USDT": "bybit"}


def _default_sleeve_fill() -> dict[str, float | None]:
    # Rating -> how full to make this coin's equal-weight sleeve (target_weight
    # strategy only).
    return {"Buy": 1.0, "Overweight": 0.70, "Hold": None, "Underweight": 0.35, "Sell": 0.0}


@dataclass
class Config:
    """Resolved settings for one environment.

    ``raw`` holds the full parsed YAML so new keys are reachable without
    editing this class; the typed attributes cover what the code uses today.
    """

    environment: str
    raw: dict[str, Any]
    secrets: dict[str, str]

    # Override the base directory for per-environment state (tests point this at
    # a temp dir; production leaves it None and uses PROJECT_ROOT/state).
    state_root: Path | None = None

    # Broker / account
    broker: str = "paper"
    starting_cash: float = 10000.0
    quote_currency: str = "USDT"

    # Market data — a basket of coins (multi-asset), each on its own exchange.
    exchange: str = "binance"                 # default exchange for price data
    symbols: list[str] = field(default_factory=_default_symbols)
    symbol_exchanges: dict[str, str] = field(default_factory=_default_symbol_exchanges)
    candle_timeframe: str = "1h"
    candle_lookback: int = 200

    # Frictions
    taker_fee_rate: float = 0.001
    slippage_rate: float = 0.0005

    # Risk / sizing (decision D4). Two strategies are supported:
    #   "fixed_notional" (default) — each buy signal buys ``trade_notional`` of
    #     the coin (opportunistic, fixed-dollar trades), capped per coin at
    #     ``max_position_notional``; Sell closes the position, Underweight trims
    #     one trade's worth.
    #   "target_weight" — equal-weight sleeves (max_total_exposure / N per coin),
    #     filled per rating via ``sleeve_fill``.
    strategy: str = "fixed_notional"
    trade_notional: float = 100.0             # USDT bought/sold per signal (fixed_notional)
    max_position_notional: float = 2000.0     # per-coin cap (fixed_notional)
    min_order_notional: float = 10.0          # skip dust orders (both strategies)
    # target_weight-only knobs:
    max_total_exposure: float = 0.80
    max_position_pct: float = 0.40
    sleeve_fill: dict[str, float | None] = field(default_factory=_default_sleeve_fill)
    rebalance_threshold_pct: float = 0.05

    # Safety — daily-loss circuit breaker (Phase 3). If the portfolio falls more
    # than ``max_daily_loss_pct`` below the UTC day's opening value, block new
    # buys for the rest of the day (sells still allowed). The bot's kill switch.
    circuit_breaker: bool = True
    max_daily_loss_pct: float = 0.05

    # LLM
    llm_provider: str = "anthropic"
    deep_think_llm: str = "claude-sonnet-4-6"
    quick_think_llm: str = "claude-haiku-4-5"
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    analysts: list[str] = field(default_factory=lambda: ["market", "social", "news"])

    @property
    def symbol_maps(self) -> list[SymbolMap]:
        """The basket as resolved :class:`SymbolMap` objects."""
        return [parse_symbol(s) for s in self.symbols]

    @property
    def num_assets(self) -> int:
        return len(self.symbols)

    @property
    def state_dir(self) -> Path:
        """Per-environment state directory (portfolio, ledger, decisions)."""
        root = self.state_root or (PROJECT_ROOT / "state")
        return root / self.environment

    @property
    def decisions_dir(self) -> Path:
        return self.state_dir / "decisions"

    @property
    def portfolio_path(self) -> Path:
        return self.state_dir / "portfolio.json"

    @property
    def ledger_path(self) -> Path:
        return self.state_dir / "ledger.sqlite"

    @property
    def equity_path(self) -> Path:
        """Time series of portfolio value (one row per cycle) — feeds the report."""
        return self.state_dir / "equity.csv"

    @property
    def breaker_path(self) -> Path:
        """Persisted daily-loss circuit-breaker state."""
        return self.state_dir / "breaker.json"

    def ensure_state_dirs(self) -> None:
        self.decisions_dir.mkdir(parents=True, exist_ok=True)

    def secret(self, name: str) -> str | None:
        """Read a secret from the env file, falling back to the process env."""
        value = self.secrets.get(name) or os.environ.get(name)
        return value or None


# Fields on Config that may be overridden by a matching YAML key.
_OVERRIDABLE = {
    "broker", "starting_cash", "quote_currency", "exchange", "symbols",
    "symbol_exchanges", "candle_timeframe", "candle_lookback", "taker_fee_rate",
    "slippage_rate", "strategy", "trade_notional", "max_position_notional",
    "min_order_notional", "max_total_exposure", "max_position_pct",
    "sleeve_fill", "rebalance_threshold_pct", "circuit_breaker",
    "max_daily_loss_pct", "llm_provider", "deep_think_llm",
    "quick_think_llm", "max_debate_rounds", "max_risk_discuss_rounds", "analysts",
}


def load_config(environment: str = "dev") -> Config:
    """Load ``config/<environment>.yaml`` and ``.env.<environment>``.

    A missing env file is tolerated (DEV needs no secrets for the MockBrain or
    keyless market data); a missing YAML file is an error.
    """
    yaml_path = PROJECT_ROOT / "config" / f"{environment}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"No config for environment '{environment}': expected {yaml_path}"
        )
    raw = yaml.safe_load(yaml_path.read_text()) or {}

    env_path = PROJECT_ROOT / f".env.{environment}"
    secrets = {k: v for k, v in dotenv_values(env_path).items() if v is not None}

    kwargs = {k: raw[k] for k in _OVERRIDABLE if k in raw}
    return Config(environment=environment, raw=raw, secrets=secrets, **kwargs)
