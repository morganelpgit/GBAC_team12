# Macro/News Agent + Risk Rules

- `macro_news_risk (revised) (1).ipynb`: news summary with Gemini, risk rules for our balanced profile, and a mini LangGraph agent (macro → portfolio manager placeholder → risk).
- Uses `data/prices.csv` (Morgane's cleaned prices). Starting capital: €10,000.
- Needs your own Gemini key in a `.env` file in the project folder: `LLM_API_KEY=your-key`. Never put the key on GitHub.
- Run the cells from top to bottom. Without a key, everything runs except the AI summary.

## Risk rules (balanced profile)

- Competition rules: max 5 orders per day (incl. sells), no borrowing, sells before buys, execution at the previous day's close, only our 50 ETFs.
- Max 20% per ETF (OVERNIGHT CASH exempt), max 10% in leveraged and inverse ETFs, min 20% defensive (OVERNIGHT CASH, EUR GOVT BOND, GLOBAL AGG BOND, cash), max 40% per theme (leveraged ETFs count in the theme they track), min order €500.
- A buy that breaks a limit is reduced to fit, or rejected if less than €500 remains, with the reason.
- Planning buffers for the Portfolio Manager: `PLAN_MIN_DEFENSIVE` = 25%, `PLAN_MAX_THEME` = 35%.

## Interfaces

- `get_macro_news()` -> `{"facts", "theme_views", "overall", "headlines", "summary"}`
  - `theme_views`: `{theme: {"view": "positive/neutral/negative", "reason", "sources"}}`, one view per theme. Bonds are split into "EUR bonds" and "US bonds"; the old key "Fixed income / Bonds" is kept and copies the EUR bonds view.
- `etf_macro_views(code, theme_views)` -> the macro views that matter for one ETF (inverse ETFs take the opposite view).
- `macro_conflicts(orders, theme_views)` -> orders that go against the macro view.
- `check_risk_rules(orders)`, with orders like `[{"code": "WORLD", "action": "buy", "amount_eur": 2000}]` -> `{"approved", "rejected", "cash_after_eur", "weights_after", "summary", "warnings"}`
