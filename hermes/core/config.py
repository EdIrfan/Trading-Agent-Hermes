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

# Hermes/ project root (two levels up from this file: hermes/core/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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

    # Market data
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    candle_timeframe: str = "1h"
    candle_lookback: int = 200

    # Frictions
    taker_fee_rate: float = 0.001
    slippage_rate: float = 0.0005

    # Risk / sizing
    target_weights: dict[str, float | None] = field(default_factory=dict)
    max_position_pct: float = 0.80
    min_order_notional: float = 10.0
    rebalance_threshold_pct: float = 0.05

    # LLM
    llm_provider: str = "anthropic"
    deep_think_llm: str = "claude-sonnet-4-6"
    quick_think_llm: str = "claude-haiku-4-5"
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    analysts: list[str] = field(default_factory=lambda: ["market", "social", "news"])

    @property
    def base_currency(self) -> str:
        """Base asset of the configured pair (e.g. 'BTC' from 'BTC/USDT')."""
        return self.symbol.split("/")[0]

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

    def ensure_state_dirs(self) -> None:
        self.decisions_dir.mkdir(parents=True, exist_ok=True)

    def secret(self, name: str) -> str | None:
        """Read a secret from the env file, falling back to the process env."""
        value = self.secrets.get(name) or os.environ.get(name)
        return value or None


# Fields on Config that may be overridden by a matching YAML key.
_OVERRIDABLE = {
    "broker", "starting_cash", "quote_currency", "exchange", "symbol",
    "candle_timeframe", "candle_lookback", "taker_fee_rate", "slippage_rate",
    "target_weights", "max_position_pct", "min_order_notional",
    "rebalance_threshold_pct", "llm_provider", "deep_think_llm",
    "quick_think_llm", "max_debate_rounds", "max_risk_discuss_rounds",
    "analysts",
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
