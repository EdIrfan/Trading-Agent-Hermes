"""The Broker interface — the single seam between DEV and PROD.

Everything above the broker (brain, risk, portfolio, CLI) is identical across
environments. Only the implementation here changes: ``PaperBroker`` (DEV,
simulated fills on live prices) vs a future ``BinanceBroker`` (PROD, real
orders). See docs/context/environments.md.

Brokers are intentionally stateless about the portfolio: ``place_order``
returns a :class:`Fill`, and the caller applies it to the portfolio and ledger.
That keeps PaperBroker and BinanceBroker the same shape.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hermes.core.models import Fill, Order


@runtime_checkable
class Broker(Protocol):
    name: str

    def get_price(self, ccxt_symbol: str) -> float: ...

    def place_order(self, order: Order) -> Fill: ...
