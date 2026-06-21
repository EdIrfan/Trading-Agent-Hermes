"""Turn a Decision into a concrete, guard-railed Order — or nothing.

Target-weight, long-only, single-asset sizing (decision D4): each 5-tier rating
maps to a target fraction of portfolio value held in the asset, and Hermes
trades the difference. Hard guardrails live here, *outside* the AI, so even a
reckless decision can't exceed the configured limits (docs/context/plan.md §3.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from hermes.core.config import Config
from hermes.core.models import Decision, Order, Side
from hermes.data.symbols import SymbolMap
from hermes.portfolio.portfolio import Portfolio


@dataclass
class RiskResult:
    order: Order | None
    reason: str


class RiskManager:
    def __init__(self, config: Config):
        self.target_weights = config.target_weights
        self.max_position_pct = config.max_position_pct
        self.min_order_notional = config.min_order_notional
        self.rebalance_threshold_pct = config.rebalance_threshold_pct
        self.fee_rate = config.taker_fee_rate

    def decide_order(
        self, decision: Decision, portfolio: Portfolio, symbols: SymbolMap, price: float
    ) -> RiskResult:
        base = symbols.base
        prices = {base: price}
        total_value = portfolio.value(prices)
        if total_value <= 0 or price <= 0:
            return RiskResult(None, "No portfolio value or price; skipping.")

        target_weight = self.target_weights.get(decision.rating)
        if target_weight is None:
            return RiskResult(None, f"Rating '{decision.rating}' holds — no change.")

        # Hard guardrail: never target more than the position cap.
        target_weight = min(float(target_weight), self.max_position_pct)

        current_value = portfolio.quantity(base) * price
        target_value = target_weight * total_value
        delta_value = target_value - current_value

        if abs(delta_value) / total_value < self.rebalance_threshold_pct:
            return RiskResult(
                None,
                f"Within {self.rebalance_threshold_pct:.0%} of target "
                f"({target_weight:.0%}); no rebalance needed.",
            )
        if abs(delta_value) < self.min_order_notional:
            return RiskResult(
                None, f"Order below min notional {self.min_order_notional:g}; skipping."
            )

        if delta_value > 0:
            return self._build_buy(decision, portfolio, symbols, price, delta_value, target_weight)
        return self._build_sell(decision, portfolio, symbols, price, -delta_value, target_weight)

    def _build_buy(self, decision, portfolio, symbols, price, notional, target_weight) -> RiskResult:
        # Cap to affordable cash (leave room for the fee).
        affordable = portfolio.cash / (1.0 + self.fee_rate)
        notional = min(notional, affordable)
        if notional < self.min_order_notional:
            return RiskResult(None, "Not enough cash to buy a meaningful amount.")
        quantity = notional / price
        order = Order(
            symbol=symbols.ccxt, side=Side.BUY, quantity=quantity,
            reason=(
                f"{decision.rating}: raise {symbols.base} toward {target_weight:.0%} "
                f"of portfolio (buy ~{notional:,.2f} {symbols.quote})."
            ),
        )
        return RiskResult(order, order.reason)

    def _build_sell(self, decision, portfolio, symbols, price, notional, target_weight) -> RiskResult:
        held = portfolio.quantity(symbols.base)
        quantity = min(notional / price, held)
        if quantity * price < self.min_order_notional:
            return RiskResult(None, "Nothing meaningful to sell toward target.")
        order = Order(
            symbol=symbols.ccxt, side=Side.SELL, quantity=quantity,
            reason=(
                f"{decision.rating}: cut {symbols.base} toward {target_weight:.0%} "
                f"of portfolio (sell ~{quantity * price:,.2f} {symbols.quote})."
            ),
        )
        return RiskResult(order, order.reason)
