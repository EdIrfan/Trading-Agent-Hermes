"""Turn a per-coin Decision into a guard-railed Order — or nothing.

Two sizing strategies (decision D4), selected by ``config.strategy``:

- ``fixed_notional`` (default): each buy signal buys a fixed dollar amount
  (``trade_notional``) of the coin, opportunistically, capped per coin at
  ``max_position_notional``. Sell closes the position; Underweight trims one
  trade's worth; Hold/Overweight handled below. Simple and intuitive — "take
  $100 trades as signals come, until cash runs low."
- ``target_weight``: equal-weight sleeves — each coin targets
  ``max_total_exposure / N`` of the portfolio, filled per rating via
  ``sleeve_fill``.

Hard guardrails — per-coin caps, min order size, the rebalance dead-band — live
here, *outside* the AI, so a reckless decision still can't exceed the limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from hermes.core.config import Config
from hermes.core.models import Decision, Order, Side
from hermes.data.symbols import SymbolMap
from hermes.portfolio.portfolio import Portfolio

_BUY_RATINGS = {"Buy", "Overweight"}


@dataclass
class RiskResult:
    order: Order | None
    reason: str


class RiskManager:
    def __init__(self, config: Config):
        self.strategy = config.strategy
        self.min_order_notional = config.min_order_notional
        self.fee_rate = config.taker_fee_rate
        # fixed_notional
        self.trade_notional = config.trade_notional
        self.max_position_notional = config.max_position_notional
        # target_weight
        self.sleeve_fill = config.sleeve_fill
        self.max_total_exposure = config.max_total_exposure
        self.num_assets = max(config.num_assets, 1)
        self.max_position_pct = config.max_position_pct
        self.rebalance_threshold_pct = config.rebalance_threshold_pct

    def decide_order(
        self,
        decision: Decision,
        portfolio: Portfolio,
        symbols: SymbolMap,
        prices: dict[str, float],
    ) -> RiskResult:
        """Size one coin's order. ``prices`` is the live price of every basket
        coin (so the whole portfolio is valued at market for target_weight)."""
        price = prices.get(symbols.base, 0.0)
        if price <= 0:
            return RiskResult(None, f"{symbols.base}: no price; skipping.")
        if self.strategy == "fixed_notional":
            return self._fixed_notional(decision, portfolio, symbols, price)
        return self._target_weight(decision, portfolio, symbols, prices, price)

    # ---- fixed-dollar strategy ------------------------------------------
    def _fixed_notional(self, decision, portfolio, symbols, price) -> RiskResult:
        base = symbols.base
        held_qty = portfolio.quantity(base)
        held_value = held_qty * price
        rating = decision.rating

        if rating in _BUY_RATINGS:
            room = self.max_position_notional - held_value
            if room < self.min_order_notional:
                return RiskResult(None, f"{base}: at per-coin cap "
                                        f"({self.max_position_notional:g}); no buy.")
            affordable = portfolio.cash / (1.0 + self.fee_rate)
            notional = min(self.trade_notional, room, affordable)
            if notional < self.min_order_notional:
                return RiskResult(None, f"{base}: not enough cash for a trade.")
            order = Order(
                symbol=symbols.ccxt, side=Side.BUY, quantity=notional / price,
                reason=f"{rating}: buy {notional:,.0f} {symbols.quote} of {base}.",
            )
            return RiskResult(order, order.reason)

        if rating == "Underweight":
            notional = min(self.trade_notional, held_value)
            if notional < self.min_order_notional:
                return RiskResult(None, f"{base}: nothing meaningful to trim.")
            order = Order(
                symbol=symbols.ccxt, side=Side.SELL, quantity=notional / price,
                reason=f"Underweight: trim {notional:,.0f} {symbols.quote} of {base}.",
            )
            return RiskResult(order, order.reason)

        if rating == "Sell":
            if held_value < self.min_order_notional:
                return RiskResult(None, f"{base}: no position to close.")
            order = Order(
                symbol=symbols.ccxt, side=Side.SELL, quantity=held_qty,
                reason=f"Sell: close {base} position (~{held_value:,.0f} {symbols.quote}).",
            )
            return RiskResult(order, order.reason)

        return RiskResult(None, f"{base}: rating '{rating}' holds — no change.")

    # ---- equal-weight-sleeve strategy -----------------------------------
    def target_weight(self, rating: str) -> float | None:
        fill = self.sleeve_fill.get(rating)
        if fill is None:
            return None
        sleeve = self.max_total_exposure / self.num_assets
        return min(sleeve * float(fill), self.max_position_pct)

    def _target_weight(self, decision, portfolio, symbols, prices, price) -> RiskResult:
        base = symbols.base
        total_value = portfolio.value(prices)
        if total_value <= 0:
            return RiskResult(None, "No portfolio value; skipping.")
        weight = self.target_weight(decision.rating)
        if weight is None:
            return RiskResult(None, f"{base}: rating '{decision.rating}' holds — no change.")

        current_value = portfolio.quantity(base) * price
        delta_value = weight * total_value - current_value
        if abs(delta_value) / total_value < self.rebalance_threshold_pct:
            return RiskResult(None, f"{base}: within dead-band of {weight:.0%}; no rebalance.")
        if abs(delta_value) < self.min_order_notional:
            return RiskResult(None, f"{base}: order below min notional; skipping.")

        if delta_value > 0:
            affordable = portfolio.cash / (1.0 + self.fee_rate)
            notional = min(delta_value, affordable)
            if notional < self.min_order_notional:
                return RiskResult(None, f"{base}: not enough cash to buy meaningfully.")
            order = Order(symbol=symbols.ccxt, side=Side.BUY, quantity=notional / price,
                          reason=f"{decision.rating}: raise {base} toward {weight:.0%}.")
        else:
            held = portfolio.quantity(base)
            quantity = min(-delta_value / price, held)
            if quantity * price < self.min_order_notional:
                return RiskResult(None, f"{base}: nothing meaningful to sell.")
            order = Order(symbol=symbols.ccxt, side=Side.SELL, quantity=quantity,
                          reason=f"{decision.rating}: cut {base} toward {weight:.0%}.")
        return RiskResult(order, order.reason)
