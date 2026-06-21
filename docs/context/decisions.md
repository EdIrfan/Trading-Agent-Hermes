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

## D4 — Mapping the 5-tier rating to an action
- **Question:** How should **Buy / Overweight / Hold / Underweight / Sell** become
  an actual order? Two styles:
  - **Target-weight:** each rating maps to a target % of the portfolio in BTC
    (e.g. Buy→80%, Overweight→60%, Hold→hold, Underweight→30%, Sell→0%); Hermes
    trades the difference.
  - **Fixed-step:** each Buy adds a fixed slice; each Sell removes one.
- **My recommendation:** **Target-weight**, long-only, single asset — it's
  intuitive, naturally caps exposure, and turns the 5 tiers into smooth sizing.
  Start conservative (e.g. max 50–80% in BTC, rest cash).
- **Impact:** `risk/` core logic. Blocks Phase 2. *(We can tune the exact
  percentages together once it runs.)*

## D5 — LLM provider & model for the brain ✅ RESOLVED
- **Decision:** **Anthropic (Claude).** `llm_provider = "anthropic"`.
  - **DEV iteration (cheap):** `deep_think_llm = claude-sonnet-4-6`,
    `quick_think_llm = claude-haiku-4-5`.
  - **Quality runs (once it works):** `deep_think_llm = claude-opus-4-8`,
    `quick_think_llm = claude-sonnet-4-6`.
- **⚠️ CRITICAL PREREQUISITE:** TradingAgents calls the Anthropic **API** directly
  via an `ANTHROPIC_API_KEY`. This is a **separate, paid, pay-per-token credential**
  from a console.anthropic.com account — it is **NOT** the same as the user's
  Claude Code subscription. Claude Code being installed does **not** give the Python
  framework access to Claude. **The user must create an `ANTHROPIC_API_KEY` (with
  billing enabled) before the brain can run.** Status: not yet obtained.
- **Pricing (per 1M tokens, in/out):** Opus 4.8 $5/$25 · Sonnet 4.6 $3/$15 ·
  Haiku 4.5 $1/$5. See [extras.md](extras.md) §1 for the per-run cost math.
- **Open sub-task:** verify TradingAgents' anthropic model catalog
  (`tradingagents/llm_clients/model_catalog.py`) recognizes these IDs, or use the
  CLI "Custom model ID" path / set `TRADINGAGENTS_DEEP_THINK_LLM` directly.
- **Impact:** can't run the brain at all without the API key. **Blocks everything
  past Phase 0.**

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
  `1d`? And run via a simple in-process loop, OS cron, or Claude Code `/schedule`?
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

### Resolved
- **All decisions: go with my recommendations** (user instruction, 2026-06-21),
  **except D5** which is explicitly set to **Anthropic / Claude** (see D5 above).
  So the working defaults are now:
  - D1 Hermes name, local git repo.
  - D2 **ccxt** for Binance access.
  - D3 inject a **verified live snapshot** into the brain (option B).
  - D4 **target-weight** rating→action mapping, long-only single-asset.
  - D5 **Anthropic/Claude** — Sonnet 4.6 + Haiku 4.5 for DEV iteration, Opus 4.8 +
    Sonnet 4.6 for quality runs. **Needs an `ANTHROPIC_API_KEY` (paid) — pending.**
  - D6 model **fees + small slippage** from day one.
  - D7 **SQLite** ledger + **JSON** snapshots/decisions.
  - D8 start `--once`, then a simple in-process loop at **4h** for DEV.
  - D9 / D10 deferred to PROD (conservative placeholders).
- **The only thing blocking Phase 0→2 now is the Anthropic API key.**
