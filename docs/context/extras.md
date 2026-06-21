# extras.md — Money, risk, security, legal, costs, gotchas

Everything important that doesn't fit the other docs. Read this **before** going
anywhere near real money. Honest, not scary-for-the-sake-of-it.

---

## 1. The running cost (this is not free)

Every decision the brain makes is a large multi-agent LLM conversation: 7+ agents,
each reading and writing long reports, plus multi-round debates. That burns
**tokens**, and tokens cost money.

- A single full run can be **tens of thousands to hundreds of thousands of
  tokens** depending on models, debate rounds, and report length.
- Rough order of magnitude (varies hugely by provider/model):
  - Cheap models (DeepSeek, mini tiers): **cents** per run.
  - Frontier models (GPT-5.x, Claude Opus): **\$X per run** (potentially a dollar
    or several).
- If you run every 4 hours, that's **6 runs/day** → multiply accordingly. Daily
  runs are 6× cheaper than 4-hourly.

**Implications:**
- Use a **cheap model during development** (D5); reserve strong models for "real"
  DEV/PROD runs.
- The trade cadence (D8) is a direct cost lever.
- Set a **spend limit / billing alert** on your LLM provider account.
- Token cost is **independent of DEV/PROD** — even fake-money DEV costs real LLM
  money. Budget for it.

---

## 2. Will it actually make money? (expectations)

- The TradingAgents authors are explicit: it's a **research framework**, results
  vary with model/temperature/period/data, and it is **not financial advice**.
- LLM trading is **unproven** as a reliable money-maker. Many strategies that look
  good on paper fail live.
- **This is exactly why DEV exists.** The entire point of paper trading on live
  data is to find out — at zero financial risk — whether this makes or loses money
  *before* it matters. Treat a profitable DEV run as encouraging, not as proof.
- **Benchmark honestly:** compare against simply **buying and holding Bitcoin**.
  If the bot can't beat buy-and-hold (its *alpha* isn't positive), it's not adding
  value, just adding cost and risk.

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

- **Web dashboard** (live P&L, decision feed, equity curve) instead of CLI-only.
- **Multi-asset** portfolio (BTC + ETH + …) with allocation logic.
- **WebSocket** live data for tighter price feeds.
- **Notifications** (Telegram/Discord/email) on trades and alerts.
- **Backtesting** engine (use the unused `backtrader` dep or a custom replay) to
  test over years of history fast.
- **Strategy variants / A-B testing** the brain config (debate rounds, models).
- **Improved learning loop:** feed real P&L back into the brain's reflection so it
  learns from actual outcomes, not just price moves.
- **Ensemble decisions:** run the brain N times and vote, to tame
  non-determinism.
- **Smarter execution:** TWAP/limit orders instead of market orders to cut
  slippage.
- **Risk analytics:** Sharpe ratio, sortino, rolling drawdown, exposure reports.

---

## 8. The one-line reality check

Build DEV, watch it paper-trade live BTC for a while, judge it honestly against
buy-and-hold, and only then — slowly, with capped real money and every safeguard
on — consider PROD. The architecture is built so that path is the natural one.
