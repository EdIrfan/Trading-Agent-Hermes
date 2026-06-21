# todo.md — Concrete build checklist

Phased, actionable steps. Maps to the roadmap in [plan.md](plan.md). Nothing here
is done yet — this pass was docs-only. Check items off as we build.

Legend: ⬜ not started · 🔧 doing · ✅ done · 🚧 blocked on a decision (see
[decisions.md](decisions.md)).

---

## Phase 0 — Foundations
- ⬜ Confirm the project name ("Hermes" placeholder) and whether the folder/repo is final. 🚧 D1
- ⬜ Initialize `Hermes/` as a git repo (separate from TradingAgents).
- ⬜ Create `pyproject.toml` for Hermes; declare dependency on `tradingagents`
      (local editable install from `../TradingAgents`).
- ⬜ Create a virtual environment; install Hermes + TradingAgents into it.
- ⬜ Smoke test: a script that does
      `TradingAgentsGraph(...).propagate("BTC-USD", today)` and prints the rating.
      Confirms the brain runs from inside Hermes. 🚧 needs an LLM API key (D5).
- ⬜ `.gitignore` (ignore `.env*`, `state/`, `__pycache__/`, caches).
- ⬜ `.env.dev` template + config loader (`config/dev.yaml`).
- ⬜ Per-environment state dirs (`state/dev/...`).
- ⬜ Hermes CLI skeleton (`hermes run/portfolio/history`) with `--env`, `--once`,
      `--dry-run` flags wired (no behavior yet).

## Phase 1 — Live data + Brain adapter
- ⬜ Binance market-data client: current price + recent candles (keyless public API). 🚧 D2
- ⬜ Symbol mapping layer (Binance `BTCUSDT` ↔ Yahoo `BTC-USD` ↔ internal).
- ⬜ Decide & implement how live price reaches the brain's market analyst
      (snapshot injection vs Binance vendor). 🚧 D3
- ⬜ `Decision` model + parser: extract rating, action, entry/stop/size hint,
      reasoning, and keep raw reports.
- ⬜ Unit tests for the parser against sample `propagate()` outputs.
- ⬜ Demo: decision grounded in the current BTC price.

## Phase 2 — Paper trading (DEV core) ⭐
- ⬜ `Broker` interface (`get_balance`, `get_price`, `place_order`, ...).
- ⬜ `PaperBroker`: simulate fills at live price + fee + optional slippage. 🚧 D6
- ⬜ Portfolio + ledger (storage choice). 🚧 D7
- ⬜ Mark-to-market valuation + realized/unrealized P&L.
- ⬜ Risk Manager:
  - ⬜ 5-tier rating → target action/weight mapping. 🚧 D4
  - ⬜ Position sizing from portfolio state + AI sizing hint.
  - ⬜ Hard guardrails: max position %, max order, min order, cooldown.
  - ⬜ Kill-switch + `--dry-run` enforcement.
- ⬜ `hermes portfolio` (balance, holdings, P&L) and `hermes history`
      (decisions + trades + reasoning).
- ⬜ Tests for broker + risk + portfolio (the money-touching code).
- ⬜ Demo: full DEV loop paper-trades BTC on live prices and reports P&L.

## Phase 3 — Scheduling & robustness
- ⬜ Scheduler/loop with `--interval`; graceful start/stop. 🚧 D8
- ⬜ Crash-safety / resume (don't double-act; reuse the brain's checkpointing).
- ⬜ Daily loss limit / circuit breaker.
- ⬜ Reconciliation routine (against paper portfolio now; Binance later).
- ⬜ Structured audit logging.

## Phase 4 — Evaluation
- ⬜ Metrics: total/period return, alpha vs buy-and-hold BTC, win rate, max drawdown.
- ⬜ Optional backtest/replay mode over historical data.
- ⬜ Simple report command/output.

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
Answer the open questions in [decisions.md](decisions.md) (especially D2, D3, D4,
D5, D6), then begin Phase 0. Nothing below Phase 0 should start before D5 (LLM
provider/key) is settled, since the brain can't run without it.
