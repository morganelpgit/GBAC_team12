# Macro/News Agent + Risk Rules (Gonçalo)

- `macro_news_risk.ipynb`: risk rules (`check_risk_rules`) + news summary with Gemini (`get_macro_news`) + mini LangGraph agent.
- Uses `data/prices.csv` (Morgane's cleaned prices).
- Needs your own Gemini key in a `.env` file in the project folder: `LLM_API_KEY=your-key`. Never put the key on GitHub.

Interfaces:
- `get_macro_news()` -> `{"summary": AI text, "headlines": raw headlines per topic}`
- `check_risk_rules(orders)`, with orders like `[{"code": "WORLD", "action": "buy", "amount_eur": 20000}]` -> approved / rejected / cash / weights
