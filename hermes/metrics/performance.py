"""Compute a performance report from the equity curve + the ledger.

Answers the question the whole project exists to answer: *is the AI any good?*
A paper P&L in isolation is meaningless — up 1% means nothing if the coins were
up 3%. So the headline number here is **alpha vs buy-and-hold**: how the strategy
did versus simply splitting the same starting cash equally across the basket and
holding it over the same window. Positive alpha = the decisions added value;
negative = you'd have done better doing nothing (and paying no fees).

Everything is derived from two on-disk sources, so a report is reproducible:
- the equity curve (``equity.csv``) → value over time, drawdown, the benchmark's
  start/end prices;
- the ledger (every fill) → trade count, fees, and a replayed win-rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hermes.core.models import Fill, Side
from hermes.metrics.equity import EquityPoint


@dataclass
class PerformanceReport:
    has_data: bool = False
    note: str = ""

    # Window
    start_epoch: float = 0.0
    end_epoch: float = 0.0
    cycles: int = 0

    # Strategy
    start_value: float = 0.0
    end_value: float = 0.0
    strategy_return_pct: float = 0.0   # percent (e.g. 1.5 == +1.5%)
    peak_value: float = 0.0
    max_drawdown_pct: float = 0.0      # percent, positive = worst peak-to-trough drop

    # Benchmark (equal-weight buy-and-hold of the basket)
    benchmark_return_pct: float = 0.0
    benchmark_end_value: float = 0.0
    alpha_pct: float = 0.0             # strategy_return - benchmark_return
    benchmark_symbols: list[str] = field(default_factory=list)

    # Trades
    trades: int = 0
    buys: int = 0
    sells: int = 0
    closed_trades: int = 0             # sells matched against cost basis
    wins: int = 0
    win_rate_pct: float = 0.0
    fees_paid: float = 0.0

    @property
    def duration_hours(self) -> float:
        return max(self.end_epoch - self.start_epoch, 0.0) / 3600.0


def _max_drawdown_pct(values: list[float]) -> float:
    peak = float("-inf")
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst * 100.0


def _benchmark(points: list[EquityPoint]) -> tuple[float, float, list[str]]:
    """Equal-weight buy-and-hold of the basket over the equity window.

    Splits the *first* recorded portfolio value equally across every coin that
    has a price at both ends of the window, buys at the first prices, and marks
    at the last prices. Frictionless on purpose — it's the "do nothing clever"
    baseline; the strategy already pays its fees, so any alpha is net of them.
    Returns (end_value, return_pct, symbols_used).
    """
    first, last = points[0], points[-1]
    symbols = sorted(
        b for b in first.prices
        if first.prices.get(b, 0) > 0 and last.prices.get(b, 0) > 0
    )
    start_value = first.value
    if not symbols or start_value <= 0:
        return start_value, 0.0, []
    per_coin = start_value / len(symbols)
    end_value = sum(
        (per_coin / first.prices[b]) * last.prices[b] for b in symbols
    )
    return_pct = (end_value - start_value) / start_value * 100.0
    return end_value, return_pct, symbols


def _trade_stats(fills: list[Fill]) -> tuple[int, int, int, int, int, float]:
    """Replay fills with a running average cost to score each closed trade.

    Returns (buys, sells, closed_trades, wins, total_trades, fees). A SELL is a
    "win" if its price beat the position's average cost at the moment of sale.
    """
    avg_cost: dict[str, float] = {}
    qty: dict[str, float] = {}
    buys = sells = closed = wins = 0
    fees = 0.0
    for f in fills:
        base = f.symbol.split("/")[0]
        fees += f.fee
        if f.side is Side.BUY:
            buys += 1
            prev_qty = qty.get(base, 0.0)
            prev_cost = avg_cost.get(base, 0.0)
            new_qty = prev_qty + f.quantity
            avg_cost[base] = (
                (prev_cost * prev_qty + f.price * f.quantity) / new_qty if new_qty else 0.0
            )
            qty[base] = new_qty
        else:  # SELL
            sells += 1
            closed += 1
            if f.price > avg_cost.get(base, 0.0):
                wins += 1
            qty[base] = max(qty.get(base, 0.0) - f.quantity, 0.0)
            if qty[base] <= 1e-12:
                avg_cost[base] = 0.0
    return buys, sells, closed, wins, buys + sells, fees


def compute_report(points: list[EquityPoint], fills: list[Fill]) -> PerformanceReport:
    """Build the full report from the equity curve and the ledger's fills."""
    if not points:
        return PerformanceReport(has_data=False, note="No equity history yet — run a cycle first.")

    values = [p.value for p in points]
    start_value, end_value = values[0], values[-1]
    strat_return = (end_value - start_value) / start_value * 100.0 if start_value else 0.0
    bench_end, bench_return, bench_syms = _benchmark(points)
    buys, sells, closed, wins, trades, fees = _trade_stats(fills)

    return PerformanceReport(
        has_data=True,
        start_epoch=points[0].epoch,
        end_epoch=points[-1].epoch,
        cycles=len(points),
        start_value=start_value,
        end_value=end_value,
        strategy_return_pct=strat_return,
        peak_value=max(values),
        max_drawdown_pct=_max_drawdown_pct(values),
        benchmark_return_pct=bench_return,
        benchmark_end_value=bench_end,
        alpha_pct=strat_return - bench_return,
        benchmark_symbols=bench_syms,
        trades=trades,
        buys=buys,
        sells=sells,
        closed_trades=closed,
        wins=wins,
        win_rate_pct=(wins / closed * 100.0) if closed else 0.0,
        fees_paid=fees,
    )
