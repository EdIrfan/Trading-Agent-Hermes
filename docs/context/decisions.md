# decisions.md — Choices only you can make

These are the forks in the road where I need your input (or your blessing on my
recommendation) before writing real code. Each has my **recommendation** so you
can just say "go with the defaults" if you want. Referenced as D1, D2… elsewhere.

You don't have to answer all of them now — only **D2–D6** block Phase 0–2. The
PROD ones (D9, D10) can wait.

---

## D1 — Project name & repo
- **Question:** Keep the codename **Hermes**? And should it be its own git repo
  (and eventually pushed to GitHub), or just a local folder for now?
- **My recommendation:** Keep "Hermes" for now (rename is trivial — nothing
  depends on it yet); make it a **local git repo** immediately (so we have
  history/safety) and decide on pushing to GitHub later.
- **Impact:** cosmetic + version control hygiene.

## D2 — Binance access library
- **Question:** Use **`python-binance`** (Binance-specific, mature) or **`ccxt`**
  (one library, 100+ exchanges, easy to swap exchanges later)?
- **My recommendation:** **`ccxt`** — it keeps you exchange-agnostic (if you ever
  leave Binance, the code barely changes) and its unified API is clean. Slight
  cost: a thin abstraction over Binance-specific features. If you're certain it's
  Binance-forever, `python-binance` is also fine.
- **Impact:** the `data/` and `broker/` implementations. Blocks Phase 1–2.

## D3 — How live price reaches the brain
- **Question:** (A) register a **Binance vendor** inside TradingAgents' data
  layer, or (B) **inject a verified live snapshot** into the run without touching
  the brain's vendors?
- **My recommendation:** Start with **(B)** — least coupling, keeps the brain
  un-edited, fastest to working DEV. Revisit (A) if we want the brain to pull
  richer live history itself.
- **Impact:** `data/` + `brain/` adapter. Blocks Phase 1.

## D4 — Mapping the 5-tier rating to an action ✅ RESOLVED (revised 2026-06-21)
- **Question:** How should **Buy / Overweight / Hold / Underweight / Sell** become
  an actual order?
- **Decision: `fixed_notional`** — fixed-dollar, opportunistic trades (user
  preference, 2026-06-21). Take trades as signals come, each a fixed size:
  - **Buy / Overweight** → buy **`trade_notional`** (default **$100**) of the coin,
    if under the per-coin cap (`max_position_notional`, default $2,000) and cash
    allows.
  - **Underweight** → sell one `trade_notional`'s worth (trim).
  - **Sell** → close the whole position.
  - **Hold** → nothing.
  - Coins are processed in basket order, cash-limited — so it's naturally
    "first come, first served" when cash gets tight. Starting capital stays $10k.
  - Change the trade size in `config/<env>.yaml` → `trade_notional` (e.g. 50).
- **Also available:** `strategy: target_weight` — the original equal-weight-sleeve
  model (each coin targets `max_total_exposure / N`). Kept as an option, not the
  default.
- **Basket (multi-asset):** **BTC, ETH, SOL, BNB, HYPE** (user-chosen). HYPE
  (Hyperliquid) is not on Binance spot, so it is priced via **Bybit** through the
  per-coin `symbol_exchanges` routing; the others use Binance. See
  [environments.md](environments.md) and `hermes/data/market.py`.
- **Impact:** `risk/` core logic + multi-exchange `data/`. **Done.**

## D5 — LLM provider & model for the brain ✅ RESOLVED (revised → Gemini, 2026-06-21; model updated 2026-06-22)
- **Current decision: Google Gemini FREE tier — `gemini-3.1-flash-lite`.**
  `llm_provider = "google"`, both slots `gemini-3.1-flash-lite`. This gives
  **500 requests/day free** on the `AQ.`-prefixed key in `.env.dev` as
  `GOOGLE_API_KEY`. Verified end-to-end: full multi-agent pipeline ran, produced
  genuine technical analysis, paper-traded. Each BTC analysis ≈ 14 requests →
  ~35 full analyses/day free.
  - Note: `gemini-2.5-flash` = 20/day (too low). `gemini-3.1-flash-lite` = 500/day ✅
  - Cadence: `--interval 4h` is the right daily-use cadence (6 runs/day);
    back-to-back batch testing exhausts the quota in ~1 hour.
- **Next step: Anthropic (Claude)** — when you have a paid `ANTHROPIC_API_KEY`:
  change `config/dev.yaml` → `llm_provider: anthropic`, `deep_think_llm:
  claude-sonnet-4-6`, `quick_think_llm: claude-haiku-4-5`. The factory is
  already provider-aware (`factory.llm_key_env`) — it's a one-line config change.
  - **⚠️ IMPORTANT:** `ANTHROPIC_API_KEY` is a **separate, paid, pay-per-token
    credential** from console.anthropic.com. It is **NOT** the same as a Claude
    Code / Claude Pro subscription. You must create a new key with billing enabled.
  - **Pricing (per 1M tokens, in/out):** Opus 4.8 $5/$25 · Sonnet 4.6 $3/$15 ·
    Haiku 4.5 $1/$5. See [extras.md](extras.md) §1 for per-run cost math.

## D6 — Paper-trading realism (fees & slippage)
- **Question:** In DEV, model **Binance fees** (~0.1%/trade) and **slippage**, or
  start with frictionless fills?
- **My recommendation:** Model **fees from day one** (they materially change
  results) and add a **small fixed slippage** assumption; refine later. Frictionless
  paper results are misleadingly rosy.
- **Impact:** `PaperBroker`. Blocks Phase 2 (but easy to start simple).

## D7 — Storage for portfolio & ledger
- **Question:** **SQLite** (queryable, robust) vs **plain JSON/CSV files**
  (simple, human-readable)?
- **My recommendation:** **SQLite for the ledger** (append-only fills, easy to
  query for P&L) + **JSON for portfolio snapshots & decisions** (readable). Matches
  what TradingAgents already does (SQLite for checkpoints).
- **Impact:** `portfolio/` + `store/`. Phase 2.

## D8 — Scheduling & trade cadence
- **Question:** How often should the bot make a decision — every `1h`, `4h`,
  `1d`? And run via a simple in-process loop, OS cron, or an AI agent's
  built-in scheduler (e.g. Claude Code's `/schedule`)?
- **My recommendation:** Start with **`--once`** (manual) during development, then
  a **simple in-process loop** with `--interval 4h` for DEV. 4h balances signal
  freshness against LLM cost (each run costs tokens). Daily is cheapest. We can
  tune once we see costs.
- **Impact:** `scheduler/`. Phase 3. Drives running cost.

## D9 — PROD risk caps (decide before any real money)
- **Question:** When/if we reach PROD: starting capital, max % per position, max
  daily loss before halting, and absolute per-trade cap?
- **My recommendation:** Don't decide yet — revisit after DEV proves itself.
  Placeholder defaults for design: tiny starting capital, ≤5% per position, halt
  on ≥3% daily loss, hard per-trade cap. Conservative on purpose.
- **Impact:** PROD only. Phase 6.

## D10 — Long-only vs shorting; spot vs futures
- **Question:** Ever want to **short** (profit when price falls) or use
  **leverage/futures**, or stay **long-only spot**?
- **My recommendation:** **Long-only spot** for the foreseeable future — simpler,
  far less risky, and the brain's signals map cleanly. Shorting/leverage is a big,
  deliberate later step (and much riskier).
- **Impact:** `risk/` + `broker/`. Affects PROD scope. Deferred.

---

## How to answer
Reply with anything from "go with all your recommendations" to specific overrides
like "D2: python-binance, D5: I have an OpenAI key, D8: daily". I'll record your
answers here (turning each into a ✅ resolved note) and update [todo.md](todo.md)
accordingly before writing code.

### Resolved — all decisions final as of 2026-06-22

- D1 Hermes name, local git repo. ✅
- D2 **ccxt** for exchange access (multi-exchange: Binance default + Bybit for HYPE). ✅
- D3 inject a **verified live snapshot** into the brain (option B — TradingAgents untouched). ✅
- D4 **`fixed_notional`** — **$10/trade** over a **5-coin basket** (BTC/ETH/SOL/BNB/HYPE),
  $200 per-coin cap, $1,000 starting capital. Long-only spot. ✅
- D5 **Google Gemini FREE tier** — `gemini-3.1-flash-lite` (500 req/day), `GOOGLE_API_KEY`
  in `.env.dev`. Next step: Anthropic API key ($20 credit) for Claude. ✅
- D6 model **0.1% fees + 0.05% slippage** from day one (realistic paper trading). ✅
- D7 **SQLite** ledger (source of truth) + **JSON** portfolio snapshots + **CSV** equity curve. ✅
- D8 `--once` for manual; `--interval 4h` for the daily loop (implemented). ✅
- D9 / D10 deferred to PROD (conservative placeholders — not started yet). ⬜

**Nothing is blocking further testing** — Gemini free tier works today. To use Claude/Anthropic
instead, create an API key at console.anthropic.com (billing enabled, separate from Claude Pro).
