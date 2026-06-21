"""Shared data shapes passed between Hermes components.

Plain dataclasses (no I/O, no business logic) so every layer — data, brain,
risk, broker, portfolio — speaks the same vocabulary. Money is held as float
here for simplicity; the ledger is the source of truth and a future hardening
could move to Decimal at the boundaries (see docs/context/extras.md).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Action(str, Enum):
    """What the trade layer should do this cycle (collapsed from the rating)."""

    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


# The brain's 5-tier rating, kept as plain strings matching TradingAgents'
# PortfolioRating ("Buy" / "Overweight" / "Hold" / "Underweight" / "Sell").
RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


@dataclass
class Decision:
    """The brain's verdict for one symbol, normalized for Hermes to act on.

    ``rating`` is the authoritative 5-tier call; ``action`` is the collapsed
    BUY/HOLD/SELL. The rest is advisory context the risk layer may use.
    """

    symbol: str
    rating: str                      # one of RATINGS
    action: Action
    reasoning: str = ""
    entry_price: float | None = None
    stop_loss: float | None = None
    position_sizing_hint: str | None = None
    confidence: str | None = None
    raw_reports: dict = field(default_factory=dict)
    source: str = "unknown"          # which brain produced it (e.g. "mock", "tradingagents")
    ts: float = field(default_factory=time.time)


@dataclass
class Order:
    """An instruction to trade ``quantity`` of ``symbol`` at market."""

    symbol: str
    side: Side
    quantity: float                  # in base units (e.g. BTC)
    reason: str = ""                 # why the risk layer sized it this way
    client_order_id: str | None = None


@dataclass
class Fill:
    """The realized result of an order (simulated in DEV, real in PROD)."""

    symbol: str
    side: Side
    quantity: float                  # base units actually filled
    price: float                     # effective fill price in quote currency
    fee: float                       # fee paid, in quote currency
    ts: float = field(default_factory=time.time)
    order_id: str | None = None
    broker: str = "paper"

    @property
    def gross_notional(self) -> float:
        """Quantity × price, before fees, in quote currency."""
        return self.quantity * self.price


@dataclass
class Balance:
    """A point-in-time account snapshot."""

    cash: float                      # free quote currency (e.g. USDT)
    positions: dict[str, float]      # base asset -> quantity held (e.g. {"BTC": 0.05})

    def quantity(self, base: str) -> float:
        return self.positions.get(base, 0.0)
