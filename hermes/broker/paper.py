"""PaperBroker — DEV execution: simulate fills at the live price.

Fills against the *real* current Binance price (so paper P&L tracks reality),
plus modeled slippage and the Binance taker fee (decision D6) so results aren't
unrealistically rosy. Places no real orders and holds no trade credentials — by
construction it cannot touch real money.
"""

from __future__ import annotations

import uuid

from hermes.core.models import Fill, Order, Side
from hermes.data.market import MarketData


class PaperBroker:
    name = "paper"

    def __init__(
        self,
        market: MarketData,
        *,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ):
        self.market = market
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def get_price(self, ccxt_symbol: str) -> float:
        return self.market.get_price(ccxt_symbol)

    def place_order(self, order: Order) -> Fill:
        mid = self.market.get_price(order.symbol)
        # Market orders pay the spread/slippage: buys fill a touch high, sells low.
        if order.side is Side.BUY:
            fill_price = mid * (1.0 + self.slippage_rate)
        else:
            fill_price = mid * (1.0 - self.slippage_rate)

        fee = fill_price * order.quantity * self.fee_rate
        return Fill(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            fee=fee,
            order_id=order.client_order_id or f"paper-{uuid.uuid4().hex[:12]}",
            broker=self.name,
        )
