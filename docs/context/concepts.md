# concepts.md — Every concept, explained

A glossary written for a beginner. Grouped by topic. No concept is too small.
When something in another doc is unfamiliar, look it up here. Terms are roughly
ordered easy → advanced within each section.

---

## A. Trading & markets — the absolute basics

**Asset / instrument** — a thing you can buy and sell. A stock (a share of a
company), a cryptocurrency (Bitcoin), gold, etc. "Instrument" is the formal word.

**Ticker / symbol** — the short code for an asset. `AAPL` = Apple stock.
`BTC-USD` = Bitcoin priced in US dollars. Exchanges use slightly different
spellings: Yahoo Finance writes `BTC-USD`, Binance writes `BTCUSDT`. Translating
between these spellings is a real task Hermes must handle (see "symbol mapping").

**Exchange** — the marketplace where buyers and sellers meet. The New York Stock
Exchange for stocks; **Binance** for crypto. The exchange matches your buy order
with someone else's sell order.

**Crypto / cryptocurrency** — digital assets like Bitcoin (BTC), Ethereum (ETH).
Traded 24/7 (unlike stocks, which have market hours). This is what Hermes targets.

**Fiat** — government money like US dollars (USD). On Binance most crypto is
priced against a **stablecoin** called **USDT** (Tether), which is designed to be
worth ~\$1. So `BTCUSDT` means "price of 1 Bitcoin in USDT (≈ dollars)".

**Quote currency vs base currency** — in the pair `BTCUSDT`, **BTC is the base**
(what you're buying) and **USDT is the quote** (what you pay with). "The price"
is how much quote currency one unit of base costs.

**Position** — what you currently own (or owe). "I have a position in Bitcoin"
means you hold some Bitcoin. **Flat / no position** means you hold none.

**Long vs short**
- **Long** = you *buy* hoping the price goes **up** (the normal thing). You profit
  if it rises.
- **Short** = you *bet the price goes down* (you borrow and sell now, buy back
  cheaper later). More advanced and riskier. Hermes will likely start **long-only**
  (buy or stay in cash) to keep DEV simple.

**Spot vs futures / margin**
- **Spot** = you buy the actual coin with cash you have. Simple, no borrowing.
- **Futures / margin / leverage** = trading with borrowed money to amplify gains
  *and losses*. Much riskier. **Hermes starts spot-only.** Leverage is a later,
  deliberate decision (see [decisions.md](decisions.md)).

**Order** — your instruction to the exchange to trade.
- **Market order** — "buy/sell right now at whatever the current price is." Fast,
  simple, but you might pay slightly more/less than you expected (**slippage**).
- **Limit order** — "buy/sell only at this price or better." You control price but
  it might never fill.

**Fill** — when your order actually executes (someone took the other side). A
"partial fill" means only some of your order traded.

**Slippage** — the difference between the price you expected and the price you
actually got. Happens with market orders in fast or thin markets.

**Bid / ask / spread**
- **Bid** = highest price a buyer will pay right now.
- **Ask** = lowest price a seller will accept right now.
- **Spread** = the gap between them. You generally buy at the ask, sell at the
  bid, so the spread is a hidden cost.

**Liquidity** — how easily you can trade without moving the price. Bitcoin is very
liquid; an obscure coin is not. Low liquidity → more slippage.

**Fees / commission** — the exchange's cut on each trade (Binance spot is often
~0.1%). Small but they add up and must be modeled even in DEV, or paper results
will look better than reality.

---

## B. Reading the market — price data & indicators

**OHLCV** — the five numbers that summarize price over a time window:
- **O**pen (price at the start), **H**igh, **L**ow, **C**lose (price at the end),
  **V**olume (how much was traded). One row of OHLCV = one **candle**.

**Candle / candlestick** — a visual bar showing OHLCV for one period (e.g. one
day, or one hour). A "daily candle" covers a whole day.

**Timeframe / interval** — the length each candle covers: `1m` (minute), `1h`
(hour), `1d` (day). TradingAgents currently uses **daily** candles. For live
crypto trading we may want shorter (e.g. `1h` or `4h`).

**Historical vs real-time (live) data**
- **Historical** — past prices, used to analyze a date in the past or to backtest.
- **Real-time / live** — the current price, right now. Hermes needs this so the
  brain reasons about *now* and we trade at *current* prices. TradingAgents only
  fetches end-of-day historical candles today; adding live data is a Hermes job.

**Technical indicator** — a formula computed from price/volume that tries to
summarize a pattern. The brain's Market Analyst uses these:
- **Moving Average (MA / SMA / EMA)** — the average price over the last N periods,
  smoothing out noise. Price above its moving average = uptrend, loosely.
- **MACD (Moving Average Convergence Divergence)** — compares two moving averages
  to spot momentum shifts (trend turning up or down).
- **RSI (Relative Strength Index)** — a 0–100 gauge of how fast price has risen.
  Above ~70 = "overbought" (maybe due for a pullback); below ~30 = "oversold".
- **Bollinger Bands** — a band around the moving average showing volatility; price
  hitting the upper/lower band signals stretched conditions.
- **ATR (Average True Range)** — how much the price typically moves; used to size
  stop-losses to volatility.

You don't need to master these — the AI uses them. But knowing the names helps
you read the reports it produces.

**Volatility** — how much the price jumps around. High volatility = bigger swings
= more risk and more opportunity. Crypto is very volatile.

**Fundamental data** — facts about the *business* behind a stock: revenue,
profit, debt (the "balance sheet", "income statement", "cash flow"). **Crypto has
no fundamentals** in this sense, which is why TradingAgents skips the Fundamentals
Analyst for crypto.

**Sentiment** — the *mood* of the crowd: are people on Reddit/StockTwits/news
bullish (optimistic) or bearish (pessimistic)? A "soft" signal but often moves
crypto a lot.

**Macro / macroeconomic data** — big-picture economy numbers: interest rates,
inflation, jobs. Pulled from **FRED** (a free US Federal Reserve data service).
Affects all markets. Less central for crypto but still used by the News Analyst.

---

## C. Decisions, risk & money management

**Buy / Hold / Sell** — the three basic actions. Buy (enter/add), Hold (do
nothing), Sell (exit/reduce).

**The 5-tier rating** — TradingAgents' Portfolio Manager outputs one of:
**Buy → Overweight → Hold → Underweight → Sell** (most bullish to most bearish).
"Overweight" = lean in / add a bit; "Underweight" = trim / reduce. Hermes must
translate these five words into an actual order (e.g. how much to buy).

**Position sizing** — *how much* to buy, not just whether. "Risk 2% of the
portfolio on this trade." Sizing is how you survive being wrong: small sizes mean
one bad call doesn't wipe you out. The Trader and Portfolio Manager suggest sizing
in words; Hermes must turn words into a number.

**Entry price** — the price you aim to buy at.

**Stop-loss** — a pre-set price at which you automatically sell to cap your loss.
"Buy at 100, stop-loss at 90" = you accept losing at most ~10%. Critical safety
tool. The Trader proposes one; Hermes can enforce it.

**Take-profit** — the mirror of a stop-loss: a price at which you sell to lock in
a gain.

**P&L (Profit and Loss)** — how much money you've made or lost.
- **Realized P&L** — locked in after you've sold.
- **Unrealized P&L** — paper gain/loss on positions you still hold (changes as the
  price moves).

**Return** — percentage change. Buy at 100, now 110 = +10% return.

**Alpha** — return *above a benchmark*. If Bitcoin (your benchmark) rose 8% and
your trades made 10%, your **alpha is +2%** — you beat the market by 2. Beating
the benchmark is the real goal; just riding the market up isn't skill.
TradingAgents computes alpha vs SPY (S&P 500) for stocks; for crypto we'd
benchmark against BTC or a buy-and-hold baseline.

**Benchmark** — the "do nothing clever" baseline you compare against (e.g.
buy-and-hold Bitcoin). If your bot can't beat just holding, it isn't adding value.

**Drawdown** — the biggest drop from a peak in your account value. "Max drawdown
30%" means at the worst point you were down 30% from your high. Measures pain.

**Risk management** — the discipline of not blowing up: position limits, stop
losses, daily loss limits, diversification. Hermes will enforce hard guardrails
*outside* the AI, so even a bad AI decision can't exceed your limits.

**Kill-switch** — an emergency "stop everything" control. Halts new trades (and
optionally liquidates) instantly. Essential for PROD.

---

## D. Testing strategies safely

**Paper trading** — trading with **fake money on real (live) prices**. No real
orders, no real risk, but realistic results. This is exactly what Hermes **DEV**
is. The gold-standard way to test a strategy before risking capital.

**Backtesting** — running a strategy against **past** data to see how it *would
have* done. Faster than paper trading (you can replay a year in minutes) but prone
to **look-ahead bias** (accidentally using information from the future) and
**overfitting** (tuning until it looks great on history but fails live). The
`backtrader` library is a dependency of TradingAgents but is currently unused.

**Forward testing** — testing going forward in real time. Paper trading is forward
testing with fake money.

**Look-ahead bias** — the classic backtest bug: letting the strategy "see" data it
couldn't have known at the time (e.g. today's news when deciding yesterday's
trade). TradingAgents has guards against this (e.g. news lookahead tests) but live
social/news data still reflects "now," which is a known limitation.

**Overfitting** — making a strategy fit past data so perfectly it just memorized
noise and fails on new data. Why paper/forward testing matters more than a pretty
backtest.

---

## E. AI / LLM concepts

**LLM (Large Language Model)** — the AI behind ChatGPT/Claude/Gemini. You give it
text, it returns text. TradingAgents uses LLMs as the "reasoning" of every agent.

**Provider / model** — the company and the specific model. Provider = OpenAI,
Anthropic, Google, etc. Model = `gpt-5.5`, `claude-opus-4-8`, etc. TradingAgents
supports many; you pick one (and need an **API key** for it).

**API key** — a secret password that lets your code use a paid service (an LLM, or
Binance). Must be kept secret (see [extras.md](extras.md) on security). Stored in a
`.env` file, never committed to git.

**Token** — the unit LLMs read and bill in (~¾ of a word). Every report the agents
write and read costs tokens, and tokens cost money. A full TradingAgents run is a
*lot* of tokens (many agents, long reports, debates). Budgeting this matters.

**Prompt** — the instructions/text you send the LLM. Each agent has a system
prompt ("you are a market analyst…") plus the data.

**Agent** — an LLM given a **role**, a **goal**, and **tools** it can call. E.g.
the Market Analyst agent is told "you analyze price data" and given a
`get_stock_data` tool. It decides when to call tools and writes a report.

**Tool / tool-calling / function-calling** — letting an LLM *run code* by emitting
a structured request like `get_stock_data("BTC-USD", "2024-01-01", "2024-05-01")`.
The framework runs the function and feeds the result back. This is how agents fetch
real data instead of hallucinating it.

**Multi-agent system** — many agents collaborating, each specialized, passing work
to each other — exactly TradingAgents' design (analysts → researchers → trader →
risk → PM).

**Structured output** — forcing the LLM to return data in a strict shape (a JSON
schema / Pydantic model) instead of free prose, so code can reliably read it.
TradingAgents uses this for the Trader and Portfolio Manager so their Buy/Sell and
ratings are machine-readable.

**Pydantic** — a Python library for defining strict data shapes (schemas) and
validating them. `TraderProposal`, `PortfolioDecision` in the code are Pydantic
models.

**Hallucination** — when an LLM confidently makes something up (e.g. inventing a
price). TradingAgents fights this with a "verified market snapshot" and
deterministic instrument identity so agents anchor to real numbers.

**Temperature** — a knob (0–~1) for LLM randomness. 0 = focused/repeatable,
higher = more creative/varied. Lower temperature → more reproducible runs.

**Reasoning / thinking effort** — newer models can "think" longer before
answering. Providers expose an effort level (low/medium/high). More thinking =
better (and pricier) answers. TradingAgents exposes this per provider.

**Reflection / memory** — TradingAgents records each decision, later checks whether
it was right (did the price go the predicted way?), writes a one-paragraph lesson,
and feeds recent lessons into future decisions. A simple form of learning from
outcomes, stored in a markdown file.

**Non-determinism** — same input, different output. LLMs don't give identical
answers twice (even at temperature 0). This means two runs of the brain on the
same coin can disagree. It's expected, and a reason to think in terms of many
decisions over time, not one.

---

## F. Software & infrastructure concepts

**LangChain** — a popular Python toolkit for building LLM apps (prompts, tools,
model adapters). TradingAgents uses it to talk to every provider uniformly.

**LangGraph** — a companion library for building **graphs** of LLM steps: nodes
(agents) connected by edges (who runs next), with shared state. TradingAgents'
whole pipeline is a LangGraph. Think flowchart where each box is an AI agent.

**Node / edge / graph** — graph vocabulary. A **node** is a step (an agent). An
**edge** is an arrow to the next step. A **conditional edge** chooses the next step
based on state (e.g. "debate again or stop?"). The **state** is a shared dictionary
every node reads and writes.

**State** — the shared memory passed through the graph: the ticker, the date, each
analyst's report, the debate transcripts, the final decision. Defined as
`AgentState` in the code.

**Checkpoint / resume** — saving progress after each step so a crashed run can
continue instead of restarting (and re-spending tokens). Opt-in in TradingAgents,
backed by small SQLite databases.

**SQLite** — a tiny, file-based database (no server needed). TradingAgents uses it
for checkpoints. Hermes may use it (or just files) for the portfolio ledger.

**Environment variable (env var)** — a setting passed to a program from outside the
code, e.g. `OPENAI_API_KEY=...`. Kept in a `.env` file. Lets you change behavior
(or switch DEV/PROD) without editing code. TradingAgents reads many `TRADINGAGENTS_*`
env vars.

**.env file** — a plain text file of `KEY=value` lines holding secrets and config.
**Never committed to git** (it's in `.gitignore`). Each environment (DEV/PROD) will
have its own.

**Configuration (config)** — the dictionary of settings (which model, how many
debate rounds, which data vendor). TradingAgents centralizes this in
`default_config.py`.

**Adapter / abstraction layer** — a piece of code that hides differences behind a
common interface. Hermes will have a **Broker** abstraction: one interface
(`place_order`, `get_balance`) with two implementations — `PaperBroker` (DEV) and
`BinanceBroker` (PROD). Swapping environments = swapping which implementation is
used. This is the single most important design idea in Hermes.

**Interface / API (Application Programming Interface)** — a defined set of
functions one piece of software offers to another. "The Binance API" = the
functions Binance lets your code call (get price, place order). "Hermes's Broker
interface" = the functions every broker must provide.

**REST API vs WebSocket**
- **REST** — request/response: you ask, you get one answer (e.g. "what's the BTC
  price?"). Simple, used for placing orders and one-off queries.
- **WebSocket** — a persistent stream: the exchange pushes you live updates
  continuously (e.g. every price tick). Used for real-time data. We may start with
  REST polling (simpler) and add WebSocket later.

**Rate limit** — a cap on how many requests you may make per minute. Both LLM
providers and Binance enforce them. Hammering the API gets you temporarily blocked,
so Hermes must pace itself.

**Idempotency** — making an operation safe to repeat. If Hermes crashes after
sending a buy but before recording it, retrying must not buy twice. Achieved with
unique **client order IDs**. Crucial for real-money PROD.

**Ledger** — the running record of every transaction and the resulting balances.
Hermes's portfolio is a ledger: each fill appends a row; the balance is derivable
from the rows. The source of truth for "how am I doing?".

**Scheduler / cron / loop** — what makes the bot run on a cadence (e.g. "decide
every 4 hours") instead of once by hand. Could be a simple loop, a cron job, or an
AI coding agent's built-in scheduler (e.g. Claude Code's `/schedule` and `/loop`).

**Dry-run** — executing all the logic but stopping short of the irreversible step
(placing a real order), printing what *would* happen. A safety feature for PROD.

**Logging / audit trail** — recording what happened and why, so you can review
every decision and trade after the fact. Non-negotiable for something touching
money.

**Library vs application**
- **Library** — code meant to be imported and used by other code (TradingAgents is
  used this way by Hermes).
- **Application** — a runnable program with an entry point (Hermes is this).

**Fork / upstream** — your copy of someone's repo (`EdIrfan/TradingAgents` is a
**fork**) tracks the original (`TauricResearch/TradingAgents` is the **upstream**).
You can pull their updates into your fork.

**Virtual environment (venv / conda)** — an isolated Python install per project so
dependencies don't collide. Hermes will have its own, and will install
TradingAgents into it.

---

## G. Money & safety vocabulary specific to going live

**Testnet** — a fake version of an exchange for developers. **Binance has a
Spot Testnet** with fake balances but the real API surface — perfect for testing
the *PROD code path* without real money. A great intermediate step between DEV
(our own paper simulator) and PROD (real Binance).

**Mainnet** — the real exchange with real money. PROD targets this.

**API key permissions** — Binance lets you create keys that can *read only*, or
*trade*, or *withdraw*. **Never enable withdrawal** on a bot key. Restrict by IP.

**Custody** — who holds the coins. On an exchange, the exchange does. Relevant to
security but beyond DEV scope.

**Compliance / KYC / tax** — the legal side: identity verification to use Binance,
and the fact that real trading has tax consequences. Flagged in [extras.md](extras.md);
not a coding concern for DEV.

---

If a term shows up in another doc and isn't here, it's worth adding — tell me and
I'll extend this file.
