# Data Agent (Morgane)

- `data_agent.ipynb`: downloads the prices of our 50 ETFs from Yahoo Finance, fixes the Yahoo errors we checked by hand (unadjusted splits of EURO BANKS and PALLADIUM LVG, corrupted day 24 Oct 2025), adds the leverage factor of each ETF, checks data quality, computes risk metrics, and has a mini LangGraph agent (Gemini) write a short data report for the team.
- Reads `data/tickers.csv` (our 50 ETFs + Yahoo symbols, 8 fixed by hand: never regenerate it).
- Today's row is always dropped (Paris time): before the close Yahoo gives intraday prices, and orders use the previous day's close.
- The AI data report is off by default (`USE_AI_DATA_REPORT = False`) to save the free Gemini quota: with it off, Gemini is never called. To switch it on, use the same key as the other notebooks: `LLM_API_KEY` in Colab Secrets or in a `.env` file. Never put the key on GitHub.
- Francesco's `Portfolio_Manager/team_graph.ipynb` uses a copy of this code for its **data** node: change it here first, then copy it there (list in section 9).

Outputs (read by the other agents, don't rename columns without telling the team):
- `data/prices.csv` -> one row per day and ETF: `date, code, isin, yahoo, theme, currency, close, adj_close, volume, leverage, return`. `close` = raw price (orders at T-1 close), `adj_close` = with dividends (performance).
- `data/metrics.csv` -> one row per ETF: returns (1w to 1y), volatility (1m, 3m, 1y), drawdowns, leverage, currency, liquidity.
- `data/data_issues.csv` -> one row per data problem found (extreme move, zero-volume print, gap, short history, not in EUR...).
- `data/data_report.md` -> the AI's data report.

Interfaces:
- `full()` / `update()` -> rebuild / extend `data/prices.csv`
- `build_outputs()` -> writes `metrics.csv` + `data_issues.csv`, returns a short summary
- `run_data_agent(use_ai=False)` -> refreshes everything and returns the data report (used by the **data** node of the team graph)

## How to run
1. Open the notebook in Jupyter (or Colab, from the repo so `data/tickers.csv` is found).
2. Optional: set `USE_AI_DATA_REPORT = True` and add your Gemini key as `LLM_API_KEY` in `.env` (or Colab Secrets).
3. Run all cells. Run it **before** the other notebooks on each trading day, so they read fresh prices.
4. If the check finds a new split or a corrupted day: add it to `SPLITS` / `BAD_DATES` (section 1) and run `full()` again.
