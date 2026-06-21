"""The Brain interface and the rating→action collapse.

A Brain turns "what's the market doing?" into a :class:`Decision`. Two
implementations exist: :class:`~hermes.brain.mock.MockBrain` (deterministic, no
API key — lets the whole DEV loop run today) and
:class:`~hermes.brain.tradingagents.TradingAgentsBrain` (the real multi-agent
pipeline). The orchestrator depends only on this Protocol, so swapping them is
the single change that turns the plumbing into the real thing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hermes.core.models import Action, Decision
from hermes.data.symbols import SymbolMap

# 5-tier rating -> collapsed BUY/HOLD/SELL. Long-only: Underweight/Sell both
# reduce exposure (the risk layer decides by how much via target weights).
_RATING_ACTION = {
    "Buy": Action.BUY,
    "Overweight": Action.BUY,
    "Hold": Action.HOLD,
    "Underweight": Action.SELL,
    "Sell": Action.SELL,
}


def rating_to_action(rating: str) -> Action:
    """Collapse a 5-tier rating to BUY / HOLD / SELL."""
    return _RATING_ACTION.get(rating, Action.HOLD)


@runtime_checkable
class Brain(Protocol):
    name: str

    def decide(
        self,
        *,
        symbols: SymbolMap,
        trade_date: str,
        live_snapshot: str,
        past_context: str = "",
    ) -> Decision:
        """Analyze the instrument and return a normalized Decision."""
        ...
