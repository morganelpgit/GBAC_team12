# Portfolio Manager (Francesco)

- **portfolio_orders.ipynb**: first version of `weights_to_orders`, which turns the Portfolio Manager's target weights into max 5 orders following the competition rules (sells first, biggest moves first, every buy funded), with tests on our price data.

- **portfolio_manager_graph.ipynb**: connects the Portfolio Manager to Gonçalo's Macro/News and Risk code in one LangGraph flow:
  `macro → portfolio_manager → orders → risk`
  - Orders use Gonçalo's format (`code`, `action`, `amount_eur`).
  - Risk rules follow our balanced profile: max 20% per ETF (except OVERNIGHT CASH), max 10% in leveraged/inverse ETFs, max 40% per theme, min 20% in defensive assets, €500 minimum order.
  - The API key is read from Colab Secrets or from a `.env` file.
  - The Portfolio Manager is still a **placeholder** with fixed weights: next step is the AI version that uses the macro summary.

## How to run
1. Open the notebook in Colab (or Jupyter).
2. Upload `prices.csv` (or run it from the repo, where `data/prices.csv` is found automatically).
3. Add your Gemini key as `LLM_API_KEY` in Colab Secrets (or in `.env`).
4. Run all cells.
