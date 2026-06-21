#!/usr/bin/env python
"""Generate demo trading data: run the DEV loop on live prices for a while.

Uses a *randomized* mock brain (weighted toward Hold) so the paper account
actually trades over time across the whole basket (BTC/ETH/SOL/BNB), producing
an equity curve, fills, and P&L we can look at — without an API key or the real
LLM. Writes to the isolated ``demo`` environment and appends one row per cycle
to ``state/demo/equity_curve.csv``.

Usage:
    python scripts/generate_demo_data.py --env demo --minutes 60 --interval 60
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from datetime import datetime, timezone

from hermes.brain.base import rating_to_action
from hermes.broker.paper import PaperBroker
from hermes.core.config import load_config
from hermes.core.models import Decision
from hermes.core.orchestrator import Orchestrator
from hermes.data.market import build_market_data
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio
from hermes.risk.manager import RiskManager

# Weighted so coins mostly hold and occasionally rebalance — less fee churn,
# more realistic activity than trading every coin every cycle.
_RATING_POOL = (
    ["Hold"] * 5 + ["Buy"] * 2 + ["Overweight"] * 2 + ["Underweight"] * 1 + ["Sell"] * 1
)


class RandomMockBrain:
    name = "mock-random"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def decide(self, *, symbols, trade_date, live_snapshot, past_context=""):
        rating = self.rng.choice(_RATING_POOL)
        return Decision(
            symbols.ccxt, rating, rating_to_action(rating),
            reasoning="Randomized mock decision (demo data generation).",
            source=self.name,
        )


def build(env: str) -> Orchestrator:
    config = load_config(env)
    config.ensure_state_dirs()
    market = build_market_data(config)
    return Orchestrator(
        config=config,
        market=market,
        brain=RandomMockBrain(),
        broker=PaperBroker(market, fee_rate=config.taker_fee_rate,
                           slippage_rate=config.slippage_rate),
        risk=RiskManager(config),
        portfolio=Portfolio.load(config.portfolio_path,
                                 starting_cash=config.starting_cash,
                                 quote_currency=config.quote_currency),
        ledger=Ledger(config.ledger_path),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="demo")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between cycles")
    args = ap.parse_args()

    orch = build(args.env)
    bases = [m.base for m in orch.symbol_maps]
    csv_path = orch.config.state_dir / "equity_curve.csv"
    fresh = not csv_path.exists()
    fh = open(csv_path, "a", newline="")  # noqa: SIM115 - held open to stream rows across the run
    writer = csv.writer(fh)
    if fresh:
        header = ["ts_utc", "value", "cash", "return_pct", "trades"]
        header += [f"{b}_px" for b in bases] + [f"{b}_qty" for b in bases]
        writer.writerow(header)

    deadline = time.time() + args.minutes * 60.0
    cycle = 0
    total_trades = 0
    print(f"Generating demo data: env={args.env} basket={bases} for "
          f"{args.minutes:g} min every {args.interval:g}s. CSV -> {csv_path}", flush=True)

    while time.time() < deadline:
        cycle += 1
        try:
            res = orch.run_cycle(dry_run=False)
            prices = {a.base: a.price for a in res.assets}
            n_trades = len(res.fills)
            total_trades += n_trades
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ret = orch.portfolio.total_return(prices) * 100
            row = [ts, f"{res.value_after:.2f}", f"{orch.portfolio.cash:.2f}",
                   f"{ret:.3f}", n_trades]
            row += [f"{prices[b]:.2f}" for b in bases]
            row += [f"{orch.portfolio.quantity(b):.6f}" for b in bases]
            writer.writerow(row)
            fh.flush()
            traded = ", ".join(
                f"{f.side.value} {f.symbol.split('/')[0]}" for f in res.fills
            ) or "—"
            print(f"[{cycle:03d}] {ts} value={res.value_after:,.2f} "
                  f"ret={ret:+.2f}% trades={n_trades} [{traded}]", flush=True)
        except Exception as e:  # noqa: BLE001 - keep the run alive on a transient error
            print(f"[{cycle:03d}] error (continuing): {e}", flush=True)

        if time.time() < deadline:
            time.sleep(args.interval)

    fh.close()
    final_prices = {m.base: orch.broker.get_price(m.ccxt) for m in orch.symbol_maps}
    print(f"DONE: {cycle} cycles, {total_trades} trades. "
          f"Final value {orch.portfolio.value(final_prices):,.2f} "
          f"{orch.config.quote_currency}. CSV at {csv_path}", flush=True)


if __name__ == "__main__":
    main()
