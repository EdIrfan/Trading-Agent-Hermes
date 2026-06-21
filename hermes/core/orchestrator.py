"""One trading cycle across the basket: data → brain → risk → broker → record.

For each coin: fetch its live price, run the brain, size against the target
weight, execute (unless ``--dry-run``). Pure coordination — every piece of
business logic lives in the component it belongs to.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from hermes.brain.base import Brain
from hermes.broker.base import Broker
from hermes.core.config import Config
from hermes.core.models import Decision, Fill, Order
from hermes.data.market import MarketData
from hermes.data.snapshot import build_live_snapshot
from hermes.data.symbols import SymbolMap
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class AssetCycle:
    """What happened for one coin this cycle."""

    symbol: str
    base: str
    price: float
    decision: Decision
    risk_reason: str
    order: Order | None
    fill: Fill | None


@dataclass
class CycleResult:
    assets: list[AssetCycle] = field(default_factory=list)
    value_before: float = 0.0
    value_after: float = 0.0
    ts: float = field(default_factory=time.time)

    @property
    def fills(self) -> list[Fill]:
        return [a.fill for a in self.assets if a.fill is not None]


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
        self.symbol_maps: list[SymbolMap] = config.symbol_maps

    def run_cycle(self, *, dry_run: bool = False) -> CycleResult:
        # Fetch prices per coin; skip any coin whose feed hiccups so one bad
        # symbol can't kill the whole cycle (or a long-running loop).
        prices: dict[str, float] = {}
        active: list[SymbolMap] = []
        for m in self.symbol_maps:
            try:
                prices[m.base] = self.broker.get_price(m.ccxt)
                active.append(m)
            except Exception as e:  # noqa: BLE001 - degrade gracefully, log and continue
                logger.warning("Skipping %s this cycle: %s", m.ccxt, e)

        value_before = self.portfolio.value(prices)
        trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        assets: list[AssetCycle] = []
        for m in active:
            snapshot = build_live_snapshot(
                self.market, m, self.config.candle_timeframe, self.config.candle_lookback
            )
            decision = self.brain.decide(
                symbols=m, trade_date=trade_date, live_snapshot=snapshot,
                past_context=self._portfolio_summary(prices),
            )
            result = self.risk.decide_order(decision, self.portfolio, m, prices)
            fill: Fill | None = None
            if result.order is not None and not dry_run:
                fill = self.broker.place_order(result.order)
                self.portfolio.apply_fill(fill)
                self.ledger.record(fill)
            assets.append(AssetCycle(
                symbol=m.ccxt, base=m.base, price=prices[m.base], decision=decision,
                risk_reason=result.reason, order=result.order, fill=fill,
            ))

        if not dry_run and any(a.fill for a in assets):
            self.portfolio.save(self.config.portfolio_path)

        cycle = CycleResult(
            assets=assets, value_before=value_before,
            value_after=self.portfolio.value(prices), ts=time.time(),
        )
        self._record(cycle)
        return cycle

    def _portfolio_summary(self, prices: dict[str, float]) -> str:
        held = ", ".join(
            f"{p.quantity:.6f} {b} ({self.portfolio.weight(b, prices):.0%})"
            for b, p in self.portfolio.positions.items() if p.quantity > 0
        ) or "no coins"
        return (
            f"Current paper portfolio: cash {self.portfolio.cash:,.2f} "
            f"{self.config.quote_currency}; holding {held}; total value "
            f"{self.portfolio.value(prices):,.2f} {self.config.quote_currency}."
        )

    def _record(self, cycle: CycleResult) -> None:
        """Persist a full decision+outcome record for the audit trail."""
        self.config.decisions_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(cycle.ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.config.decisions_dir / f"{stamp}.json"
        record = {
            "ts": cycle.ts,
            "value_before": cycle.value_before,
            "value_after": cycle.value_after,
            "assets": [
                {
                    "symbol": a.symbol,
                    "price": a.price,
                    "decision": asdict(a.decision),
                    "risk_reason": a.risk_reason,
                    "order": asdict(a.order) if a.order else None,
                    "fill": asdict(a.fill) if a.fill else None,
                }
                for a in cycle.assets
            ],
        }
        path.write_text(json.dumps(record, indent=2, default=str))
