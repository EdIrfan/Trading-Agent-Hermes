"""A deterministic stand-in brain — no API key, no LLM.

Returns a fixed (configurable) rating so the rest of Hermes (data → risk →
broker → portfolio → CLI) can be built and tested end-to-end before the real
brain is wired in. Swap :class:`MockBrain` for ``TradingAgentsBrain`` and the
loop is live.
"""

from __future__ import annotations

from hermes.brain.base import rating_to_action
from hermes.core.models import Decision
from hermes.data.symbols import SymbolMap


class MockBrain:
    name = "mock"

    def __init__(self, rating: str = "Buy"):
        self.rating = rating

    def decide(
        self,
        *,
        symbols: SymbolMap,
        trade_date: str,
        live_snapshot: str,
        past_context: str = "",
    ) -> Decision:
        return Decision(
            symbol=symbols.ccxt,
            rating=self.rating,
            action=rating_to_action(self.rating),
            reasoning=(
                "MockBrain: fixed decision for plumbing tests. No real analysis "
                "was performed. Replace with TradingAgentsBrain once an "
                "ANTHROPIC_API_KEY is configured."
            ),
            source=self.name,
        )
