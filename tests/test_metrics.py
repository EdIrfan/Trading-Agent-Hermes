"""Performance metrics: equity-log round-trip, drawdown, and alpha vs buy-and-hold."""

from hermes.core.models import Fill, Side
from hermes.metrics.equity import EquityLog, EquityPoint
from hermes.metrics.performance import compute_report


def _pt(epoch, value, prices):
    return EquityPoint(epoch=epoch, value=value, cash=0.0, prices=prices)


def test_equity_log_round_trip(tmp_path):
    log = EquityLog(tmp_path / "equity.csv")
    log.append(value=1000.0, cash=900.0, prices={"BTC": 100.0}, epoch=1000.0)
    log.append(value=1100.0, cash=900.0, prices={"BTC": 110.0}, epoch=2000.0)
    pts = log.points()
    assert [p.value for p in pts] == [1000.0, 1100.0]
    assert pts[0].prices["BTC"] == 100.0


def test_no_data_report():
    rep = compute_report([], [])
    assert not rep.has_data


def test_return_drawdown_and_benchmark():
    # Value dips to 900 mid-window then ends at 1100; BTC 100 -> 110.
    points = [
        _pt(1000.0, 1000.0, {"BTC": 100.0}),
        _pt(2000.0, 900.0, {"BTC": 90.0}),
        _pt(3000.0, 1100.0, {"BTC": 110.0}),
    ]
    rep = compute_report(points, [])
    assert rep.has_data
    assert round(rep.strategy_return_pct, 6) == 10.0          # 1000 -> 1100
    assert round(rep.max_drawdown_pct, 6) == 10.0             # peak 1000 -> trough 900
    # Equal-weight buy-and-hold of just BTC: also +10% -> zero alpha here.
    assert round(rep.benchmark_return_pct, 6) == 10.0
    assert round(rep.alpha_pct, 6) == 0.0
    assert rep.benchmark_symbols == ["BTC"]


def test_alpha_positive_when_strategy_beats_hold():
    # Portfolio +10% while BTC only +5% -> +5% alpha (the AI added value).
    points = [
        _pt(1000.0, 1000.0, {"BTC": 100.0}),
        _pt(2000.0, 1100.0, {"BTC": 105.0}),
    ]
    rep = compute_report(points, [])
    assert round(rep.strategy_return_pct, 6) == 10.0
    assert round(rep.benchmark_return_pct, 6) == 5.0
    assert round(rep.alpha_pct, 6) == 5.0


def test_win_rate_from_replayed_fills():
    fills = [
        Fill("BTC/USDT", Side.BUY, 1.0, 100.0, 0.1),
        Fill("BTC/USDT", Side.SELL, 1.0, 110.0, 0.1),   # win: 110 > 100
        Fill("ETH/USDT", Side.BUY, 1.0, 100.0, 0.1),
        Fill("ETH/USDT", Side.SELL, 1.0, 90.0, 0.1),    # loss: 90 < 100
    ]
    points = [_pt(1000.0, 1000.0, {"BTC": 100.0}), _pt(2000.0, 1000.0, {"BTC": 100.0})]
    rep = compute_report(points, fills)
    assert rep.trades == 4 and rep.buys == 2 and rep.sells == 2
    assert rep.closed_trades == 2 and rep.wins == 1
    assert round(rep.win_rate_pct, 6) == 50.0
    assert round(rep.fees_paid, 6) == 0.4
