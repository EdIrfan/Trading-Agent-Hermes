"""Daily-loss circuit breaker — the autonomous-trading kill switch.

A bot that decides on its own needs a hard floor that no AI decision can argue
its way past: if the portfolio falls more than ``max_daily_loss_pct`` below the
day's opening value, stop opening or adding to positions for the rest of the UTC
day. This lives *outside* the brain and even outside the per-coin risk sizing —
it's a portfolio-level halt, the last line of defence against a bad model day or
a flash crash.

What "tripped" does (deliberately asymmetric):
- **Blocks BUYs** — no new risk, no averaging down.
- **Allows SELLs** — closing/trimming reduces exposure, which is the whole point;
  a halt should never trap you in a losing position.

State is a tiny JSON file (``state/<env>/breaker.json``) so the halt and the day's
reference value survive process restarts within the same day. At the first cycle
of a new UTC day the reference resets to that day's opening value and the breaker
re-arms.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class BreakerState:
    day: str = ""              # UTC date "YYYY-MM-DD" the reference value belongs to
    day_open_value: float = 0.0  # portfolio value at the first cycle of that day
    tripped: bool = False
    tripped_at: float | None = None  # epoch when it tripped (for the audit trail)


@dataclass
class BreakerCheck:
    """The verdict for one cycle."""

    allow_buys: bool
    tripped: bool
    drawdown_pct: float        # current intraday drawdown (0..1, positive = down)
    day_open_value: float
    reason: str


class CircuitBreaker:
    """Portfolio-level daily-loss halt with persisted, self-resetting state."""

    def __init__(self, path: Path, *, max_daily_loss_pct: float, enabled: bool = True):
        self.path = path
        self.max_daily_loss_pct = max_daily_loss_pct
        self.enabled = enabled
        self.state = self._load()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load(self) -> BreakerState:
        if not self.path.exists():
            return BreakerState()
        try:
            return BreakerState(**json.loads(self.path.read_text()))
        except (ValueError, TypeError):
            return BreakerState()  # corrupt/old file: start clean rather than crash

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state.__dict__, indent=2))

    def check(self, value: float, *, now: datetime | None = None) -> BreakerCheck:
        """Evaluate the breaker against the current portfolio ``value`` and persist.

        Call once per cycle, before sizing orders. Returns whether buys are allowed.
        """
        today = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")

        # New UTC day (or first ever run): re-anchor and re-arm.
        if self.state.day != today:
            self.state = BreakerState(day=today, day_open_value=value, tripped=False)
            self._save()

        if not self.enabled:
            return BreakerCheck(True, False, 0.0, self.state.day_open_value,
                                "circuit breaker disabled")

        open_value = self.state.day_open_value or value
        drawdown = (open_value - value) / open_value if open_value > 0 else 0.0

        if not self.state.tripped and drawdown >= self.max_daily_loss_pct:
            self.state.tripped = True
            self.state.tripped_at = (now or datetime.now(timezone.utc)).timestamp()
            self._save()

        if self.state.tripped:
            return BreakerCheck(
                allow_buys=False, tripped=True, drawdown_pct=drawdown,
                day_open_value=open_value,
                reason=(f"DAILY LOSS HALT: down {drawdown:.2%} from the day's open "
                        f"{open_value:,.2f} (limit {self.max_daily_loss_pct:.0%}); "
                        f"buys blocked until {today} UTC ends, sells still allowed."),
            )
        return BreakerCheck(
            allow_buys=True, tripped=False, drawdown_pct=drawdown,
            day_open_value=open_value,
            reason=(f"ok: intraday drawdown {drawdown:.2%} "
                    f"(limit {self.max_daily_loss_pct:.0%})"),
        )
