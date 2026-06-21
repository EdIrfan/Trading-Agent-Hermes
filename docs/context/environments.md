# environments.md — DEV vs PROD, in depth

This is the core of your idea: two environments that are **the same system with
one component swapped**. This file explains exactly what that means, how paper
trading on live data works, and the safe path from fake money to real money.

See [concepts.md](concepts.md) for any unfamiliar term.

---

## 1. The guiding principle

> **DEV and PROD differ in exactly one place: where orders go and where the
> balance comes from.** Everything else — the AI brain, the live data, the
> decision logic, the risk guardrails, the logging — is identical.

We achieve this with one abstraction: the **Broker interface**. Two
implementations:

| Environment | Broker implementation | Money | Orders go to | Prices |
|-------------|----------------------|-------|--------------|--------|
| **DEV** | `PaperBroker` | fake (simulated balance) | a local simulator | **real, live Binance** |
| **TESTNET** *(optional middle step)* | `BinanceBroker` pointed at Binance **Spot Testnet** | fake (Binance-issued test funds) | Binance testnet API | testnet prices |
| **PROD** | `BinanceBroker` pointed at Binance **mainnet** | **real** | real Binance API | real, live |

You asked to **start with DEV**. We will. TESTNET and PROD are designed-for and
documented, but built later.

---

## 2. What DEV actually does (paper trading on live data)

The defining feature: **fake money, real prices.** Step by step, one cycle:

1. **Fetch live price.** Hermes asks Binance for the current `BTCUSDT` price
   (real, current — e.g. \$64,231).
2. **Run the brain.** Hermes calls `TradingAgentsGraph.propagate("BTC-USD",
   today)` with that live data made available to the market analyst. The AI team
   deliberates and returns, say, **Buy**.
3. **Size the trade.** Hermes's risk layer turns "Buy" + the portfolio state
   (e.g. \$10,000 fake cash) into a concrete order: "buy \$2,000 of BTC ≈
   0.0311 BTC."
4. **Simulate the fill.** `PaperBroker` fills the order at the **real current
   price** (optionally plus modeled slippage and Binance's ~0.1% fee), then:
   - deducts \$2,000 (+ fee) from fake cash,
   - adds 0.0311 BTC to fake holdings,
   - appends a row to the **ledger**.
5. **Record everything.** The decision, the reasoning, the fill, and the new
   portfolio value are logged.
6. **Repeat on a schedule** (e.g. every 4 hours), and continuously **mark to
   market** (revalue holdings at the live price) so you can watch unrealized P&L.

No order ever reaches Binance's order book. You cannot lose real money. But
because every price is real and current, the resulting P&L is a **faithful
preview** of how PROD would behave — minus a few real-world frictions (your order
actually moving the market, partial fills in thin books). For Bitcoin-sized
liquidity and modest sizes, that gap is small.

### Why this is the right first step
- **Zero financial risk** while the AI is unproven.
- **Realistic feedback** — real prices, real volatility, real fees modeled.
- **Exercises almost all the PROD code** — only the broker swaps, so a DEV that
  works de-risks PROD enormously.

---

## 3. What changes for PROD (and why it's a small change)

When you flip `--env prod`:

- `PaperBroker` → `BinanceBroker`. `place_order()` now signs a real request to
  Binance and a real order hits the book. `get_balance()` reads your real account.
- The **same** brain, **same** sizing, **same** guardrails, **same** logging run
  unchanged.

That's the payoff of the abstraction: **PROD is a config flip, not a rewrite.**
But "small code change" ≠ "small decision" — real money demands the extra
safeguards in §5 and the legal/security notes in [extras.md](extras.md).

### The recommended intermediate: Binance Spot Testnet
Before mainnet, point `BinanceBroker` at **Binance's Spot Testnet** (fake funds,
real API). This tests the *actual PROD code path* — authentication, order
formatting, error handling, rate limits — without real money. It catches the
class of bugs a paper simulator can't (real API quirks). Strongly recommended as
the gate between DEV and PROD.

The full ladder:

```
DEV (PaperBroker, our simulator)
   │  prove the strategy makes/keeps money on live prices
   ▼
TESTNET (BinanceBroker → testnet)
   │  prove the real API integration works (auth, orders, errors)
   ▼
PROD (BinanceBroker → mainnet, tiny size first)
   │  prove it with real money, capped small, then scale slowly
```

---

## 4. How environments are selected (no code editing)

Each environment is just a **named config + its own `.env`**. Selection is by a
single flag or env var:

```bash
hermes run --env dev    # loads .env.dev  → PaperBroker
hermes run --env prod   # loads .env.prod → BinanceBroker(mainnet)
```

Proposed layout:

```
Hermes/
├── .env.dev        # DEV: LLM keys, Binance READ-ONLY key (for prices), fake start balance
├── .env.prod       # PROD: LLM keys, Binance TRADE key, real account (gitignored, guarded)
├── .env.testnet    # optional middle rung
└── config/
    ├── dev.yaml     # broker: paper, start_cash: 10000, max_position_pct: 20, ...
    ├── prod.yaml    # broker: binance, network: mainnet, max_position_pct: 5, ...
    └── testnet.yaml
```

- **All secrets live in `.env.*` files, never in git** (they go in `.gitignore`).
- **DEV needs only a read-only Binance key** (just to *read* live prices) — or
  even no key at all, since public price data is keyless. So DEV can be run with
  **zero ability to touch real funds**, by construction.
- **PROD's trade-enabled key** is isolated in `.env.prod`, which we treat as
  radioactive (see security in [extras.md](extras.md)).

> **Safety by construction:** because DEV literally has no trade-capable
> credentials loaded, a bug in DEV *cannot* place a real order. The capability
> isn't present.

---

## 5. PROD-only safeguards (built before any real money)

These are designed now even though we build DEV first, so DEV already exercises
most of them:

- **Hard position limits** — never more than X% of the portfolio in one asset,
  enforced *outside* the AI. The AI can scream "Buy"; the guard caps the size.
- **Daily loss limit / circuit breaker** — if the account drops more than Y% in a
  day, stop trading until you intervene.
- **Kill-switch** — a single command/flag that halts all new orders immediately.
- **Dry-run mode** — `--dry-run` runs everything and *prints the order it would
  send* without sending it. The final sanity check before going live.
- **Idempotent orders** — every order carries a unique client ID so a crash-retry
  can't double-trade.
- **Confirmation gate** — PROD refuses to start without an explicit
  acknowledgement (e.g. `--i-understand-real-money`) to prevent "oops, wrong env".
- **Min/max order size & precision** — respect Binance's lot-size and tick rules
  so orders aren't rejected.
- **Reconciliation** — on startup, compare Hermes's ledger against Binance's
  actual balance and refuse to trade if they disagree.

DEV implements the *same* limits, kill-switch, and dry-run against the simulator,
so the guardrail code is battle-tested long before it guards real money.

---

## 6. Live data in both environments

Both DEV and PROD use **the same live Binance market data** for prices — that's
what makes DEV realistic. The difference is only execution. Concretely:

- **Prices / candles:** Binance public market-data API (keyless). Used to feed the
  brain's market analyst and to value the portfolio. Same in DEV and PROD.
- **News / sentiment / macro:** unchanged from TradingAgents (Yahoo/Reddit/
  StockTwits/FRED). These don't depend on the trading environment.

A subtle point: TradingAgents analyzes a **date** and pulls **daily** candles. For
live crypto we pass **today** as the date and must make the analyst see the
**current** price, not yesterday's close. The mechanics (a Binance vendor and/or a
verified live snapshot injected into the brain) are in [plan.md](plan.md) §"Data".

---

## 7. State that each environment keeps separate

Each environment has its **own isolated portfolio and logs**, so DEV experiments
never contaminate PROD records:

```
Hermes/state/
├── dev/
│   ├── portfolio.json       # fake cash + holdings
│   ├── ledger.sqlite        # every simulated fill
│   └── decisions/           # every brain run + reasoning
├── testnet/...
└── prod/
    ├── portfolio.json       # mirror of real Binance balance (reconciled)
    ├── ledger.sqlite
    └── decisions/
```

The brain's own memory/reflection file can also be namespaced per environment
(via `TRADINGAGENTS_MEMORY_LOG_PATH`) so DEV's lessons and PROD's lessons don't mix
unless you want them to.

---

## 8. Summary table

| Aspect | DEV | TESTNET | PROD |
|--------|-----|---------|------|
| Money | fake (simulated) | fake (Binance test funds) | **real** |
| Orders | local `PaperBroker` | Binance testnet API | Binance mainnet API |
| Prices | real live Binance | testnet | real live Binance |
| Can lose real money? | **No** | No | **Yes** |
| Credentials loaded | none / read-only | testnet keys | trade-enabled keys |
| Purpose | prove the strategy | prove the API integration | the real thing |
| Build order | **1st (now)** | 2nd | 3rd |
| Shares code with PROD | ~95% | ~99% | — |

The takeaway: **build DEV well, and PROD is mostly already built.** Next, the
architecture that makes this swap possible: [plan.md](plan.md).
