# Technical Analysis agent (Juliet)

**Question it answers:** which ETFs have the price trend on their side right now, and is it a good moment to enter?

- **`technical_agent.py`**: the agent (pure Python, **no AI call**: same rule as the team graph, *the AI never computes a number*, and it keeps working when Gemini is over its free quota). Main function: `run_technical_agent(prices)`.
- **`technical_agent.ipynb`**: today's signals, the evidence behind them, and how to plug the agent into `team_graph.ipynb`.
- **`results/`**: `ic_table.csv` (which indicators predict returns) and `competition_replay.csv` (the competition replayed 243 times on history).

## What it outputs
`run_technical_agent(prices)` returns a dict:

| Key | Content |
|---|---|
| `signals` | one row per ETF: `tech_view` (positive / neutral / negative), `confidence`, `tech_score`, `mom_rank`, `mom_6m_%`, `mom_12_1_%`, `vs_ma50_%`, `rsi14`, `breakout_20d`, `behaviour`, `timing_note`, `reason` |
| `theme_views` | one net view per theme, **same format as the macro agent** (`theme → view, reason, sources`) |
| `summary` | ready-to-use text for the Portfolio Manager prompt (`technical_signals=` in `build_pm_prompt`) |

Plus `technical_conflicts(...)`: the same check as the macro one: buying an ETF with a **negative technical view** needs *"Contrary to technical signal because ..."* in its reason.

## How the view is built
1. **Momentum (main signal).** `tech_score` = average percentile rank (0 = worst, 1 = best) of 6-month and 12-1-month returns across our ETFs. Cash and leveraged twins are not ranked.
2. **Trend filter.** Positive only if `tech_score ≥ 0.67` **and** price above its 50-day average; negative only if `≤ 0.33` **and** below.
3. **Timing notes (weak signals).** Trending ETFs: 20-day breakout (+ volume check). Mean-reverting ETFs: pullback in an uptrend (RSI < 40, price above MA50). Any ETF: overbought warning (RSI > 70).
4. **Leveraged / inverse** (NASDAQ 3X, EURO STOXX 2X, S&P 500 SHORT, STOXX SHORT) follow their unleveraged twin, inverse = flipped, never "high" confidence.

## Evidence (2022–2026, our 50 ETFs, close prices, no dividends)
| Indicator | IC 5 days (t-stat) | IC 10 days (t-stat) | Positive years |
|---|---|---|---|
| **tech_score (momentum)** | **0.044 (2.7)** | **0.053 (2.1)** | **5/5** |
| 50-day trend | 0.021 (1.1) | 0.024 (1.0) | 3/5 |
| 20-day breakout | 0.016 (1.3) | 0.015 (0.8) | 3–4/5 |
| RSI | 0.021 (1.3) | 0.029 (1.5) | 3–4/5 |
| Low volatility | −0.027 (−1.1) | −0.036 (−1.2) | 2–3/5 |

**Competition replay** (243 windows, real rules: 5 trading days, max 5 orders, T-1 close, no dividends): the pure-technical strategy earns **+0.6% more than WORLD on average per window**, but beats it only **~49% of the time** (gains concentrated in strong trends, e.g. 2025; it lost in 2023). Conclusion: momentum is a useful input, not an autopilot: it works best combined with the macro view, the risk rules and human judgement.

## How to run
1. Colab: upload `prices.csv` (from `data/`) and `technical_agent.py`, open `technical_agent.ipynb`, run all cells (no API key needed).
2. In the repo: open the notebook from the project folder; `data/prices.csv` is found automatically.

## Plugging it into `team_graph.ipynb`
See section 6 of the notebook: one `technical_node` after `macro`, pass `state["technical"]["summary"]` as `technical_signals` to `ask_portfolio_manager`, and add `technical_conflicts(...)` to `validate_node`.
