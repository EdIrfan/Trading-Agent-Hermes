"""Translate one instrument across the three spellings Hermes touches.

    role        example      used by
    ---------   ----------   ----------------------------------------
    ccxt        BTC/USDT     ccxt market-data + order calls (Binance)
    binance     BTCUSDT      raw Binance symbol (logging / REST)
    yahoo       BTC-USD      TradingAgents brain (Yahoo-style symbol)
    base        BTC          the asset we hold in the portfolio

A symbol-mapping bug means analyzing one thing and trading another, so this is
deliberately small, explicit, and unit-tested. Quote stablecoins (USDT/USDC)
all collapse to Yahoo's USD pair, mirroring TradingAgents' own convention.
"""

from __future__ import annotations

from dataclasses import dataclass

_USD_QUOTES = ("USDT", "USDC", "USD")


@dataclass(frozen=True)
class SymbolMap:
    base: str       # BTC
    quote: str      # USDT
    ccxt: str       # BTC/USDT
    binance: str    # BTCUSDT
    yahoo: str      # BTC-USD


def parse_symbol(symbol: str) -> SymbolMap:
    """Build a :class:`SymbolMap` from any of the accepted spellings.

    Accepts ``BTC/USDT`` (ccxt), ``BTCUSDT`` (binance), or ``BTC-USD`` (yahoo).
    """
    s = symbol.strip().upper()

    if "/" in s:
        base, quote = s.split("/", 1)
    elif "-" in s:
        base, quote = s.split("-", 1)
    else:
        base, quote = _split_compact(s)

    yahoo_quote = "USD" if quote in _USD_QUOTES else quote
    return SymbolMap(
        base=base,
        quote=quote,
        ccxt=f"{base}/{quote}",
        binance=f"{base}{quote}",
        yahoo=f"{base}-{yahoo_quote}",
    )


def _split_compact(s: str) -> tuple[str, str]:
    """Split a separator-less symbol like ``BTCUSDT`` into (base, quote)."""
    for quote in sorted(_USD_QUOTES, key=len, reverse=True):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)], quote
    # Fallback: assume a 3-letter quote.
    return s[:-3], s[-3:]
