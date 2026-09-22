# CLAUDE.md — Agent operating contract for Hermes

You (an AI coding agent — Claude, Codex, Cursor, Copilot, or otherwise) are
working on **Hermes**: an AI-driven crypto **paper/live trading** system built
on top of the **TradingAgents** multi-agent framework (`../TradingAgents/`).
This file is your entry point. Read it fully, then read
[docs/context/README.md](docs/context/README.md) — the full map — before doing
anything.

## What this project is (30 seconds)

TradingAgents is a research tool: give it a ticker and a date and a team of AI
agents debates and produces a Buy/Hold/Sell-style recommendation. It talks; it
does not trade. **Hermes** turns that recommendation into action: it feeds the
brain **live crypto prices** (via ccxt/Binance), takes the decision, and places
orders — against a simulated paper account in **DEV** (fake money, real live
data) or against Binance in **PROD** (real money, only once DEV has earned
trust).

## Where the knowledge lives

Start at [docs/context/README.md](docs/context/README.md) — it is the map for
this whole project (glossary, architecture, DEV/PROD design, plan, open
decisions, todo checklist, and cost/risk gotchas) and is written for anyone —
agent or human — who has not seen this repo before.

## The rules that are non-negotiable

1. **DEV loads no trade-capable credentials.** It cannot place a real order,
   full stop. Real-money code paths live only behind explicit PROD
   configuration.
2. **Hard guardrails live outside the AI**, in `hermes/risk/` (max position %,
   min order size, rebalance threshold). Never let the brain's recommendation
   bypass them.
3. **Never edit TradingAgents.** It's an installed library. All coupling to it
   lives in `hermes/brain/`. Keeping it pristine lets us pull upstream.
4. **`--dry-run` must compute everything and place nothing.** Keep it that way.
5. **Money-touching and integrity code gets tests.** `pytest` runs fully
   offline — no network or API key required.
6. **Secrets only in `.env.<env>`** (gitignored). Never commit keys.
7. **The docs are the source of truth.** If you discover something that
   contradicts `docs/context/`, update the doc (note the date) in the same
   change — don't let code and docs drift.

## On-disk layout you can rely on

```
GitHub/Trading Agent/
├── TradingAgents/   # the brain (do not edit)
├── Hermes/          # THIS repo: v1, live/paper trading
│   ├── CLAUDE.md            # you are here
│   ├── docs/context/        # the full map (source of truth)
│   ├── hermes/               # the package
│   ├── config/               # dev.yaml etc.
│   ├── state/                # portfolio/ledger/equity (gitignored)
│   └── tests/
└── Hermes-v2/       # sibling: backtesting evolution of this repo
```

If anything here is stale, trust the code and fix this file.
