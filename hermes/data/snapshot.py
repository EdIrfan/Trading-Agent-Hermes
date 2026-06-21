"""Build a verified live-price snapshot to anchor the brain on current data.

TradingAgents was built around *daily, historical* candles. To make it reason
about *now*, Hermes injects a compact snapshot of the current live price and a
few recent candles into the run (decision D3 — least-invasive option; the
brain's own data vendors are left untouched). This is the seam where Hermes's
live Binance feed reaches the brain.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .market import MarketData
from .symbols import SymbolMap


def build_live_snapshot(
    market: MarketData, symbols: SymbolMap, timeframe: str, lookback: int
) -> str:
    """Return a markdown snapshot of the current price + recent candles."""
    price = market.get_price(symbols.ccxt)
    candles = market.get_candles(symbols.ccxt, timeframe, min(lookback, 30))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    recent = candles[-10:]
    lines = [
        f"### Verified Live Market Snapshot — {symbols.ccxt} (Binance)",
        f"As of {now}, the current price of {symbols.base} is "
        f"**{price:,.2f} {symbols.quote}**. This is live exchange data; treat it "
        f"as the authoritative current price and do not contradict it.",
        "",
        f"Most recent {len(recent)} {timeframe} candles (oldest first):",
        "",
        "| time (UTC) | open | high | low | close | volume |",
        "|---|---|---|---|---|---|",
    ]
    for c in recent:
        t = datetime.fromtimestamp(c.ts / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
        lines.append(
            f"| {t} | {c.open:,.2f} | {c.high:,.2f} | {c.low:,.2f} "
            f"| {c.close:,.2f} | {c.volume:,.2f} |"
        )
    return "\n".join(lines)


def latest_price(market: MarketData, symbols: SymbolMap) -> float:
    return market.get_price(symbols.ccxt)
