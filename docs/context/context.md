# context.md — How the existing TradingAgents repo works

A deep, file-by-file tour of the "brain" Hermes builds on. Based on a full read
of the repository at `../TradingAgents` (fork `EdIrfan/TradingAgents`, version
0.2.5, tracking upstream `TauricResearch/TradingAgents`).

If a term is unfamiliar, see [concepts.md](concepts.md).

---

## 1. The 30-second mental model

```
ticker + date
     │
     ▼
┌──────────────────────────────────────────────────────────────────┐
│  TradingAgentsGraph (LangGraph pipeline of AI agents)              │
│                                                                    │
│  Analysts ──▶ Researchers (Bull/Bear debate) ──▶ Research Manager  │
│  (market,        │                                    │            │
│   sentiment,     ▼                                    ▼            │
│   news,      Trader (Buy/Hold/Sell proposal) ──▶ Risk Team debate  │
│   fundamentals)                                       │            │
│                                                       ▼            │
│                                          Portfolio Manager         │
│                                          (final 5-tier rating)     │
└──────────────────────────────────────────────────────────────────┘
     │
     ▼
final decision (rating) + written reports + memory-log entry
     │
     ▼
   (STOPS — no order is ever placed)
```

The entire thing is invoked with two lines:

```python
ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("BTC-USD", "2024-05-10")   # returns the rating string
```

That `.propagate()` call is the **single seam Hermes plugs into.**

---

## 2. Repository layout (what's where)

```
TradingAgents/
├── main.py                  # minimal example: build graph, propagate, print
├── test.py                  # ad-hoc scratch test
├── pyproject.toml           # package metadata + dependencies (installable lib)
├── requirements.txt         # (nearly empty; deps live in pyproject)
├── default_config.py        ← actually at tradingagents/default_config.py
├── .env.example             # template of all API keys + TRADINGAGENTS_* overrides
├── Dockerfile / docker-compose.yml   # containerized run
│
├── cli/                     # the interactive terminal app
│   ├── main.py              # Typer CLI: prompts, live dashboard, runs the graph
│   ├── utils.py             # ticker input, asset-type detection, provider menus
│   ├── models.py            # AnalystType, AssetType enums; model catalog
│   └── ...
│
├── tradingagents/           # THE LIBRARY (the brain) — this is what Hermes imports
│   ├── default_config.py    # the central settings dict (+ env-var overrides)
│   │
│   ├── graph/               # orchestration (LangGraph wiring)
│   │   ├── trading_graph.py # TradingAgentsGraph — the main entry class
│   │   ├── setup.py         # builds the node/edge graph
│   │   ├── conditional_logic.py  # the "loop again or move on?" decisions
│   │   ├── propagation.py   # builds the initial shared state
│   │   ├── signal_processing.py  # extracts the rating from PM's text
│   │   ├── reflection.py    # writes the "was I right?" lesson
│   │   ├── checkpointer.py  # crash-resume via SQLite
│   │   └── analyst_execution.py  # plan for running analysts (seq/parallel)
│   │
│   ├── agents/              # the AI agents themselves (prompts + logic)
│   │   ├── analysts/        # market, sentiment(social), news, fundamentals
│   │   ├── researchers/     # bull_researcher, bear_researcher
│   │   ├── managers/        # research_manager, portfolio_manager
│   │   ├── trader/          # trader
│   │   ├── risk_mgmt/       # aggressive/conservative/neutral debators
│   │   ├── schemas.py       # Pydantic output shapes (Trader/PM/Sentiment)
│   │   └── utils/           # agent_states, agent_utils, memory, tools, rating
│   │
│   ├── dataflows/           # DATA SOURCES (where facts come from)
│   │   ├── interface.py     # vendor router: picks yfinance vs alpha_vantage...
│   │   ├── y_finance.py     # Yahoo Finance (default vendor) — daily OHLCV
│   │   ├── alpha_vantage*.py# Alpha Vantage vendor (alt OHLCV/fundamentals/news)
│   │   ├── fred.py          # macro data (rates/inflation) from FRED
│   │   ├── reddit.py, stocktwits.py   # social sentiment sources
│   │   ├── polymarket.py    # prediction-market probabilities
│   │   ├── symbol_utils.py  # maps broker symbols → Yahoo symbols
│   │   ├── market_data_validator.py   # anti-hallucination price snapshot
│   │   └── errors.py        # typed vendor errors (NoMarketDataError, ...)
│   │
│   └── llm_clients/          # provider adapters (OpenAI/Anthropic/Google/...)
│       ├── factory.py        # create_llm_client(provider, model, ...)
│       ├── model_catalog.py  # known models per provider
│       └── *_client.py       # one per provider family
│
└── tests/                    # ~50 pytest files — a strong safety net to emulate
```

**The only part Hermes strictly needs is the `tradingagents/` library**, and
within it, `graph/trading_graph.py`'s `TradingAgentsGraph.propagate()`.

---

## 3. The pipeline, node by node

All wiring lives in `tradingagents/graph/setup.py` (`GraphSetup.setup_graph`).
It builds a LangGraph `StateGraph` whose shared state is `AgentState`
(`agents/utils/agent_states.py`).

### 3.1 Analysts (data gathering)
Selected via `selected_analysts=("market","social","news","fundamentals")`.
Each analyst is a node that can call **tools** (a `ToolNode`) in a loop until it
has enough data, then writes its report into state and clears its scratch
messages. The tool sets per analyst (from `trading_graph.py:_create_tool_nodes`):

- **market** → `get_stock_data`, `get_indicators`, `get_verified_market_snapshot`
- **social** → `get_news` (reads StockTwits/Reddit-style sentiment)
- **news** → `get_news`, `get_global_news`, `get_insider_transactions`,
  `get_macro_indicators`, `get_prediction_markets`
- **fundamentals** → `get_fundamentals`, `get_balance_sheet`, `get_cashflow`,
  `get_income_statement`

The conditional logic `should_continue_<analyst>` (in `conditional_logic.py`)
loops the analyst back to its tools while it keeps requesting data, then routes to
a "Msg Clear" node and on to the next analyst. Analysts run **sequentially** by
default (`analyst_concurrency_limit: 1`), configurable.

> **Crypto note:** the CLI's `filter_analysts_for_asset_type` drops the
> **fundamentals** analyst for crypto (a coin has no balance sheet). So a crypto
> run uses market + social + news.

### 3.2 Researchers (the Bull/Bear debate)
`Bull Researcher` and `Bear Researcher` alternate, each arguing their side using
the analyst reports. `should_continue_debate` counts turns and stops after
`2 * max_debate_rounds` exchanges (default `max_debate_rounds: 1` → ~one round
each), then routes to the Research Manager.

### 3.3 Research Manager
A **deep-thinking** LLM node. Reads the whole debate and emits a structured
`ResearchPlan` (`schemas.py`): a `recommendation` (5-tier), a `rationale`, and
`strategic_actions` for the trader. Rendered to markdown into
`state["investment_plan"]`.

### 3.4 Trader
Turns the plan into a structured `TraderProposal` (`schemas.py`):
- `action`: **Buy / Hold / Sell**
- `reasoning`
- optional `entry_price`, `stop_loss`, `position_sizing`

Rendered into `state["trader_investment_plan"]`, ending with a literal line
`FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` (kept for backward-compat parsing).

> **This is the richest signal for Hermes**: it already contains an action,
> entry, stop, and sizing hint. Hermes can read `TraderProposal` *and* the final
> PM rating.

### 3.5 Risk team
`Aggressive`, `Conservative`, `Neutral` debators take turns (round-robin) for
`3 * max_risk_discuss_rounds` turns, stress-testing the proposal.

### 3.6 Portfolio Manager (final word)
A **deep-thinking** node. Emits a structured `PortfolioDecision` (`schemas.py`):
- `rating`: **Buy / Overweight / Hold / Underweight / Sell** (the final answer)
- `executive_summary`, `investment_thesis`
- optional `price_target`, `time_horizon`

Rendered into `state["final_trade_decision"]`. The graph then hits `END`.

### 3.7 Output
`propagate()` returns `(final_state, decision)` where `decision` is the rating
string (extracted by `SignalProcessor.process_signal`, a deterministic parse of
the PM markdown — no extra LLM call). The full state is also written to
`~/.tradingagents/logs/<TICKER>/TradingAgentsStrategy_logs/full_states_log_<date>.json`.

---

## 4. The data layer (what Hermes must extend)

`dataflows/interface.py` is a **vendor router**. Each data category
(`core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`,
`macro_data`, `prediction_markets`) maps to a vendor chain configured in
`default_config.py` under `data_vendors`. Today:

- `core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data` →
  **`yfinance`** (Yahoo Finance) by default, with **`alpha_vantage`** as an
  alternative.
- `macro_data` → **`fred`** (needs `FRED_API_KEY`).
- `prediction_markets` → **`polymarket`** (keyless).

### Key facts that drive Hermes's design

1. **Data is daily and historical.** `get_YFin_data_online(symbol, start, end)`
   pulls **daily** candles between two dates. There is **no intraday/live tick
   feed** and **no Binance**. The "current price" is just the latest daily close.

2. **Symbol mapping already exists** (`symbol_utils.py`): it converts broker-style
   symbols to Yahoo's (`BTCUSDT`/`BTCUSD` → `BTC-USD`, `XAUUSD` → `GC=F`, etc.).
   Hermes must do the *reverse-ish* mapping too: Binance uses `BTCUSDT`, Yahoo
   uses `BTC-USD`. We'll need a translation layer.

3. **Anti-hallucination guard** (`market_data_validator.py` +
   `get_verified_market_snapshot`): the market analyst is *required* to fetch a
   verified price snapshot so it can't invent numbers. Good — it means the brain
   anchors on real data we feed it.

4. **Staleness guard** (`_assert_ohlcv_not_stale`): the data layer raises if it
   gets old data. Relevant when we feed live data — it must be fresh.

> **Hermes's data plan, in one line:** add a **Binance vendor** (or a thin live
> adapter) so the brain's market analyst sees current crypto prices, while leaving
> the rest of the data layer (news/sentiment/macro) as-is for now. Detailed in
> [plan.md](plan.md).

---

## 5. Configuration & how behavior is controlled

`tradingagents/default_config.py` is the central settings dict. Notable keys:

| Key | Default | Meaning for Hermes |
|-----|---------|--------------------|
| `llm_provider` | `"openai"` | Which AI company. Pick what you have a key for. |
| `deep_think_llm` | `"gpt-5.5"` | Model for the heavy nodes (Research Mgr, PM). |
| `quick_think_llm` | `"gpt-5.4-mini"` | Model for the lighter nodes. |
| `max_debate_rounds` | `1` | More = deeper but pricier/slower. |
| `max_risk_discuss_rounds` | `1` | Same trade-off for the risk team. |
| `data_vendors` | yfinance/fred/polymarket | Where Hermes will add `binance`. |
| `results_dir` | `~/.tradingagents/logs` | Where full-state JSON logs go. |
| `memory_log_path` | `~/.tradingagents/memory/trading_memory.md` | The reflection/learning file. |
| `temperature` | `None` | Lower → more repeatable. |

Crucially, **every key can be overridden by environment variables** (the
`TRADINGAGENTS_*` family, mapped in `default_config.py`) without editing code.
That is *exactly* the hook Hermes uses to give DEV and PROD different configs —
each environment just sets different env vars / passes a different config dict.

---

## 6. Persistence & learning (already built)

- **Decision log / memory** (`agents/utils/memory.py`, `TradingMemoryLog`): every
  run appends its decision to a markdown file. On the next run for the same
  ticker, it fetches the *realized return* (did the price move as predicted?),
  generates a one-paragraph **reflection**, and injects recent lessons into the
  Portfolio Manager's prompt. A built-in feedback loop.
  - **For Hermes this is gold:** the brain already wants to know "what actually
    happened after my last call?" Hermes's portfolio gives a *much* better answer
    (actual fills and P&L) than the current price-only lookup. We can enrich it.
- **Checkpoint/resume** (`graph/checkpointer.py`): opt-in SQLite save-after-each-
  node so a crashed run resumes. Per-ticker `.db` files.

---

## 7. The CLI (a reference, not a dependency)

`cli/main.py` is a polished **Typer + Rich** terminal app: it prompts for ticker,
date, provider, model, analysts, depth; detects asset type (stock vs crypto);
then streams a live dashboard of the agents working. Hermes does **not** need the
CLI — but it's an excellent reference for:
- how to construct and run `TradingAgentsGraph` end-to-end,
- how asset-type detection and analyst filtering work for crypto,
- how to display progress.

Hermes will have its *own* CLI focused on trading (run/portfolio/history), reusing
these patterns.

---

## 8. Dependencies worth knowing

From `pyproject.toml`: `langchain-*` (LLM glue), `langgraph` (the pipeline),
`yfinance` (data), `stockstats` (indicators), `pandas` (data frames),
`questionary`/`rich`/`typer` (CLI), `redis` (optional caching),
`langgraph-checkpoint-sqlite` (resume), and notably **`backtrader`** — a
backtesting library that is **listed but never imported anywhere in the code**.
That tells us backtesting was *intended* but not implemented — another gap Hermes
can fill if we want backtests.

For Hermes we'll add: a **Binance client** (likely `python-binance` or `ccxt`),
and whatever we choose for scheduling/storage.

---

## 9. What this means for Hermes (the seams we plug into)

| Need | Existing seam to use |
|------|---------------------|
| Get a decision | `TradingAgentsGraph(...).propagate(symbol, date, asset_type="crypto")` |
| Read action + entry/stop/size | parse `final_state["trader_investment_plan"]` / the `TraderProposal`; and the PM rating |
| Feed live price to the brain | add a Binance vendor in `dataflows` *or* inject a live snapshot via config; pass current date as `trade_date` |
| Configure per environment | pass a distinct `config` dict / `TRADINGAGENTS_*` env vars per env |
| Learn from outcomes | extend the memory/reflection layer with real portfolio P&L |
| Don't reinvent symbol mapping | reuse/extend `dataflows/symbol_utils.py` |

The brain is well-factored and library-friendly. Hermes is mostly **new code
around it**, not changes inside it. Architecture and the phased build are in
[plan.md](plan.md); the DEV/PROD specifics are in [environments.md](environments.md).
