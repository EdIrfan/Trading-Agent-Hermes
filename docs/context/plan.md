# plan.md — Hermes architecture & phased roadmap

How Hermes is structured and the order we build it. This is a *proposed* design,
not yet code. Open choices are flagged and collected in [decisions.md](decisions.md).

Read [explanation.md](explanation.md), [context.md](context.md), and
[environments.md](environments.md) first — this assumes them.

---

## 1. Design goals (what "good" means here)

1. **Don't fork the brain.** Use TradingAgents as an installed library; never edit
   it (so we can pull upstream updates). All Hermes logic lives in `Hermes/`.
2. **One swap between DEV and PROD.** The `Broker` interface is the only thing that
   changes. Everything else is shared.
3. **Safe by construction.** DEV cannot touch real money (no trade credentials
   loaded). Guardrails live outside the AI.
4. **Auditable.** Every decision and trade is logged with its reasoning.
5. **Boring and testable.** Plain Python, typed interfaces, unit tests around the
   money-touching parts, mirroring TradingAgents' own strong test culture.

---

## 2. The component map

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes (the application)                                            │
│                                                                      │
│  ┌────────────┐   ┌───────────────┐   ┌──────────────────────────┐  │
│  │  Scheduler │──▶│   Orchestrator │──▶│  Brain Adapter           │  │
│  │ (loop/cron)│   │ (one cycle)    │   │  wraps TradingAgentsGraph │  │
│  └────────────┘   └───────┬────────┘   │  .propagate() → decision │  │
│                           │            └──────────┬───────────────┘  │
│                           │                       │ (live data in)   │
│                           ▼                       ▼                  │
│                   ┌───────────────┐      ┌──────────────────┐        │
│                   │  Risk Manager │      │  Market Data      │        │
│                   │  (sizing +    │      │  (Binance live)   │        │
│                   │   guardrails) │      └──────────────────┘        │
│                   └───────┬───────┘                                   │
│                           ▼                                           │
│                   ┌───────────────┐      ┌──────────────────┐         │
│                   │    Broker     │─────▶│   Portfolio /    │         │
│                   │  (interface)  │      │   Ledger         │         │
│                   └───────┬───────┘      └──────────────────┘         │
│              ┌────────────┴────────────┐                              │
│              ▼                         ▼                              │
│      PaperBroker (DEV)        BinanceBroker (PROD/TESTNET)            │
└─────────────────────────────────────────────────────────────────────┘
              │                         │
              ▼                         ▼
       (local simulator)        (Binance API)
```

---

## 3. Component responsibilities

### 3.1 Market Data (`hermes/data/`)
- Fetch **live** Binance prices and recent candles (keyless public API).
- Provide a "current price" and a small recent-history window.
- **Symbol mapping:** Binance `BTCUSDT` ↔ Yahoo `BTC-USD` ↔ TradingAgents internal.
  Extend/reuse `tradingagents/dataflows/symbol_utils.py` conventions.
- **Feed the brain:** make the live price reach TradingAgents' market analyst.
  Two options (decide in [decisions.md](decisions.md)):
  - **(A) Binance vendor inside TradingAgents config** — register a `binance`
    vendor in `data_vendors`. Cleanest data-wise but touches the brain's config.
  - **(B) Inject a verified live snapshot** — pass current price/indicators into
    the run via the existing `get_verified_market_snapshot` / instrument-context
    mechanism, leaving the brain's vendors untouched. Less invasive.
  - Likely start with **(B)** for minimal coupling; revisit.

### 3.2 Brain Adapter (`hermes/brain/`)
- Thin wrapper around `TradingAgentsGraph`.
- Builds the per-environment `config` dict (model, rounds, memory path).
- Calls `.propagate(symbol, today, asset_type="crypto")`.
- Parses the result into a clean `Decision` object:
  `{rating, action, entry_price, stop_loss, position_sizing_hint, reasoning, raw_reports}`.
- This is the *only* place that knows TradingAgents' internals, so upstream
  changes are absorbed here.

### 3.3 Risk Manager (`hermes/risk/`)
- Translate the AI's words ("Buy", "Overweight", "5% of portfolio") into a
  **concrete order quantity** given current portfolio state.
- Enforce **hard guardrails** (independent of the AI): max position %, max order
  size, daily loss limit, cooldown between trades, min order size, kill-switch.
- Decide the **5-tier → action mapping** (e.g. Buy/Overweight → increase toward a
  target weight; Underweight/Sell → reduce; Hold → no-op). Exact mapping is a
  decision (see [decisions.md](decisions.md)).
- Long-only and spot-only to start.

### 3.4 Broker (`hermes/broker/`) — the DEV/PROD seam
A single interface, e.g.:

```python
class Broker(Protocol):
    def get_balance(self) -> Balance: ...
    def get_price(self, symbol: str) -> float: ...
    def place_order(self, order: Order) -> Fill: ...
    def get_open_orders(self) -> list[Order]: ...
    def cancel(self, order_id: str) -> None: ...
```

- **`PaperBroker`** — fills against the live price (+ modeled fee/slippage),
  updates the local portfolio/ledger. Pure local logic. **DEV.**
- **`BinanceBroker`** — signs and sends real orders; reads real balance; handles
  Binance lot-size/precision, rate limits, idempotent client order IDs, errors.
  Targets testnet or mainnet by config. **TESTNET/PROD.**

### 3.5 Portfolio / Ledger (`hermes/portfolio/`)
- Track cash + holdings; append every fill to an immutable **ledger**.
- Compute realized/unrealized P&L, current value, returns, drawdown.
- **Reconcile** (PROD) against Binance's reported balance on startup.
- Per-environment isolated storage (`state/dev/`, `state/prod/`).

### 3.6 Orchestrator (`hermes/core/`)
- Runs **one cycle**: fetch data → run brain → size & risk-check → place order →
  record. Pure coordination; no business logic of its own.
- Supports `--dry-run` (do everything except actually place the order).

### 3.7 Scheduler (`hermes/scheduler/` or external)
- Run the orchestrator on a cadence (`--interval 4h`) or once (`--once`).
- Could be a simple Python loop, OS cron, or Claude Code `/schedule`/`/loop`.
  Decide later; start with a simple loop + `--once`.

### 3.8 CLI (`hermes/cli/`)
- `hermes run --env dev --symbol BTCUSDT [--interval 4h | --once] [--dry-run]`
- `hermes portfolio --env dev` — show balance, holdings, P&L.
- `hermes history --env dev` — list decisions + trades with reasoning.
- `hermes backtest ...` — later.
- Built with Typer + Rich (same stack TradingAgents' CLI uses).

### 3.9 Storage & logging (`hermes/store/`)
- Decisions, fills, and portfolio snapshots persisted per environment.
- Likely: JSON for portfolio snapshots + decisions, SQLite for the ledger.
  (Decide in [decisions.md](decisions.md).)

---

## 4. Proposed directory layout

```
Hermes/
├── pyproject.toml              # Hermes package; depends on tradingagents (local path)
├── README.md
├── .gitignore                  # ignores .env*, state/, __pycache__
├── .env.dev / .env.prod / .env.testnet   # secrets (gitignored)
├── config/
│   ├── dev.yaml / prod.yaml / testnet.yaml
├── docs/
│   └── context/                # ← these docs
├── hermes/
│   ├── cli/                    # Typer app: run/portfolio/history
│   ├── core/                   # orchestrator (one cycle), config loading
│   ├── brain/                  # TradingAgents adapter → Decision
│   ├── data/                   # Binance live data + symbol mapping
│   ├── risk/                   # sizing + guardrails + kill-switch
│   ├── broker/                 # Broker interface, PaperBroker, BinanceBroker
│   ├── portfolio/              # ledger, P&L, reconciliation
│   └── store/                  # persistence helpers
├── state/                      # per-env portfolios/ledgers/decisions (gitignored)
└── tests/                      # unit tests, esp. broker + risk + portfolio
```

How Hermes depends on the brain (in `pyproject.toml`):

```toml
[project]
dependencies = [
  "tradingagents",          # the brain
  "python-binance",         # or ccxt — see decisions.md
  "typer", "rich", "pydantic", "pyyaml", "python-dotenv",
]
[tool.uv.sources]            # or pip editable install
tradingagents = { path = "../TradingAgents", editable = true }
```

---

## 5. Phased roadmap

Each phase is independently demoable. **We start at Phase 0/1; PROD is late.**

### Phase 0 — Foundations (no trading yet)
- Create the Hermes package, `pyproject.toml`, install TradingAgents as a local
  editable dependency, confirm `from tradingagents... import TradingAgentsGraph`
  works and we can run one `.propagate()` end-to-end.
- Set up `.env.dev`, config loading, per-env state dirs, `.gitignore`.
- **Demo:** `hermes run --env dev --symbol BTCUSDT --once --dry-run` runs the
  brain on live-ish data and prints the decision. No portfolio yet.

### Phase 1 — Live data + Brain adapter
- Binance live price + recent candles; symbol mapping; feed the brain.
- `Decision` parser (rating + action + entry/stop/size + reasoning).
- **Demo:** decision is grounded in the *current* BTC price.

### Phase 2 — Paper trading (DEV core) ⭐ the main milestone
- `PaperBroker`, portfolio/ledger, fee/slippage model, mark-to-market.
- Risk manager: 5-tier→action mapping, position sizing, hard guardrails,
  kill-switch, dry-run.
- `hermes portfolio` and `hermes history`.
- **Demo:** a full DEV loop that paper-trades BTC on live prices and shows P&L.

### Phase 3 — Scheduling & robustness
- Scheduler/loop with `--interval`; crash-safety; resume; daily loss limit;
  reconciliation logic (works against the paper portfolio first).
- Richer logging/audit trail.
- **Demo:** leave it running for days; review the decision/trade history.

### Phase 4 — Evaluation
- Metrics: total/period return, alpha vs buy-and-hold BTC, win rate, drawdown.
- Optionally wire up real **backtesting** (the unused `backtrader` dep, or a
  custom replay) to test over history fast.
- **Demo:** "here's how the strategy did over N weeks of paper trading."

### Phase 5 — TESTNET (real API, fake funds)
- `BinanceBroker` against Binance Spot Testnet; auth, order formatting, error
  handling, rate limits, idempotency.
- **Demo:** the exact PROD code path works end-to-end with no real money.

### Phase 6 — PROD (real money, gated & capped)
- `BinanceBroker` → mainnet, tiny caps, confirmation gate, full safeguards,
  monitoring/alerts.
- **Only after** DEV + TESTNET have earned trust and you've read
  [extras.md](extras.md) (security/legal/risk) and answered the PROD decisions.

---

## 6. What we deliberately defer

- Shorting, leverage, futures (start long-only spot).
- Multiple simultaneous assets / portfolio optimization (start single-asset).
- Web dashboard / GUI (start CLI).
- WebSocket streaming (start REST polling).
- Fine-tuning the brain's prompts (use it as-is first).

Each is a clean later addition because the architecture isolates concerns.

---

## 7. Risks this design mitigates (and how)

| Risk | Mitigation in the design |
|------|--------------------------|
| Accidentally trading real money in DEV | DEV loads **no** trade credentials; `PaperBroker` has no API to Binance orders. |
| AI makes a reckless call | Hard guardrails in Risk Manager *outside* the AI cap size/loss. |
| Upstream brain changes break us | All brain knowledge isolated in `brain/` adapter. |
| Crash mid-order double-trades | Idempotent client order IDs. |
| Paper results lie vs reality | Model fees + slippage; later validate on TESTNET. |
| Secrets leak | `.env.*` gitignored; PROD key isolated, read-only DEV key. |

Next: the concrete checklist in [todo.md](todo.md), and the choices you need to
make in [decisions.md](decisions.md).
