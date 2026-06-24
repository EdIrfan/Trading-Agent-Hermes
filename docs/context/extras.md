# extras.md — Money, risk, security, legal, costs, gotchas

Everything important that doesn't fit the other docs. Read this **before** going
anywhere near real money. Honest, not scary-for-the-sake-of-it.

---

## 1. The running cost (this is not free — except on Gemini free tier)

Every decision the brain makes is a large multi-agent LLM conversation: 7+ agents,
each reading and writing long reports, plus multi-round debates. That burns
**tokens** (and API **requests**), and both can cost money.

### Gemini Free Tier (current setup — zero cost)
`gemini-3.1-flash-lite` on a free AI Studio key gives **500 requests/day** at no
charge. Each full BTC analysis uses ~14 requests, so you get **~35 full analyses/day
free**. On a 4-hour loop (6 runs/day) that's about 5 days of free testing per day's
quota. The `GOOGLE_API_KEY` in `.env.dev` is all you need.

**Current model:** `deep_think_llm: gemini-3.1-flash-lite` (both slots, `config/dev.yaml`).
Key starts with `AQ.` prefix — this is a restricted AI Studio key type that only
works with flash-lite. If you want higher-quota models later, regenerate a standard
key (`AIza...`) at https://aistudio.google.com/apikey.

### Paid providers (for higher quality or production)
- Cheap models (DeepSeek, Haiku tiers): **cents** per run.
- Frontier models (Claude Opus 4, GPT-5.x): **\$1–\$5+ per run**.
- If you run every 4 hours, that's **6 runs/day** → multiply accordingly.

**To switch to Claude:** change `config/dev.yaml` → `llm_provider: anthropic`,
`deep_think_llm: claude-sonnet-4-6`, `quick_think_llm: claude-haiku-4-5`, and add
`ANTHROPIC_API_KEY=...` to `.env.dev`. **Note:** this requires a separate paid
Anthropic API key — your Claude Code subscription does NOT grant API access.

**Implications:**
- The trade cadence is a direct cost lever — 4h is much cheaper than back-to-back.
- Set a billing alert on whatever paid provider you use.
- Token cost is independent of DEV/PROD — even fake-money DEV costs real LLM money.

---

## 2. Will it actually make money? (expectations + early evidence)

- The TradingAgents authors are explicit: it's a **research framework**, results
  vary with model/temperature/period/data, and it is **not financial advice**.
- LLM trading is **unproven** as a reliable money-maker. Many strategies that look
  good on paper fail live.
- **This is exactly why DEV exists.** The entire point of paper trading on live
  data is to find out — at zero financial risk — whether this makes or loses money
  *before* it matters. Treat a profitable DEV run as encouraging, not as proof.
- **Benchmark honestly:** compare against simply **buying and holding the basket**.
  `hermes report` computes this automatically. If alpha isn't positive, the bot is
  not adding value — just adding cost and risk.

### Early real-brain results (Gemini free tier, BTC only, 2026-06-22 and 2026-06-24)
| Day | Strategy return | BTC buy-and-hold | Alpha |
|-----|----------------|-----------------|-------|
| Jun 22 | −0.08% | −0.25% | **+0.17%** |
| Jun 24 | −0.03% | −0.32% | **+0.28%** |

Both sessions: the AI was cautious (kept ~70–85% in cash), which protected capital
on days BTC drifted down. The **circuit breaker never triggered** — drawdown stayed
under 0.05%. Win rate was 0% on Jun 24 (bought slightly before each dip) but total
losses were only $0.36 on $1,000 capital across 35 runs.

**What this is NOT:** two 48-minute backtests are not a track record. Positive alpha
on a flat/down day from staying in cash is not the same as an alpha-generating
strategy. Run it over weeks/months, on both up and down markets, before drawing
conclusions.

---

## 3. Security — protecting keys and money

### LLM API keys
- Stored in `.env.*`, **never committed** (`.gitignore` covers it).
- A leaked LLM key = someone spends your money on tokens. Bad, but bounded by your
  billing limit.

### Binance API keys (the dangerous ones — PROD)
- **Create separate keys per environment.** DEV uses a **read-only** key (or none
  — public price data is keyless). PROD uses a **trade-enabled** key, isolated in
  `.env.prod`.
- **NEVER enable "withdrawal" permission** on a bot key. Trade-only. If a
  trade-only key leaks, an attacker can trade your account but **cannot take your
  coins out**. Withdrawal permission turns a leak into theft.
- **Restrict by IP** (Binance lets you whitelist the IP your bot runs from).
- **Rotate keys** if you ever suspect exposure.
- Never paste keys into chat, code, screenshots, or commits.
- Consider a dedicated sub-account with limited funds for the bot, separate from
  your main holdings.

### Safe-by-construction DEV
- Because DEV loads **no trade-capable credentials**, a bug in DEV literally
  cannot place a real order — the capability isn't present. This is intentional.

---

## 4. Legal / compliance / tax (not legal advice)

- **KYC:** Binance requires identity verification to trade. API trading is allowed
  but subject to their terms.
- **Jurisdiction:** crypto trading rules vary by country/region; some restrict
  Binance or certain products. Check your local rules before PROD.
- **Tax:** real trades can be **taxable events** (capital gains). Keep the ledger
  (Hermes does) and consult a tax professional. DEV/paper has no tax impact.
- **Bots are allowed** on Binance via their API, within rate limits and terms.
- This is informational, **not legal or financial advice.** When real money is
  involved, do your own due diligence.

---

## 5. Technical gotchas & pitfalls

- **LLM non-determinism:** the brain can give different answers on identical
  inputs. Two runs may disagree. Don't over-trust a single decision; think in
  aggregate over time. Lower `temperature` reduces (not eliminates) this.
- **Data spelling mismatches:** Binance `BTCUSDT` vs Yahoo `BTC-USD` vs internal —
  a mapping bug means you analyze one thing and trade another. Tested carefully in
  the `data/` layer. (TradingAgents already had bugs here historically — see its
  symbol-mapping hardening.)
- **Daily-vs-live mismatch:** the brain was built around **daily** candles and a
  historical date. Feeding it "now" needs care so the market analyst sees the
  current price, not a stale close (TradingAgents has a staleness guard that can
  reject data it deems old).
- **Rate limits:** both LLM providers and Binance throttle. Pace requests; handle
  429/backoff. Don't poll prices in a tight loop.
- **Idempotency:** if Hermes crashes between "sent order" and "recorded order,"
  a naive retry could double-trade. Unique client order IDs prevent this — must be
  in place before PROD.
- **Reconciliation drift:** the local ledger can diverge from Binance's real
  balance (a missed fill, a manual trade you did yourself). PROD must reconcile on
  startup and refuse to trade on mismatch.
- **Slippage & fees make paper rosy:** unmodeled, paper P&L looks better than
  reality. Model them (D6).
- **Partial fills & min lot sizes:** Binance rejects orders below a minimum and
  rounds to lot/tick increments. The `BinanceBroker` must respect these.
- **Time zones & "today":** decide the run's date in a consistent timezone (UTC is
  safest for 24/7 crypto).
- **Clock/scheduler reliability:** a loop that silently dies stops trading without
  telling you. Add health logging/alerts (Phase 3).

---

## 6. Operational safety checklist (before PROD)

- [ ] DEV has run profitably (or at least sanely) over a meaningful period.
- [ ] TESTNET validated the real Binance code path (auth, orders, errors).
- [ ] Trade-only Binance key (no withdrawal), IP-restricted, in `.env.prod` only.
- [ ] Hard caps set: max position %, per-trade cap, daily loss limit (D9).
- [ ] Kill-switch tested. `--dry-run` tested. Confirmation gate in place.
- [ ] Startup reconciliation vs real balance works and blocks on mismatch.
- [ ] Billing/spend alerts on the LLM provider.
- [ ] Monitoring/alerts on each trade and each guardrail trip.
- [ ] You've started with **tiny** capital and will scale slowly.
- [ ] You accept you can lose what you put in.

---

## 7. Ideas / "over-and-beyond" backlog (not committed)

Things the architecture supports later, if you want them:

- **Phase 5 (Binance testnet)** — real API, fake test funds. Proves the execution
  code path before real money. `BinanceBroker` pointing at Binance Spot Testnet.
- **Phase 6 (PROD real money)** — the real thing, gated behind every check in §6.
  Start tiny (few hundred dollars), scale only after months of positive DEV evidence.
- **Slower cadence / real intervals** — run on `--interval 4h` across real days to
  see decisions on genuine price moves, not 90-second noise. The Jun 22 and Jun 24
  batch tests were back-to-back; the AI was reacting to noise, not trends.
- **All 5 coins at once** — current tests use only BTC to save quota. Run on the
  full basket (`hermes run --env dev`) when you have more quota headroom.
- **Web dashboard** (live P&L, decision feed, equity curve chart) instead of CLI-only.
- **WebSocket** live data for tighter price feeds than 1-minute REST polling.
- **Notifications** (Telegram/Discord/email) on trades and circuit breaker trips.
- **Backtesting** engine (use the unused `backtrader` dep or a custom replay) to
  test over years of history fast — the architecture is ready (equity curve is
  already a time series).
- **Strategy variants / A-B testing** the brain config (debate rounds, models).
- **Improved learning loop:** feed real P&L back into the brain's reflection
  (`TradingMemoryLog`) so it learns from actual outcomes, not just price moves.
- **Ensemble decisions:** run the brain N times and vote, to reduce flip-flopping.
- **Smarter execution:** TWAP/limit orders instead of market orders to cut slippage.
- **Risk analytics:** Sharpe ratio, Sortino, rolling drawdown exposure reports.

---

## 8. The one-line reality check

Build DEV, watch it paper-trade live BTC for a while, judge it honestly against
buy-and-hold, and only then — slowly, with capped real money and every safeguard
on — consider PROD. The architecture is built so that path is the natural one.
