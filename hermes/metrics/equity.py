"""The equity time series — one row per trading cycle.

Every cycle the orchestrator appends the marked-to-market portfolio value (plus
cash and the live basket prices) to ``state/<env>/equity.csv``. That series is
what powers the performance report: the return curve, the max-drawdown, and the
buy-and-hold benchmark (which needs each coin's price at the start and end of the
window). The SQLite ledger remains the source of truth for *trades*; this file is
the source of truth for *value over time*.

Prices are stored as a JSON blob in one column so the schema doesn't change when
the basket does (adding HYPE shouldn't rewrite the header).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HEADER = ["ts_utc", "epoch", "value", "cash", "prices_json"]


@dataclass(frozen=True)
class EquityPoint:
    epoch: float
    value: float
    cash: float
    prices: dict[str, float]

    @property
    def when(self) -> datetime:
        return datetime.fromtimestamp(self.epoch, tz=timezone.utc)


class EquityLog:
    """Append-only CSV of portfolio value over time."""

    def __init__(self, path: Path):
        self.path = path

    def append(
        self,
        *,
        value: float,
        cash: float,
        prices: dict[str, float],
        epoch: float | None = None,
    ) -> None:
        epoch = epoch if epoch is not None else datetime.now(timezone.utc).timestamp()
        ts = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="") as fh:
            writer = csv.writer(fh)
            if fresh:
                writer.writerow(_HEADER)
            writer.writerow([ts, f"{epoch:.0f}", f"{value:.2f}", f"{cash:.2f}",
                             json.dumps(prices, separators=(",", ":"))])

    def points(self) -> list[EquityPoint]:
        if not self.path.exists():
            return []
        out: list[EquityPoint] = []
        with self.path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    out.append(EquityPoint(
                        epoch=float(row["epoch"]),
                        value=float(row["value"]),
                        cash=float(row["cash"]),
                        prices=json.loads(row["prices_json"] or "{}"),
                    ))
                except (KeyError, ValueError):
                    continue  # skip a malformed/partial row rather than crash a report
        return out
