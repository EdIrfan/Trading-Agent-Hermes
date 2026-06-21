"""One trading cycle: data → brain → risk → broker → portfolio → record.

Pure coordination — every piece of business logic lives in the component it
belongs to. ``--dry-run`` runs the whole cycle but stops short of placing the
order, printing what *would* happen (a key PROD safeguard, exercised in DEV).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from hermes.brain.base import Brain
from hermes.broker.base import Broker
from hermes.core.config import Config
from hermes.core.models import Decision, Fill, Order
from hermes.data.market import MarketData
from hermes.data.snapshot import build_live_snapshot
from hermes.data.symbols import SymbolMap, parse_symbol
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager


@dataclass
class CycleResult:
    symbol: str
    price: float
    decision: Decision
    risk_reason: str
    order: Order | None
    fill: Fill | None
    dry_run: bool
    value_before: float
    value_after: float
    ts: float


class Orchestrator:
    def __init__(
        self,
        *,
        config: Config,
        market: MarketData,
        brain: Brain,
        broker: Broker,
        risk: RiskManager,
        portfolio: Portfolio,
        ledger: Ledger,
    ):
        self.config = config
        self.market = market
        self.brain = brain
        self.broker = broker
        self.risk = risk
        self.portfolio = portfolio
        self.ledger = ledger
        self.symbols: SymbolMap = parse_symbol(config.symbol)

    def run_cycle(self, *, dry_run: bool = False) -> CycleResult:
        base = self.symbols.base
        price = self.broker.get_price(self.symbols.ccxt)
        prices = {base: price}
        value_before = self.portfolio.value(prices)

        snapshot = build_live_snapshot(
            self.market, self.symbols, self.config.candle_timeframe,
            self.config.candle_lookback,
        )
        trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        decision = self.brain.decide(
            symbols=self.symbols,
            trade_date=trade_date,
            live_snapshot=snapshot,
            past_context=self._portfolio_summary(prices),
        )

        result = self.risk.decide_order(decision, self.portfolio, self.symbols, price)
        order = result.order
        fill: Fill | None = None

        if order is not None and not dry_run:
            fill = self.broker.place_order(order)
            self.portfolio.apply_fill(fill)
            self.ledger.record(fill)
            self.portfolio.save(self.config.portfolio_path)

        value_after = self.portfolio.value({base: price})
        cycle = CycleResult(
            symbol=self.symbols.ccxt, price=price, decision=decision,
            risk_reason=result.reason, order=order, fill=fill, dry_run=dry_run,
            value_before=value_before, value_after=value_after, ts=time.time(),
        )
        self._record(cycle)
        return cycle

    def _portfolio_summary(self, prices: dict[str, float]) -> str:
        base = self.symbols.base
        return (
            f"Current paper portfolio: cash {self.portfolio.cash:,.2f} "
            f"{self.config.quote_currency}, holding {self.portfolio.quantity(base):.6f} "
            f"{base} ({self.portfolio.weight(base, prices):.0%} of value), "
            f"total value {self.portfolio.value(prices):,.2f} "
            f"{self.config.quote_currency}."
        )

    def _record(self, cycle: CycleResult) -> None:
        """Persist a full decision+outcome record for the audit trail."""
        self.config.decisions_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(cycle.ts, tz=timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        path = self.config.decisions_dir / f"{stamp}.json"
        record = {
            "ts": cycle.ts,
            "symbol": cycle.symbol,
            "price": cycle.price,
            "dry_run": cycle.dry_run,
            "decision": asdict(cycle.decision),
            "risk_reason": cycle.risk_reason,
            "order": asdict(cycle.order) if cycle.order else None,
            "fill": asdict(cycle.fill) if cycle.fill else None,
            "value_before": cycle.value_before,
            "value_after": cycle.value_after,
        }
        path.write_text(json.dumps(record, indent=2, default=str))
