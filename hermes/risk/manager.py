"""Turn a per-coin Decision into a guard-railed Order — or nothing.

Multi-asset target-weight sizing (decision D4): the crypto basket splits into
equal-weight sleeves (``max_total_exposure / N`` per coin), and each coin's
rating sets how full its sleeve is (``sleeve_fill``). Hermes trades the
difference between that target and the current holding. Hard guardrails — the
per-coin position cap, the min order size, the rebalance dead-band — live here,
*outside* the AI, so a reckless decision still can't exceed the limits
(docs/context/plan.md §3.3).
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
        self.sleeve_fill = config.sleeve_fill
        self.max_total_exposure = config.max_total_exposure
        self.num_assets = max(config.num_assets, 1)
        self.max_position_pct = config.max_position_pct
        self.min_order_notional = config.min_order_notional
        self.rebalance_threshold_pct = config.rebalance_threshold_pct
        self.fee_rate = config.taker_fee_rate

    def target_weight(self, rating: str) -> float | None:
        """Target portfolio weight for one coin given its rating (None = hold)."""
        fill = self.sleeve_fill.get(rating)
        if fill is None:
            return None
        sleeve = self.max_total_exposure / self.num_assets
        return min(sleeve * float(fill), self.max_position_pct)

    def decide_order(
        self,
        decision: Decision,
        portfolio: Portfolio,
        symbols: SymbolMap,
        prices: dict[str, float],
    ) -> RiskResult:
        """Size one coin's order. ``prices`` is the live price of every basket
        coin (so the whole portfolio is valued at market, not cost basis)."""
        base = symbols.base
        price = prices.get(base, 0.0)
        total_value = portfolio.value(prices)
        if total_value <= 0 or price <= 0:
            return RiskResult(None, "No portfolio value or price; skipping.")

        weight = self.target_weight(decision.rating)
        if weight is None:
            return RiskResult(None, f"{base}: rating '{decision.rating}' holds — no change.")

        current_value = portfolio.quantity(base) * price
        target_value = weight * total_value
        delta_value = target_value - current_value

        if abs(delta_value) / total_value < self.rebalance_threshold_pct:
            return RiskResult(
                None,
                f"{base}: within {self.rebalance_threshold_pct:.0%} of target "
                f"({weight:.0%}); no rebalance.",
            )
        if abs(delta_value) < self.min_order_notional:
            return RiskResult(None, f"{base}: order below min notional; skipping.")

        if delta_value > 0:
            return self._build_buy(decision, portfolio, symbols, price, delta_value, weight)
        return self._build_sell(decision, portfolio, symbols, price, -delta_value, weight)

    def _build_buy(self, decision, portfolio, symbols, price, notional, weight) -> RiskResult:
        affordable = portfolio.cash / (1.0 + self.fee_rate)
        notional = min(notional, affordable)
        if notional < self.min_order_notional:
            return RiskResult(None, f"{symbols.base}: not enough cash to buy meaningfully.")
        order = Order(
            symbol=symbols.ccxt, side=Side.BUY, quantity=notional / price,
            reason=(
                f"{decision.rating}: raise {symbols.base} toward {weight:.0%} "
                f"of portfolio (buy ~{notional:,.2f} {symbols.quote})."
            ),
        )
        return RiskResult(order, order.reason)

    def _build_sell(self, decision, portfolio, symbols, price, notional, weight) -> RiskResult:
        held = portfolio.quantity(symbols.base)
        quantity = min(notional / price, held)
        if quantity * price < self.min_order_notional:
            return RiskResult(None, f"{symbols.base}: nothing meaningful to sell.")
        order = Order(
            symbol=symbols.ccxt, side=Side.SELL, quantity=quantity,
            reason=(
                f"{decision.rating}: cut {symbols.base} toward {weight:.0%} "
                f"of portfolio (sell ~{quantity * price:,.2f} {symbols.quote})."
            ),
        )
        return RiskResult(order, order.reason)
