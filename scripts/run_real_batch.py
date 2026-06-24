#!/usr/bin/env python
"""Run the REAL brain on a symbol repeatedly until the daily LLM quota runs out.

Each run is a full multi-agent analysis (real TradingAgents brain on Gemini),
paper-traded into the env's portfolio. Logs one row per run to
``state/<env>/real_runs.csv`` and stops cleanly on a per-DAY quota error. Other
errors (transient throttles, source 429s) are logged and the loop waits, then
continues.

Usage:
    python scripts/run_real_batch.py --env dev --symbols BTC/USDT --max-runs 60
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone

from hermes.core.config import load_config
from hermes.core.factory import build_orchestrator


def quota_kind(err: Exception) -> str | None:
    """Classify a Gemini quota error: 'daily' (stop) vs 'rate' (wait) vs None."""
    s = str(err).lower()
    if "perday" in s or "per day" in s or "requestsperday" in s:
        return "daily"
    if "resource_exhausted" in s or "429" in s or "quota" in s:
        return "rate"
    return None


def _summary_line(reasoning: str) -> str:
    """First meaningful line of the PM's reasoning, for the log."""
    for line in reasoning.splitlines():
        line = line.strip().lstrip("*# ").strip()
        if line and not line.lower().startswith("rating"):
            return line[:140]
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="dev")
    ap.add_argument("--symbols", default="BTC/USDT")
    ap.add_argument("--max-runs", type=int, default=60)
    args = ap.parse_args()

    config = load_config(args.env)
    config.symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    orch = build_orchestrator(config, force_mock=False)
    print(f"env={args.env} symbols={config.symbols} brain={orch.brain.name} "
          f"model={config.deep_think_llm}", flush=True)
    if orch.brain.name != "tradingagents":
        print("ERROR: real brain not selected (is GOOGLE_API_KEY set in .env."
              f"{args.env}?). Got '{orch.brain.name}'. Aborting.", flush=True)
        return

    csv_path = config.state_dir / "real_runs.csv"
    fresh = not csv_path.exists()
    fh = open(csv_path, "a", newline="")  # noqa: SIM115 - streamed across the batch
    writer = csv.writer(fh)
    if fresh:
        writer.writerow(["run", "ts_utc", "secs", "symbol", "price", "rating",
                         "action", "traded", "value", "cash", "summary"])

    completed = 0
    rate_waits = 0
    for run in range(1, args.max_runs + 1):
        t0 = time.time()
        try:
            cycle = orch.run_cycle(dry_run=False)
        except Exception as e:  # noqa: BLE001 - classify and decide whether to stop
            kind = quota_kind(e)
            if kind == "daily":
                print(f"[{run:02d}] DAILY QUOTA EXHAUSTED — stopping after "
                      f"{completed} completed runs.", flush=True)
                break
            if kind == "rate":
                rate_waits += 1
                if rate_waits > 8:
                    print(f"[{run:02d}] persistent rate-limit; stopping.", flush=True)
                    break
                print(f"[{run:02d}] per-minute throttle; waiting 60s…", flush=True)
                time.sleep(60)
                continue
            print(f"[{run:02d}] error (continuing): {type(e).__name__}: {str(e)[:120]}",
                  flush=True)
            time.sleep(10)
            continue

        a = cycle.assets[0]
        traded = a.fill is not None
        completed += 1
        secs = time.time() - t0
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        summary = _summary_line(a.decision.reasoning)
        writer.writerow([run, ts, f"{secs:.0f}", a.symbol, f"{a.price:.2f}",
                         a.decision.rating, a.decision.action.value, traded,
                         f"{cycle.value_after:.2f}", f"{orch.portfolio.cash:.2f}", summary])
        fh.flush()
        mark = "TRADE" if traded else "----"
        fill = (f" {a.fill.side.value} {a.fill.quantity:.6f}@{a.fill.price:,.2f}"
                if a.fill else "")
        print(f"[{run:02d}] {mark} {a.decision.rating:<11}->{a.decision.action.value:<4}"
              f"{fill}  value={cycle.value_after:,.2f}  ({secs:.0f}s)", flush=True)

    fh.close()
    base = orch.symbol_maps[0].base
    print(f"DONE: {completed} completed runs. Cash {orch.portfolio.cash:,.2f} USDT, "
          f"{base} held {orch.portfolio.quantity(base):.6f}. CSV at {csv_path}",
          flush=True)


if __name__ == "__main__":
    main()
