# Technical Analysis agent (Juliet)

**Question it answers:** which ETFs have the price trend on their side right now, and is it a good moment to enter?

- **`technical_agent.py`**: the agent (pure Python, **no AI call**: same rule as the team graph, *the AI never computes a number*, and it keeps working when Gemini is over its free quota). Main function: `run_technical_agent(prices)`.
- **`technical_agent.ipynb`**: today's signals, the evidence behind them, and how to plug the agent into `team_graph.ipynb`.
- **`results/`**: `ic_table.csv` (which indicators predict returns), `indicator_correlation.csv` and `indicator_ic_correlation.csv` (how indicators relate to each other), `combination_test.csv` (does adding a second indicator help?), `etf_correlation_1y.csv`, `lead_lag_test.csv` and `divergence_test.csv` (correlations between ETFs, delays, divergence strategy), `competition_replay.csv` (the competition replayed 243 times on history).

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

**Correlations between indicators** (notebook section 5):
- Short-term trend indicators carry almost the **same information**: 1-month momentum, price vs MA50 and RSI correlate 0.76–0.84 (MACD ≈ 0.5). Using two of them counts the same thing twice.
- Long-term (12-1) momentum is a **different** signal: ≈ 0 correlation with the short-term group (0.07 with 1-month momentum, −0.10 with MACD).
- Negative correlation: volatile ETFs tend to be far below their 52-week high (−0.58).
- Combining 12-1 momentum with a second indicator does **not** beat 12-1 alone (MACD clearly hurts). More indicators ≠ better: one long-term momentum signal drives the view, MA50 is only a filter, RSI / breakout are timing notes.

**Correlations between ETFs, delays and the divergence strategy** (notebook section 6):
- Many ETFs are almost the same bet (WORLD–S&P 500 0.97, gold miners–silver miners 0.96, energy–oil & gas 0.93): useful for the Risk agent.
- Real opposite moves are rare: strongly negative pairs all involve the inverse ETFs; between normal ETFs only 1.8% of pairs are below −0.3.
- **Lead-lag:** the strongest "A today → B 1–2 days later" pairs found in 2022–2024 almost vanish in 2025–2026 (|corr| 0.26 → 0.05); most were artefacts of an ETF with only 39 days of data.
- **Divergence / catch-up strategy** (A moved, B did not move as usual → bet that B catches up): right **≈ 50% of the time** for every pair type (38,192 events since 2022). Juliet's exact case (A up, B "should have fallen" but did not): B fell 50.2% of the time vs 50.7% without the signal. Linked ETFs adjust on the same day, so there is no exploitable delay at our 5–10-day horizon. Not used in the agent.

**Competition replay** (243 windows, real rules: 5 trading days, max 5 orders, T-1 close, no dividends): the pure-technical strategy earns **+0.6% more than WORLD on average per window**, but beats it only **~49% of the time** (gains concentrated in strong trends, e.g. 2025; it lost in 2023). Conclusion: momentum is a useful input, not an autopilot: it works best combined with the macro view, the risk rules and human judgement.

**Rules-only benchmarks, with drawdown** (notebook section 7b, 243 windows, same competition rules):

| Strategy | Avg return per window | Beats WORLD | Worst window | Avg max drawdown | Return per unit of drawdown |
|---|---|---|---|---|---|
| WORLD | +0.61% | – | −12.9% | −2.4% | 0.25 |
| AI dry-run portfolio, held fixed (defensive) | +0.23% | 40% | −4.5% | −1.3% | 0.17 |
| Momentum top 5 | +1.23% | 50% | −11.4% | −4.2% | 0.29 |
| Momentum + team risk rules | +0.82% | 47% | −7.6% | −3.3% | 0.25 |

The defensive portfolio our AI tends to choose has the smallest drawdowns but also the lowest return, and less return per unit of drawdown than WORLD. The AI itself is **not** backtested (look-ahead bias: Gemini knows these years; no historical headlines; free quota): it is compared forward, with a shadow rules-only portfolio.

## How to run
1. Colab: upload `prices.csv` (from `data/`) and `technical_agent.py`, open `technical_agent.ipynb`, run all cells (no API key needed).
2. In the repo: open the notebook from the project folder; `data/prices.csv` is found automatically.

## Plugging it into `team_graph.ipynb`
See section 8 of the notebook: one `technical_node` after `macro`, pass `state["technical"]["summary"]` as `technical_signals` to `ask_portfolio_manager`, and add `technical_conflicts(...)` to `validate_node`.
