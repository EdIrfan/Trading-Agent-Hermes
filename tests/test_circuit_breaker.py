"""The daily-loss circuit breaker: arms per UTC day, trips on drawdown, persists."""

from datetime import datetime, timezone

from hermes.risk.circuit_breaker import CircuitBreaker

DAY = datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc)
NEXT_DAY = datetime(2026, 6, 23, 9, 0, tzinfo=timezone.utc)


def _breaker(tmp_path, pct=0.05, enabled=True):
    return CircuitBreaker(tmp_path / "breaker.json", max_daily_loss_pct=pct, enabled=enabled)


def test_first_cycle_anchors_the_day_and_allows_buys(tmp_path):
    cb = _breaker(tmp_path)
    chk = cb.check(1000.0, now=DAY)
    assert chk.allow_buys and not chk.tripped
    assert chk.day_open_value == 1000.0


def test_small_drawdown_does_not_trip(tmp_path):
    cb = _breaker(tmp_path, pct=0.05)
    cb.check(1000.0, now=DAY)
    chk = cb.check(970.0, now=DAY)  # -3%, under the 5% limit
    assert chk.allow_buys and not chk.tripped


def test_breach_trips_and_blocks_buys(tmp_path):
    cb = _breaker(tmp_path, pct=0.05)
    cb.check(1000.0, now=DAY)
    chk = cb.check(940.0, now=DAY)  # -6%, over the limit
    assert chk.tripped and not chk.allow_buys
    assert "HALT" in chk.reason


def test_stays_tripped_even_if_it_recovers_same_day(tmp_path):
    cb = _breaker(tmp_path, pct=0.05)
    cb.check(1000.0, now=DAY)
    cb.check(940.0, now=DAY)             # trips
    chk = cb.check(990.0, now=DAY)       # recovers, but the day stays halted
    assert chk.tripped and not chk.allow_buys


def test_persists_tripped_state_across_instances(tmp_path):
    cb = _breaker(tmp_path, pct=0.05)
    cb.check(1000.0, now=DAY)
    cb.check(940.0, now=DAY)
    reloaded = _breaker(tmp_path, pct=0.05)  # new process, same day
    chk = reloaded.check(950.0, now=DAY)
    assert chk.tripped and not chk.allow_buys


def test_new_utc_day_rearms(tmp_path):
    cb = _breaker(tmp_path, pct=0.05)
    cb.check(1000.0, now=DAY)
    cb.check(940.0, now=DAY)             # tripped on day 1
    chk = cb.check(940.0, now=NEXT_DAY)  # day 2 re-anchors at 940, fresh
    assert chk.allow_buys and not chk.tripped
    assert chk.day_open_value == 940.0


def test_disabled_breaker_never_blocks(tmp_path):
    cb = _breaker(tmp_path, pct=0.05, enabled=False)
    cb.check(1000.0, now=DAY)
    chk = cb.check(500.0, now=DAY)  # -50% and still allowed
    assert chk.allow_buys and not chk.tripped
