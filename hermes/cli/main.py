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
from hermes.data.symbols import parse_symbol
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
):
    """Run one trading cycle (or loop on --interval)."""
    config = load_config(env)
    if config.broker != "paper":
        _confirm_real_money(config)

    orch = build_orchestrator(config, force_mock=mock)
    console.print(
        f"[bold]Hermes[/bold] env=[cyan]{env}[/cyan] broker=[cyan]{config.broker}[/cyan] "
        f"symbol=[cyan]{config.symbol}[/cyan] brain=[cyan]{orch.brain.name}[/cyan]"
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
                _render_cycle(orch.run_cycle(dry_run=dry_run))
                time.sleep(seconds)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
    else:
        _render_cycle(orch.run_cycle(dry_run=dry_run))


@app.command()
def portfolio(
    env: str = typer.Option("dev", help="Environment."),
):
    """Show balance, holdings, and P&L (marked to the live price)."""
    config = load_config(env)
    pf = Portfolio.load(
        config.portfolio_path, starting_cash=config.starting_cash,
        quote_currency=config.quote_currency,
    )
    symbols = parse_symbol(config.symbol)
    try:
        price = build_market_data(config).get_price(symbols.ccxt)
    except Exception as e:  # noqa: BLE001 - show why pricing failed, keep going
        console.print(f"[yellow]Could not fetch live price ({e}); using cost basis.[/yellow]")
        price = pf.positions.get(symbols.base).avg_cost if pf.positions.get(symbols.base) else 0.0

    prices = {symbols.base: price}
    value = pf.value(prices)
    table = Table(title=f"Portfolio — {env}", show_header=False, box=None)
    table.add_row("Cash", f"{pf.cash:,.2f} {config.quote_currency}")
    table.add_row(
        f"{symbols.base} held",
        f"{pf.quantity(symbols.base):.6f}  (@ {price:,.2f}, "
        f"{pf.weight(symbols.base, prices):.0%} of value)",
    )
    table.add_row("Total value", f"[bold]{value:,.2f} {config.quote_currency}[/bold]")
    table.add_row("Total return", _pnl(pf.total_return(prices) * 100, suffix="%"))
    table.add_row("Realized P&L", _pnl(pf.realized_pnl, suffix=f" {config.quote_currency}"))
    table.add_row("Unrealized P&L", _pnl(pf.unrealized_pnl(prices), suffix=f" {config.quote_currency}"))
    table.add_row("Fees paid", f"{pf.fees_paid:,.2f} {config.quote_currency}")
    console.print(table)


@app.command()
def history(
    env: str = typer.Option("dev", help="Environment."),
    limit: int = typer.Option(20, help="How many recent fills to show."),
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


# --------------------------------------------------------------------------
def _render_cycle(cycle: CycleResult) -> None:
    d = cycle.decision
    lines = [
        f"[bold]{cycle.symbol}[/bold] @ [bold]{cycle.price:,.2f}[/bold]   "
        f"brain=[cyan]{d.source}[/cyan]",
        f"Rating: [bold]{d.rating}[/bold]  →  Action: [bold]{d.action.value}[/bold]",
        "",
        f"Risk: {cycle.risk_reason}",
    ]
    if cycle.order is not None:
        if cycle.dry_run:
            lines.append(
                f"[yellow]DRY RUN[/yellow] — would {cycle.order.side.value} "
                f"{cycle.order.quantity:.6f} {cycle.symbol.split('/')[0]} (not placed)."
            )
        elif cycle.fill is not None:
            f = cycle.fill
            lines.append(
                f"[green]FILLED[/green] {f.side.value} {f.quantity:.6f} @ "
                f"{f.price:,.2f}  fee {f.fee:,.2f}  (order {f.order_id})."
            )
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
