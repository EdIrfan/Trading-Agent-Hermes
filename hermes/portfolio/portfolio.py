"""Portfolio state: cash, holdings, cost basis, and P&L.

Tracks an average cost basis per asset so realized and unrealized P&L are
separable (see docs/context/concepts.md). Persisted to JSON as a convenience
snapshot; the SQLite ledger remains the source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from hermes.core.models import Balance, Fill, Side


@dataclass
class Position:
    quantity: float = 0.0
    avg_cost: float = 0.0     # average entry price in quote currency


@dataclass
class Portfolio:
    quote_currency: str = "USDT"
    starting_cash: float = 10000.0
    cash: float = 10000.0
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    # ---- mutation -------------------------------------------------------
    def apply_fill(self, fill: Fill) -> None:
        """Update cash, holdings, cost basis, and realized P&L from a fill."""
        base = fill.symbol.split("/")[0]
        pos = self.positions.setdefault(base, Position())
        self.fees_paid += fill.fee

        if fill.side is Side.BUY:
            self.cash -= fill.gross_notional + fill.fee
            total_cost = pos.avg_cost * pos.quantity + fill.gross_notional
            pos.quantity += fill.quantity
            pos.avg_cost = total_cost / pos.quantity if pos.quantity else 0.0
        else:  # SELL
            self.cash += fill.gross_notional - fill.fee
            self.realized_pnl += (fill.price - pos.avg_cost) * fill.quantity
            pos.quantity -= fill.quantity
            if pos.quantity <= 1e-12:
                pos.quantity = 0.0
                pos.avg_cost = 0.0

    # ---- queries --------------------------------------------------------
    def quantity(self, base: str) -> float:
        pos = self.positions.get(base)
        return pos.quantity if pos else 0.0

    def balance(self) -> Balance:
        return Balance(
            cash=self.cash,
            positions={b: p.quantity for b, p in self.positions.items() if p.quantity > 0},
        )

    def value(self, prices: dict[str, float]) -> float:
        """Total mark-to-market value = cash + holdings priced at ``prices``."""
        holdings = sum(
            p.quantity * prices.get(b, 0.0) for b, p in self.positions.items()
        )
        return self.cash + holdings

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        return sum(
            (prices.get(b, p.avg_cost) - p.avg_cost) * p.quantity
            for b, p in self.positions.items()
        )

    def total_return(self, prices: dict[str, float]) -> float:
        if self.starting_cash == 0:
            return 0.0
        return (self.value(prices) - self.starting_cash) / self.starting_cash

    def weight(self, base: str, prices: dict[str, float]) -> float:
        """Fraction of total portfolio value held in ``base`` (0..1)."""
        total = self.value(prices)
        if total <= 0:
            return 0.0
        return (self.quantity(base) * prices.get(base, 0.0)) / total

    # ---- persistence ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "quote_currency": self.quote_currency,
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "fees_paid": self.fees_paid,
            "positions": {
                b: {"quantity": p.quantity, "avg_cost": p.avg_cost}
                for b, p in self.positions.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> Portfolio:
        return cls(
            quote_currency=d.get("quote_currency", "USDT"),
            starting_cash=d.get("starting_cash", 10000.0),
            cash=d.get("cash", 10000.0),
            realized_pnl=d.get("realized_pnl", 0.0),
            fees_paid=d.get("fees_paid", 0.0),
            positions={
                b: Position(quantity=v["quantity"], avg_cost=v["avg_cost"])
                for b, v in d.get("positions", {}).items()
            },
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path, *, starting_cash: float, quote_currency: str) -> Portfolio:
        """Load from JSON, or create a fresh portfolio if none exists yet."""
        if path.exists():
            return cls.from_dict(json.loads(path.read_text()))
        return cls(
            quote_currency=quote_currency,
            starting_cash=starting_cash,
            cash=starting_cash,
        )
