# Portfolio Manager (Francesco)

**team_graph.ipynb** is the integrated notebook the team uses on each trading day. It runs the whole process as a LangGraph graph:

`data → macro → technical → portfolio_manager → validate → human_approval → orders → risk → log`

- Data (Morgane) and Macro/News + risk rules (Gonçalo) are included in the notebook; the Technical agent (Juliet) is imported from `Technical_code/technical_agent.py`.
- Python computes every number; the AI (Gemini) only writes the macro view and proposes the portfolio; the team approves, edits or rejects before any order.
- The Gemini key is read from Colab Secrets (`LLM_API_KEY`) or from a `.env` file: it is never written in the code.

## How to run (Google Colab)
1. Upload `data/prices.csv`, `data/tickers.csv` and `Technical_code/technical_agent.py`. On a real trading day, also upload `portfolio.csv` and `trade_log.csv` from the previous day.
2. Run the cells one at a time, from top to bottom (not "Run all").
3. Section 11 tests the whole flow with a simulated AI, without using the Gemini quota.
4. Section 12 runs the real graph and stops for the team's decision; section 13 records it (name and reason required).
5. Download the logs (section 14) at the end of the session.
