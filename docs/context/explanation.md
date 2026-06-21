# explanation.md — What is this, in plain English?

This file assumes you know nothing about trading or AI agents. We build up
from zero. If a word is unfamiliar, it is defined in [concepts.md](concepts.md).

---

## 1. The problem we're solving

You want a system that **decides when to buy and sell crypto, and actually does
it for you** — but you want to test it safely first, with fake money on real
prices, before risking a single real dollar.

That system has two halves:

1. **A brain** — something that looks at the market and decides "buy" or "sell".
2. **Hands** — something that takes that decision and places the actual order on
   an exchange, tracks how much money you have, and records the profit or loss.

You found a project on the web — **TradingAgents** — that is a very sophisticated
**brain**. It has **no hands at all**. Our job is to build the hands (and to give
the brain live data to think about), without breaking the brain.

---

## 2. What TradingAgents (the brain) actually is

TradingAgents is a research framework from a group called Tauric Research. Its
big idea: instead of one AI making a trading decision, it **simulates a whole
trading firm** as a team of AI agents that each have a job and talk to each
other. (An "agent" here just means an AI given a role and some tools — see
[concepts.md](concepts.md).)

Here is the team, in the order they work:

1. **Analysts** gather facts about one asset (say Bitcoin):
   - *Market/Technical Analyst* — reads the price chart and indicators (is it
     trending up? overbought?).
   - *Sentiment Analyst* — reads social media (Reddit, StockTwits) mood.
   - *News Analyst* — reads news headlines and big-picture economy news.
   - *Fundamentals Analyst* — reads company financials (for stocks; **skipped for
     crypto** because a coin has no balance sheet).

2. **Researchers** argue about the facts:
   - A *Bull* researcher makes the optimistic case ("this will go up").
   - A *Bear* researcher makes the pessimistic case ("this will go down").
   - They debate back and forth for a configurable number of rounds.

3. **Research Manager** listens to the debate and writes an *investment plan*.

4. **Trader** turns that plan into a concrete proposal: Buy / Hold / Sell, with
   an optional entry price, stop-loss, and position size.

5. **Risk team** stress-tests the proposal — an *Aggressive*, a *Conservative*,
   and a *Neutral* voice debate whether the trade is too risky.

6. **Portfolio Manager** makes the final call and assigns a **rating**:
   **Buy, Overweight, Hold, Underweight, or Sell**.

The final output of the entire machine is that one rating, plus a pile of
written reports explaining the reasoning. **It then stops.** It does not buy
anything. It writes the decision to a memory file so that next time it can look
back and learn from whether the call was right.

> **Key realization:** TradingAgents is an *advisor*, not a *trader*. The README
> says approved orders are "sent to the simulated exchange and executed" — but
> after reading the entire codebase, **that execution step does not exist in the
> code**. There is no exchange, simulated or real. That's the gap Hermes fills.

---

## 3. What's missing (everything Hermes adds)

The brain has four big gaps for our goal:

| Gap | What TradingAgents does today | What Hermes needs |
|-----|------------------------------|-------------------|
| **Live data** | Pulls **daily** candles from Yahoo Finance, and can analyze a *historical* date. | **Live, current** crypto prices from Binance, refreshed as we run. |
| **Execution** | None. Outputs a rating and stops. | Place real orders (PROD) or simulated orders (DEV). |
| **Portfolio** | None. No idea how much money you have or own. | Track cash, holdings, and profit/loss over time. |
| **Automation** | You run it once, by hand, for one ticker+date. | A loop/scheduler that runs the brain on a cadence and acts on its output. |

---

## 4. The two environments: DEV and PROD

This is the heart of your idea.

### DEV — "paper trading" on live data

- **Fake money, real prices.** Hermes pretends you have, say, \$10,000. When the
  brain says "Buy Bitcoin", Hermes records a *simulated* buy at the **real
  current Binance price**, deducts fake cash, and tracks the fake position.
- **Nothing hits the real exchange.** You cannot lose real money in DEV.
- **Purpose:** prove the brain + hands actually make money (or at least don't
  bleed it) before you trust them. This is called **paper trading**.
- **Realistic:** because the prices are real and current, a profit/loss in DEV is
  a meaningful (if imperfect) preview of how PROD would behave.

### PROD — real trading on Binance

- **Real money, real orders.** Same brain, same hands — but the "place order"
  step now calls the **Binance API** with your real account, and the portfolio
  reflects your actual balance.
- **Purpose:** the real thing. We only flip to PROD after DEV has earned trust.
- We will build PROD as a thin swap of one component (the "broker"), so DEV and
  PROD share 95% of the code and differ only in *where orders go*.

> The whole design principle: **DEV and PROD are the same system with one part
> swapped.** If it works in DEV, PROD is a configuration change, not a rewrite.

We will **start with DEV only**, exactly as you asked. PROD is designed-for but
not built until you're ready.

---

## 5. Why a separate project instead of editing TradingAgents?

- **Keep the brain pristine.** TradingAgents is actively maintained by its
  authors; you have it as a git fork (`EdIrfan/TradingAgents`) tracking the
  original (`TauricResearch/TradingAgents` upstream). If we bolt our trading
  logic *inside* it, every time we pull their updates we'll fight merge
  conflicts. Keeping Hermes separate means we can upgrade the brain freely.
- **Separation of concerns.** The brain decides; Hermes acts. Mixing "decide"
  and "act" code makes both harder to reason about and test.
- **Hermes imports TradingAgents as a library.** TradingAgents already supports
  this — you can `from tradingagents.graph.trading_graph import TradingAgentsGraph`
  and call `.propagate(ticker, date)` to get a decision. Hermes will call exactly
  that, then do something with the answer.

So the folder layout becomes:

```
GitHub/
└── Trading Agent/
    ├── TradingAgents/   ← the brain (unchanged, upstream library)
    └── Hermes/          ← our new project (the hands + data + portfolio + envs)
        └── docs/context/  ← you are here
```

---

## 6. What "go over and beyond" looks like (the north star)

Concretely, a finished Hermes lets you do this:

```bash
# DEV: run the AI on live BTC data, paper-trade the decision, every 4 hours
hermes run --env dev --symbol BTCUSDT --interval 4h

# See how the fake portfolio is doing
hermes portfolio --env dev

# Look at every decision and trade it made, with reasoning
hermes history --env dev
```

…and later, when DEV has proven itself, the same command with `--env prod`
trades real money on Binance.

Along the way we get: a dashboard of P&L, a record of every decision and *why*
the AI made it, safety guardrails (max position size, daily loss limits,
kill-switch), and a backtest mode to replay history. All of that is detailed in
[plan.md](plan.md).

---

## 7. What this is NOT (honesty up front)

- **Not a money printer.** Even the TradingAgents authors say it's a research
  tool, results vary wildly, and it is *not financial advice*. Hermes inherits
  that. The point of DEV is precisely to find out whether it makes or loses
  money *before* it matters.
- **Not high-frequency trading.** The brain takes minutes and real LLM API money
  to make one decision (it's a big AI conversation). This is slow, deliberate
  trading — think hours/days between decisions, not milliseconds.
- **Not free to run.** Every decision burns LLM tokens (real cost) — see
  [extras.md](extras.md) for the money math.
- **Not safe to point at real money yet.** We build DEV first, on purpose.

Next: skim [concepts.md](concepts.md), then read [context.md](context.md) to see
how the brain works under the hood.
