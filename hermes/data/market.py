"""Live market data via ccxt (Binance).

Both DEV and PROD read the *same* live Binance prices — that's what makes DEV
paper results meaningful. Public market data is keyless, so this works with no
credentials; optional read-only keys raise rate limits.

``MarketData`` is a Protocol so tests (and offline runs) can substitute a
deterministic fake without a network — see tests/ and hermes/data/fake.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Candle:
    ts: int          # ms epoch
    open: float
    high: float
    low: float
    close: float
    volume: float


@runtime_checkable
class MarketData(Protocol):
    """The market-data surface Hermes depends on (price + recent candles)."""

    def get_price(self, ccxt_symbol: str) -> float: ...

    def get_candles(
        self, ccxt_symbol: str, timeframe: str, limit: int
    ) -> list[Candle]: ...


class CcxtMarketData:
    """ccxt-backed live data. Default exchange is Binance spot.

    ``ccxt`` is imported lazily so importing this module (e.g. during tests
    that use the fake) never requires the dependency to be installed.
    """

    def __init__(
        self,
        exchange: str = "binance",
        api_key: str | None = None,
        api_secret: str | None = None,
    ):
        import ccxt  # lazy

        exchange_cls = getattr(ccxt, exchange)
        params: dict = {"enableRateLimit": True}
        if api_key and api_secret:
            params.update({"apiKey": api_key, "secret": api_secret})
        self._client = exchange_cls(params)
        self.exchange = exchange

    def get_price(self, ccxt_symbol: str) -> float:
        ticker = self._client.fetch_ticker(ccxt_symbol)
        price = ticker.get("last") or ticker.get("close")
        if price is None:
            raise RuntimeError(f"No price returned for {ccxt_symbol} on {self.exchange}")
        return float(price)

    def get_candles(
        self, ccxt_symbol: str, timeframe: str, limit: int
    ) -> list[Candle]:
        rows = self._client.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit)
        return [
            Candle(ts=int(r[0]), open=float(r[1]), high=float(r[2]),
                   low=float(r[3]), close=float(r[4]), volume=float(r[5]))
            for r in rows
        ]


def build_market_data(config) -> MarketData:
    """Construct the live market-data client from a :class:`Config`."""
    return CcxtMarketData(
        exchange=config.exchange,
        api_key=config.secret("BINANCE_API_KEY"),
        api_secret=config.secret("BINANCE_API_SECRET"),
    )
