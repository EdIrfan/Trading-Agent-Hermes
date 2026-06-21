"""Deterministic fake market data for offline runs and tests.

Lets the whole DEV loop run end-to-end with no network and no API key, so the
plumbing (broker, portfolio, risk, CLI) can be exercised before the real brain
and live feed are wired in.
"""

from __future__ import annotations

import math

from .market import Candle


class FakeMarketData:
    """Generates smooth, deterministic candles around a base price."""

    def __init__(self, base_price: float = 60000.0, drift: float = 0.0):
        self.base_price = base_price
        self.drift = drift

    def get_price(self, ccxt_symbol: str) -> float:
        return self.base_price

    def get_candles(self, ccxt_symbol: str, timeframe: str, limit: int) -> list[Candle]:
        candles: list[Candle] = []
        for i in range(limit):
            wobble = math.sin(i / 7.0) * (self.base_price * 0.01)
            close = self.base_price + self.drift * i + wobble
            open_ = close - (self.base_price * 0.002)
            high = max(open_, close) + self.base_price * 0.003
            low = min(open_, close) - self.base_price * 0.003
            candles.append(
                Candle(ts=i * 3_600_000, open=open_, high=high, low=low,
                       close=close, volume=10.0 + (i % 5))
            )
        return candles
