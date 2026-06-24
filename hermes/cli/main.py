"""Hermes CLI: run the loop, inspect the portfolio, review history.

    hermes run --env dev --once [--dry-run] [--mock]
    hermes run --env dev --interval 4h
    hermes portfolio --env dev
    hermes history --env dev
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hermes.core.config import load_config
from hermes.core.factory import build_market_data, build_orchestrator
from hermes.core.orchestrator import CycleResult
from hermes.metrics.equity import EquityLog
from hermes.metrics.performance import compute_report
from hermes.portfolio.ledger import Ledger
from hermes.portfolio.portfolio import Portfolio

app = typer.Typer(help="Hermes — AI crypto trading (DEV paper / PROD Binance).", add_completion=False)
console = Console()

_INTERVAL_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_interval(value: str) -> int:
    """Parse '4h' / '30m' / '1d' into seconds."""
    value = value.strip().lower()
    unit = value[-1]
    if unit not in _INTERVAL_SECONDS:
        raise typer.BadParameter("Interval must end in s/m/h/d, e.g. 4h, 30m, 1d.")
    return int(value[:-1]) * _INTERVAL_SECONDS[unit]


@app.command()
def run(
    env: str = typer.Option("dev", help="Environment (config/<env>.yaml + .env.<env>)."),
    once: bool = typer.Option(True, help="Run a single cycle (default)."),
    interval: str | None = typer.Option(None, help="Loop on this cadence, e.g. 4h. Overrides --once."),
    dry_run: bool = typer.Option(False, help="Do everything except place the order."),
    mock: bool = typer.Option(False, help="Force the MockBrain (no LLM/API key)."),
    symbols: str | None = typer.Option(
        None, help="Override the basket for this run, e.g. 'BTC/USDT' or 'BTC/USDT,ETH/USDT'. "
                   "Handy for testing the real brain on one coin to save free-tier quota."
    ),
):
    """Run one trading cycle over the basket (or loop on --interval)."""
    config = load_config(env)
    if symbols:
        config.symbols = [s.strip() for s in symbols.split(",") if s.strip()]
    if config.broker != "paper":
        _confirm_real_money(config)

    orch = build_orchestrator(config, force_mock=mock)
    console.print(
        f"[bold]Hermes[/bold] env=[cyan]{env}[/cyan] broker=[cyan]{config.broker}[/cyan] "
        f"basket=[cyan]{', '.join(config.symbols)}[/cyan] brain=[cyan]{orch.brain.name}[/cyan]"
    )
    if orch.brain.name == "mock":
        console.print(
            "[yellow]Using MockBrain[/yellow] — no real analysis. Set ANTHROPIC_API_KEY "
            f"in .env.{env} to use the real brain."
        )

    if interval:
        seconds = _parse_interval(interval)
        console.print(f"Looping every {interval} ({seconds}s). Ctrl-C to stop.")
        try:
            while True:
                _render_cycle(orch.run_cycle(dry_run=dry_run), dry_run)
                time.sleep(seconds)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
    else:
        _render_cycle(orch.run_cycle(dry_run=dry_run), dry_run)


@app.command()
def portfolio(
    env: str = typer.Option("dev", help="Environment."),
):
    """Show balance, per-coin holdings, and P&L (marked to live prices)."""
    config = load_config(env)
    pf = Portfolio.load(
        config.portfolio_path, starting_cash=config.starting_cash,
        quote_currency=config.quote_currency,
    )
    prices = _live_prices(config, pf)

    table = Table(title=f"Portfolio — {env}")
    for col in ("asset", "quantity", "price", "value", "weight", "avg cost", "unrl P&L"):
        table.add_column(col)
    for m in config.symbol_maps:
        pos = pf.positions.get(m.base)
        qty = pos.quantity if pos else 0.0
        px = prices.get(m.base, 0.0)
        upnl = (px - (pos.avg_cost if pos else 0.0)) * qty
        table.add_row(
            m.base, f"{qty:.6f}", f"{px:,.2f}", f"{qty * px:,.2f}",
            f"{pf.weight(m.base, prices):.1%}",
            f"{(pos.avg_cost if pos else 0.0):,.2f}", _pnl(upnl),
        )
    console.print(table)

    value = pf.value(prices)
    summary = Table(show_header=False, box=None)
    summary.add_row("Cash", f"{pf.cash:,.2f} {config.quote_currency}")
    summary.add_row("Total value", f"[bold]{value:,.2f} {config.quote_currency}[/bold]")
    summary.add_row("Total return", _pnl(pf.total_return(prices) * 100, suffix="%"))
    summary.add_row("Realized P&L", _pnl(pf.realized_pnl, suffix=f" {config.quote_currency}"))
    summary.add_row("Unrealized P&L", _pnl(pf.unrealized_pnl(prices), suffix=f" {config.quote_currency}"))
    summary.add_row("Fees paid", f"{pf.fees_paid:,.2f} {config.quote_currency}")
    console.print(summary)


@app.command()
def history(
    env: str = typer.Option("dev", help="Environment."),
    limit: int = typer.Option(30, help="How many recent fills to show."),
):
    """Show recent trades from the ledger."""
    config = load_config(env)
    fills = Ledger(config.ledger_path).recent_fills(limit)
    if not fills:
        console.print("[dim]No trades yet.[/dim]")
        return
    table = Table(title=f"Recent trades — {env}")
    for col in ("time (UTC)", "side", "symbol", "qty", "price", "notional", "fee"):
        table.add_column(col)
    for f in fills:
        t = datetime.fromtimestamp(f.ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        colour = "green" if f.side.value == "BUY" else "red"
        table.add_row(
            t, f"[{colour}]{f.side.value}[/{colour}]", f.symbol,
            f"{f.quantity:.6f}", f"{f.price:,.2f}",
            f"{f.gross_notional:,.2f}", f"{f.fee:,.2f}",
        )
    console.print(table)


@app.command()
def report(
    env: str = typer.Option("dev", help="Environment."),
):
    """Performance report: return, drawdown, win-rate, and alpha vs buy-and-hold."""
    config = load_config(env)
    points = EquityLog(config.equity_path).points()
    fills = Ledger(config.ledger_path).all_fills()
    rep = compute_report(points, fills)
    if not rep.has_data:
        console.print(f"[dim]{rep.note}[/dim]")
        return

    perf = Table(title=f"Performance — {env}", show_header=False, box=None)
    perf.add_row("Window", f"{rep.cycles} cycles over {rep.duration_hours:.1f}h")
    perf.add_row("Value", f"{rep.start_value:,.2f} → [bold]{rep.end_value:,.2f}[/bold] "
                          f"{config.quote_currency}")
    perf.add_row("Strategy return", _pnl(rep.strategy_return_pct, suffix="%"))
    perf.add_row("Buy & hold return", _pnl(rep.benchmark_return_pct, suffix="%"))
    perf.add_row("[bold]Alpha (strat − B&H)[/bold]",
                 _pnl(rep.alpha_pct, suffix="%") + "  [dim](the number that matters)[/dim]")
    perf.add_row("Max drawdown", f"[red]-{rep.max_drawdown_pct:.2f}%[/red]")
    perf.add_row("Peak value", f"{rep.peak_value:,.2f} {config.quote_currency}")
    console.print(perf)

    trades = Table(show_header=False, box=None)
    trades.add_row("Trades", f"{rep.trades}  ({rep.buys} buys, {rep.sells} sells)")
    trades.add_row("Closed trades", f"{rep.closed_trades}")
    trades.add_row("Win rate", f"{rep.win_rate_pct:.0f}%  "
                               f"[dim]({rep.wins}/{rep.closed_trades} sells beat cost)[/dim]")
    trades.add_row("Fees paid", f"{rep.fees_paid:,.2f} {config.quote_currency}")
    console.print(trades)

    if rep.benchmark_symbols:
        console.print(f"[dim]Benchmark = equal-weight buy-and-hold of "
                      f"{', '.join(rep.benchmark_symbols)} over the same window.[/dim]")


# --------------------------------------------------------------------------
def _live_prices(config, pf) -> dict[str, float]:
    """Live prices for the basket; fall back to cost basis if a fetch fails."""
    try:
        market = build_market_data(config)
        return {m.base: market.get_price(m.ccxt) for m in config.symbol_maps}
    except Exception as e:  # noqa: BLE001 - report and degrade gracefully
        console.print(f"[yellow]Could not fetch live prices ({e}); using cost basis.[/yellow]")
        return {b: p.avg_cost for b, p in pf.positions.items()}


def _render_cycle(cycle: CycleResult, dry_run: bool = False) -> None:
    lines = []
    if cycle.halted:
        lines.append(f"[bold red]⛔ {cycle.halt_reason}[/bold red]")
        lines.append("")
    for a in cycle.assets:
        head = (
            f"[bold]{a.symbol}[/bold] @ {a.price:,.2f}  "
            f"[bold]{a.decision.rating}[/bold]→{a.decision.action.value}"
        )
        if a.order is not None and dry_run:
            head += (
                f"  [yellow]DRY[/yellow] would {a.order.side.value} {a.order.quantity:.6f}"
            )
        elif a.fill is not None:
            head += (
                f"  [green]{a.fill.side.value} {a.fill.quantity:.6f} @ "
                f"{a.fill.price:,.2f}[/green] (fee {a.fill.fee:,.2f})"
            )
        else:
            head += "  [dim]—[/dim]"
        lines.append(head)
    lines.append("")
    lines.append(
        f"Portfolio value: {cycle.value_before:,.2f} → "
        f"[bold]{cycle.value_after:,.2f}[/bold]"
    )
    console.print(Panel("\n".join(lines), title="Cycle", border_style="cyan"))


def _pnl(value: float, suffix: str = "") -> str:
    colour = "green" if value >= 0 else "red"
    sign = "+" if value >= 0 else ""
    return f"[{colour}]{sign}{value:,.2f}{suffix}[/{colour}]"


def _confirm_real_money(config) -> None:
    """PROD guard: refuse to trade real money without explicit acknowledgement."""
    console.print(
        "[bold red]WARNING:[/bold red] this environment uses a real-money broker "
        f"('{config.broker}')."
    )
    if not typer.confirm("Trade REAL money?", default=False):
        raise typer.Abort()


if __name__ == "__main__":
    app()
