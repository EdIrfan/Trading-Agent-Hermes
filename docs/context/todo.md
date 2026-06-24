# todo.md — Concrete build checklist

Phased, actionable steps. Maps to the roadmap in [plan.md](plan.md). **Phases 0–4
are built and tested** (DEV paper-trading on live prices, real Gemini brain,
multi-asset basket, daily-loss circuit breaker, and a performance report with
alpha vs buy-and-hold). Phases 5–6 (real Binance) are deliberately not started.

Legend: ⬜ not started · 🔧 doing · ✅ done · 🚧 blocked on a decision (see
[decisions.md](decisions.md)).

---

## Phase 0 — Foundations ✅
- ✅ Project name "Hermes" (placeholder, rename trivial); local git repo separate from TradingAgents.
- ✅ `pyproject.toml`; depends on local editable `tradingagents` (`../TradingAgents`).
- ✅ Virtualenv `.venv/` with Hermes + TradingAgents installed.
- ✅ Brain smoke test — the real TradingAgents brain runs from inside Hermes (verified on Gemini).
- ✅ `.gitignore` (`.env*`, `state/`, caches), `.env.dev` template + config loader (`config/dev.yaml`).
- ✅ Per-environment state dirs (`state/dev/...`).
- ✅ Hermes CLI (`hermes run/portfolio/history/report`) with `--env`, `--once`, `--dry-run`, `--mock`, `--interval`, `--symbols`.

## Phase 1 — Live data + Brain adapter ✅
- ✅ ccxt market-data client: live price + recent candles (keyless), multi-exchange (Binance + Bybit for HYPE).
- ✅ Symbol mapping layer (`hermes/data/symbols.py`).
- ✅ Live price reaches the brain via verified-snapshot injection (option B, D3) — TradingAgents un-edited.
- ✅ `Decision` model + parser (rating, action, entry/stop/size hint, reasoning, raw reports).
- ✅ Demo: decisions grounded in the current live price (Gemini batch on BTC).

## Phase 2 — Paper trading (DEV core) ⭐ ✅
- ✅ `Broker` interface; `PaperBroker` simulates fills at live price + fee + slippage (D6).
- ✅ Portfolio + SQLite ledger (D7); mark-to-market + realized/unrealized P&L.
- ✅ Risk Manager: 5-tier rating → action (D4, `fixed_notional` default + `target_weight`);
      sizing from portfolio state; hard guardrails (per-coin cap, min order); `--dry-run` enforcement.
- ✅ `hermes portfolio` and `hermes history`.
- ✅ Tests for broker + risk + portfolio (the money-touching code).
- ✅ Demo: full DEV loop paper-trades the live basket and reports P&L.

## Phase 3 — Scheduling & robustness ✅ (mostly)
- ✅ Scheduler/loop with `--interval`; graceful Ctrl-C stop (D8).
- ✅ **Daily loss limit / circuit breaker** — portfolio-level halt, blocks buys / allows sells,
      persists per UTC day (`hermes/risk/circuit_breaker.py`, `state/<env>/breaker.json`).
- ✅ Structured audit logging — per-cycle decision+outcome JSON in `state/<env>/decisions/`.
- ⬜ Crash-safety / resume across a hard kill mid-cycle (rely on append-only ledger for now).
- ⬜ Reconciliation routine (trivial vs the paper portfolio; matters for Binance later).

## Phase 4 — Evaluation ✅ (core)
- ✅ Equity time series per cycle (`state/<env>/equity.csv`, `hermes/metrics/equity.py`).
- ✅ Metrics: total return, **alpha vs equal-weight buy-and-hold**, win rate, max drawdown, fees
      (`hermes/metrics/performance.py`).
- ✅ `hermes report` command renders it.
- ⬜ Optional backtest/replay mode over historical data (future).

## Phase 5 — TESTNET (real API, fake funds)
- ⬜ `BinanceBroker` against Binance Spot Testnet.
- ⬜ Auth, lot-size/precision handling, rate limits, idempotent client order IDs,
      error handling/retries.
- ⬜ `.env.testnet` + `config/testnet.yaml`.
- ⬜ Validate the full PROD code path with no real money.

## Phase 6 — PROD (real money) — GATED
- ⬜ `BinanceBroker` → mainnet with tiny caps.
- ⬜ Confirmation gate (`--i-understand-real-money`), refuse-on-missing-config.
- ⬜ Startup reconciliation vs real balance; refuse to trade on mismatch.
- ⬜ Monitoring/alerts (e.g. notify on each trade and on guardrail trips).
- ⬜ Read & satisfy everything in [extras.md](extras.md) (security/legal/risk).
- ⬜ Answer PROD decisions (D9, D10) before enabling.

---

## Cross-cutting / always-on
- ⬜ Keep TradingAgents un-edited; absorb all coupling in `hermes/brain/`.
- ⬜ Maintain tests alongside each money-touching component.
- ⬜ Keep these docs updated as decisions are made and code lands.

## Immediate next action
Phases 0–4 are done. Money settings now mirror the real plan: **$1,000 starting
capital, $10 fixed-notional trades**, $200 per-coin cap (`config/dev.yaml`).
The realistic next experiments, none of which need new code:
- Re-run the real Gemini brain on a fresh UTC day, ideally on a **slower cadence**
  (`--interval 4h`) so it decides on real moves, not minute-to-minute noise.
- After a few cycles, `hermes report --env dev` to see **alpha vs buy-and-hold**.
Then, only when you want real exchange wiring, start **Phase 5 (Binance testnet)** —
real API, fake funds — before anything touches real money (Phase 6, gated).
