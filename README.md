# Hermes

AI-driven crypto trading built on top of the **TradingAgents** multi-agent
framework. The brain (TradingAgents) decides Buy/Hold/Sell; Hermes adds the
missing half — live market data, an execution layer, a portfolio, and two
environments:

- **DEV** — paper trading (fake money) on **real live Binance prices**. Build &
  prove the strategy here. No real money can be touched.
- **PROD** — real Binance orders. Designed-for, built last.

DEV and PROD share one codebase and differ only in the **Broker** implementation.

> **[CLAUDE.md](CLAUDE.md)** — the operating contract for an AI coding agent
> driving this repo. Full design docs are in [`docs/context/`](docs/context/) —
> start with [`docs/context/README.md`](docs/context/README.md).

## Status

Phase 0–2 plumbing is in place and runs **end-to-end today** using a `MockBrain`
stand-in (so no API key is needed to test the pipeline). The real brain drops in
the moment an `ANTHROPIC_API_KEY` is configured — it's a one-line swap.

## Quick start

```bash
# From the Hermes/ directory, with TradingAgents checked out as a sibling:
python -m venv .venv && source .venv/bin/activate
pip install -e ../TradingAgents        # the brain
pip install -e .                       # Hermes + deps (ccxt, typer, ...)

cp .env.dev.example .env.dev           # add ANTHROPIC_API_KEY when ready

# Run one cycle. Without a key (or with --mock) it uses the MockBrain.
hermes run --env dev --once --dry-run --mock     # see the intent, place nothing
hermes run --env dev --once --mock               # paper-trade on live prices
hermes portfolio --env dev                        # balance + P&L
hermes history --env dev                          # recent trades

# Loop on a cadence:
hermes run --env dev --interval 4h
```

## Layout

```
hermes/
  core/        config loading, orchestrator (one cycle), component factory
  data/        ccxt Binance live price/candles, symbol mapping, live snapshot
  brain/       Decision model, MockBrain, TradingAgents adapter (live-snapshot inject)
  risk/        target-weight sizing + hard guardrails (outside the AI)
  broker/      Broker interface + PaperBroker (DEV); BinanceBroker is a later phase
  portfolio/   SQLite ledger (truth) + portfolio state + P&L
  cli/         run / portfolio / history
config/        dev.yaml (non-secret settings per environment)
state/         per-env portfolio.json, ledger.sqlite, decisions/ (gitignored)
tests/         unit + offline end-to-end smoke
```

## Testing

```bash
pytest          # runs offline; no network or API key required
```

## Safety

- DEV loads **no** trade-capable credentials, so it cannot place a real order.
- Hard guardrails (max position %, min order size, rebalance threshold) live in
  `hermes/risk/` — *outside* the AI.
- `--dry-run` computes everything and places nothing.
- Real-money brokers prompt for explicit confirmation before trading.

See [`docs/context/extras.md`](docs/context/extras.md) for the full security,
cost, and risk notes before going anywhere near PROD.
