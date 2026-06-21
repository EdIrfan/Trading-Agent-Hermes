"""Adapter around TradingAgents — the only module that knows its internals.

Keeping all coupling here means upstream changes to the brain are absorbed in
one place (decision in docs/context/plan.md). The live Binance snapshot is
injected by subclassing ``TradingAgentsGraph`` and appending it to the
instrument context every agent sees — option B in docs/context/decisions.md
(D3): the brain's own data vendors are left untouched.

Requires an ``ANTHROPIC_API_KEY`` in the environment (the framework reads it
directly). Imports are lazy so the rest of Hermes works without the framework
installed or a key present.
"""

from __future__ import annotations

from hermes.brain.base import rating_to_action
from hermes.core.config import Config
from hermes.core.models import Decision
from hermes.data.symbols import SymbolMap


def _build_graph(config: Config, live_snapshot: str):
    """Construct a snapshot-injecting TradingAgentsGraph from Hermes config."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta_config = DEFAULT_CONFIG.copy()
    ta_config["llm_provider"] = config.llm_provider
    ta_config["deep_think_llm"] = config.deep_think_llm
    ta_config["quick_think_llm"] = config.quick_think_llm
    ta_config["max_debate_rounds"] = config.max_debate_rounds
    ta_config["max_risk_discuss_rounds"] = config.max_risk_discuss_rounds
    # Keep each environment's reflection/memory separate from the user's other
    # TradingAgents usage.
    ta_config["memory_log_path"] = str(
        config.state_dir / "brain_memory" / "trading_memory.md"
    )

    class _LiveContextGraph(TradingAgentsGraph):
        """Appends Hermes's live Binance snapshot to every agent's context."""

        hermes_snapshot: str = ""

        def resolve_instrument_context(self, ticker: str, asset_type: str = "stock") -> str:
            base = super().resolve_instrument_context(ticker, asset_type)
            if self.hermes_snapshot:
                return f"{base}\n\n{self.hermes_snapshot}"
            return base

    graph = _LiveContextGraph(
        selected_analysts=tuple(config.analysts),
        config=ta_config,
    )
    graph.hermes_snapshot = live_snapshot
    return graph


class TradingAgentsBrain:
    """Runs the real multi-agent pipeline and parses its verdict."""

    name = "tradingagents"

    def __init__(self, config: Config):
        self.config = config

    def decide(
        self,
        *,
        symbols: SymbolMap,
        trade_date: str,
        live_snapshot: str,
        past_context: str = "",
    ) -> Decision:
        from tradingagents.agents.utils.rating import parse_rating

        graph = _build_graph(self.config, live_snapshot)
        final_state, _decision_label = graph.propagate(
            symbols.yahoo, trade_date, asset_type="crypto"
        )

        pm_text = final_state.get("final_trade_decision", "")
        rating = parse_rating(pm_text)
        trader_text = final_state.get("trader_investment_plan", "")

        return Decision(
            symbol=symbols.ccxt,
            rating=rating,
            action=rating_to_action(rating),
            reasoning=pm_text,
            position_sizing_hint=trader_text or None,
            raw_reports={
                "market_report": final_state.get("market_report", ""),
                "sentiment_report": final_state.get("sentiment_report", ""),
                "news_report": final_state.get("news_report", ""),
                "investment_plan": final_state.get("investment_plan", ""),
                "trader_investment_plan": trader_text,
                "final_trade_decision": pm_text,
            },
            source=self.name,
        )
