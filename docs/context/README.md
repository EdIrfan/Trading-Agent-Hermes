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

## Current status

- ✅ Explored and understood the full TradingAgents repository.
- ✅ Documentation written (this folder).
- ⬜ No Hermes code written yet — per your instruction, this pass is **docs only**.
- ⬜ Open decisions in [decisions.md](decisions.md) still need your answers.

When you're ready to build, start with [todo.md](todo.md) Phase 0.
