# Hermes — Documentation Context

This folder is your **map of the whole project**. It was written for someone
who does not yet know what this project is, how trading works, or how the
underlying AI framework is built. Nothing here is assumed knowledge.

> **What is Hermes?** A personal, AI-driven crypto trading system that *wraps*
> the existing **TradingAgents** framework (the "brain" that decides Buy / Hold /
> Sell) and adds the missing pieces: live market data, an execution layer, a
> portfolio with real or fake money, and two environments — **DEV** (fake money,
> real live data) and **PROD** (real money, real Binance orders).
>
> The name "Hermes" is just a codename (Greek god of trade/commerce). Rename it
> whenever you like — nothing depends on the name yet.

---

## Read these in order

| # | File | What it answers | Read when |
|---|------|-----------------|-----------|
| 1 | [explanation.md](explanation.md) | "What is this thing, in plain English? What are we building and why?" | First. Start here. |
| 2 | [concepts.md](concepts.md) | "What does every term mean?" — a glossary of every trading, AI, and software concept used, no matter how small. | Keep open as a reference while reading everything else. |
| 3 | [context.md](context.md) | "How does the existing TradingAgents repo actually work?" — a deep, file-by-file tour of the brain we're building on. | When you want to understand the code we already have. |
| 4 | [environments.md](environments.md) | "What exactly is DEV vs PROD? How does fake-money trading on live data work?" | When you want to understand the core DEV/PROD design. |
| 5 | [plan.md](plan.md) | "What is the architecture of Hermes and the phased roadmap to build it?" | When you want the build plan. |
| 6 | [todo.md](todo.md) | "What are the concrete next steps, as a checklist?" | When you want to start doing work. |
| 7 | [decisions.md](decisions.md) | "What choices do *you* (the human) still need to make?" — open questions with my recommendations. | Before we write real code. Answer these. |
| 8 | [extras.md](extras.md) | "What about money, risk, security, legal, gotchas, and costs?" — everything that doesn't fit elsewhere but matters. | Before going anywhere near real money. |

---

## The one-paragraph summary

The repo you found, **TradingAgents**, is a research tool: you give it a stock
or crypto ticker and a date, and a team of AI agents (analysts, researchers, a
trader, a risk team, a portfolio manager) debate and produce a **recommendation**
— Buy, Overweight, Hold, Underweight, or Sell. That's *all* it does today: it
talks, it does not trade. **Hermes** turns that recommendation into action:
it feeds the brain **live crypto prices**, takes the Buy/Sell decision, and
**places orders** — against a simulated paper account in **DEV** (so you can
test safely with fake money on real market data) or against **Binance** in
**PROD** (real money, only once DEV has earned your trust).

---

## Current status (as of 2026-06-24)

**Phases 0–4 are fully built and tested.** The system runs end-to-end.

- ✅ TradingAgents repo read and understood; all docs written.
- ✅ Hermes code built: brain adapter, live data (ccxt, Binance + Bybit), PaperBroker,
  portfolio/ledger (SQLite), risk manager (fixed_notional + target_weight), orchestrator, CLI.
- ✅ Real brain verified end-to-end: Gemini 3.1 Flash Lite (500 req/day free) runs the full
  multi-agent pipeline on live BTC prices and paper-trades the decision.
- ✅ 5-coin basket: BTC, ETH, SOL, BNB, HYPE — HYPE priced via Bybit (not on Binance spot).
- ✅ **Circuit breaker** (Phase 3): halts new buys if the portfolio drops >5% intraday.
- ✅ **Performance report** (Phase 4): `hermes report` shows return, max drawdown, win rate,
  and **alpha vs equal-weight buy-and-hold** — the honest verdict on whether the AI adds value.
- ✅ Capital set to **$1,000 / $10 trades** to match the real intended live amount.
- ✅ 36 pytest tests pass; ruff clean.
- ⬜ Phase 5 (Binance testnet) and Phase 6 (PROD real money) — deliberately not built yet.

**Real results so far (paper trading, 2026-06-22 and 2026-06-24):**
- Day 1 (Jun 22): 35 runs on BTC, alpha **+0.17%** vs buy-and-hold (strategy −0.08%, BTC −0.25%).
- Day 2 (Jun 24): 35 runs on BTC, alpha **+0.28%** vs buy-and-hold (strategy −0.03%, BTC −0.32%).
- Circuit breaker never triggered (intraday drawdown stayed under 0.05%).
- Both days the AI was cautious: kept ~70–85% in cash, which beat a falling market.

**To resume testing tomorrow:** `hermes run --env dev --symbols BTC/USDT --interval 4h`
(or re-run the batch: `python scripts/run_real_batch.py --env dev --symbols BTC/USDT`)

All open decisions are resolved — see [decisions.md](decisions.md).
