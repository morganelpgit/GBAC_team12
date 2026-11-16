"""
Technical Analysis agent (Juliet) - Team 12, QDC Fall 2026.

Pure Python: no AI call. Every number and every reason is computed here, so the
signals are reproducible and still available when Gemini is busy or over quota.
The AI Portfolio Manager only reads the output.

Why these signals (see Technical_code/technical_agent.ipynb, section "Evidence"):
- Cross-sectional MOMENTUM (6-month and 12-1 month return, ranked across our ETFs)
  is the only indicator with a stable predictive power for the next 5-10 trading days
  in our universe (IC > 0, t-stat > 2, positive every year 2022-2026 for 12-1).
- Trend (price vs 50-day average), 20-day breakout and RSI are weak on their own:
  they are used as context / timing notes, never as the main signal.
- Each ETF gets a BEHAVIOUR type from its own history (variance ratio): trending ETFs
  are timed with breakouts, mean-reverting ETFs with pullbacks (RSI).

Main entry point:  run_technical_agent(prices) -> dict
    {"as_of", "signals" (DataFrame), "theme_views" (dict, same format as the macro agent),
     "summary" (text for the Portfolio Manager prompt), "method" (text)}
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- settings
MOM_LONG, MOM_SKIP, MOM_MID = 252, 21, 126      # 12-1 month momentum (skip last month) and 6-month momentum
MA_WINDOW = 50                                  # trend: price vs 50-day average
BREAKOUT_WINDOW = 20                            # breakout: close above the highest close of the previous 20 days
VOLUME_WINDOW, VOLUME_CONFIRM = 20, 1.5         # breakout confirmed if volume >= 1.5x its 20-day average
RSI_WINDOW = 14
RSI_OVERBOUGHT, RSI_PULLBACK = 70, 40
VR_LAG, VR_YEARS = 10, 3                        # behaviour type: 10-day variance ratio over the last 3 years
VR_TREND, VR_MEANREV = 1.02, 0.95
MIN_HISTORY = MOM_MID + 1                       # below this: not enough history for a momentum signal
POSITIVE_SCORE, NEGATIVE_SCORE = 0.67, 0.33     # momentum score (0-1 percentile) thresholds for the view

CASH_LIKE = {"OVERNIGHT CASH"}                   # money market: no technical signal
# Leveraged / inverse ETFs follow the signal of their unleveraged twin in our universe (inverse = flipped).
UNDERLYING = {"NASDAQ 3X": ("NASDAQ", 1), "EURO STOXX 2X": ("EURO STOXX 50", 1),
              "S&P 500 SHORT": ("S&P 500", -1), "STOXX SHORT": ("EURO STOXX 50", -1)}
FLIP = {"positive": "negative", "negative": "positive", "neutral": "neutral"}


# ---------------------------------------------------------------- helpers
def today_paris() -> pd.Timestamp:
    return pd.Timestamp.now(tz="Europe/Paris").normalize().tz_localize(None)


def load_prices(path="data/prices.csv") -> pd.DataFrame:
    """Same rule as the rest of the team: today's row is intraday, never used (orders execute at the T-1 close)."""
    df = pd.read_csv(path, parse_dates=["date"])
    return df[df["date"] < today_paris()].sort_values(["code", "date"]).reset_index(drop=True)


def _rsi(p: pd.Series, n: int = RSI_WINDOW) -> pd.Series:
    d = p.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _variance_ratio(p: pd.Series, lag: int = VR_LAG) -> float:
    lp = np.log(p.dropna())
    if len(lp) < lag * 20:
        return np.nan
    return float(lp.diff(lag).var() / (lag * lp.diff().var()))


def panel(prices: pd.DataFrame, col: str) -> pd.DataFrame:
    return prices.pivot_table(index="date", columns="code", values=col).sort_index()


# ---------------------------------------------------------------- indicators (whole history, used by the backtest too)
def indicator_panels(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """All indicators as date x ETF tables. Uses adj_close (no artificial drop on ex-dividend days)."""
    adj = panel(prices, "adj_close").ffill(limit=5)
    vol = panel(prices, "volume").reindex(adj.index)
    out = {
        "mom_12_1": adj.shift(MOM_SKIP) / adj.shift(MOM_LONG) - 1,
        "mom_6m": adj / adj.shift(MOM_MID) - 1,
        "vs_ma50": adj / adj.rolling(MA_WINDOW).mean() - 1,
        "breakout_20d": (adj > adj.rolling(BREAKOUT_WINDOW).max().shift(1)).astype(float).where(adj.notna()),
        "volume_ratio": vol / vol.rolling(VOLUME_WINDOW).mean().shift(1),
        "rsi14": adj.apply(_rsi),
    }
    return out


def momentum_score(panels: dict, exclude=None) -> pd.DataFrame:
    """Cross-sectional percentile (0 = worst, 1 = best) of 12-1 and 6-month momentum, averaged.
    ETFs without 12-1 history use the 6-month rank only. Cash and leveraged twins are not ranked
    (a 3x NASDAQ is just NASDAQ amplified: ranking both would count the same bet twice)."""
    exclude = CASH_LIKE | set(UNDERLYING) if exclude is None else exclude
    cols = [c for c in panels["mom_6m"].columns if c not in exclude]
    r_long = panels["mom_12_1"][cols].rank(axis=1, pct=True)
    r_mid = panels["mom_6m"][cols].rank(axis=1, pct=True)
    return pd.concat([r_long, r_mid]).groupby(level=0).mean()


# ---------------------------------------------------------------- behaviour type per ETF
def behaviour_types(prices: pd.DataFrame) -> dict[str, str]:
    adj = panel(prices, "adj_close")
    lev = prices.drop_duplicates("code").set_index("code")["leverage"].to_dict()
    start = adj.index.max() - pd.DateOffset(years=VR_YEARS)
    out = {}
    for c in adj.columns:
        p = adj.loc[adj.index >= start, c].dropna()
        if c in CASH_LIKE:
            out[c] = "cash-like"
        elif c in UNDERLYING:
            out[c] = f"leveraged (follows {UNDERLYING[c][0]})"
        elif lev.get(c, 1) != 1:
            out[c] = "leveraged"
        elif adj[c].notna().sum() < MIN_HISTORY:
            out[c] = "short history"
        else:
            vr = _variance_ratio(p)
            out[c] = ("trending" if vr > VR_TREND else "mean-reverting" if vr < VR_MEANREV else "mixed")
    return out


# ---------------------------------------------------------------- today's signal table
def _timing_note(btype, breakout, vol_ok, rsi, above_ma):
    notes = []
    if btype in ("trending", "mixed") and breakout:
        notes.append("breakout to a 20-day high" + (" on high volume" if vol_ok else " (volume not confirmed)"))
    if btype == "mean-reverting" and above_ma and rsi < RSI_PULLBACK:
        notes.append("pullback in an uptrend (RSI low, price above MA50)")
    if rsi > RSI_OVERBOUGHT:
        notes.append("overbought (RSI > 70): risk of buying after a sharp rise")
    return "; ".join(notes) or "-"


def signal_table(prices: pd.DataFrame, panels: dict | None = None, as_of=None) -> pd.DataFrame:
    panels = panels or indicator_panels(prices)
    score = momentum_score(panels)
    as_of = pd.Timestamp(as_of) if as_of is not None else score.index.max()
    info = prices.drop_duplicates("code", keep="last").set_index("code")
    btypes = behaviour_types(prices[prices["date"] <= as_of])
    hist = panel(prices, "adj_close").loc[:as_of].notna().sum()
    rows = []
    for c in info.index:
        row = {"code": c, "theme": info.loc[c, "theme"], "leverage": int(info.loc[c, "leverage"]),
               "behaviour": btypes.get(c, "-")}
        val = lambda k: panels[k].loc[as_of, c] if c in panels[k].columns and as_of in panels[k].index else np.nan
        row.update({"mom_12_1_%": round(val("mom_12_1") * 100, 1), "mom_6m_%": round(val("mom_6m") * 100, 1),
                    "vs_ma50_%": round(val("vs_ma50") * 100, 1), "rsi14": round(val("rsi14"), 0),
                    "breakout_20d": bool(val("breakout_20d") == 1),
                    "volume_ratio": round(val("volume_ratio"), 2)})
        s = score.loc[as_of, c] if c in score.columns else np.nan
        row["tech_score"] = round(float(s), 2) if pd.notna(s) else np.nan
        rows.append(row)
    t = pd.DataFrame(rows).set_index("code")

    # momentum rank (1 = strongest) among ETFs that have a score
    t["mom_rank"] = t["tech_score"].rank(ascending=False, method="min")

    views, conf, reasons, timing = {}, {}, {}, {}
    for c, r in t.iterrows():
        if c in CASH_LIKE:
            views[c], conf[c], reasons[c] = "neutral", "-", "money market: no technical signal"
            timing[c] = "-"
            t.loc[c, ["rsi14", "vs_ma50_%"]] = np.nan
            t.loc[c, "breakout_20d"] = False
            continue
        if c in UNDERLYING:                                   # handled below: follows the unleveraged twin
            continue
        if hist.get(c, 0) < MIN_HISTORY or pd.isna(r["tech_score"]):
            views[c], conf[c] = "neutral", "low"
            reasons[c] = f"only {int(hist.get(c, 0))} days of history: no momentum signal"
            timing[c] = "-"
            continue
        above = r["vs_ma50_%"] > 0
        if r["tech_score"] >= POSITIVE_SCORE and above:
            v = "positive"
        elif r["tech_score"] <= NEGATIVE_SCORE and not above:
            v = "negative"
        else:
            v = "neutral"
        views[c] = v
        if v == "neutral":
            conf[c] = "-"
        else:
            sign = 1 if v == "positive" else -1                 # both momentum horizons point the same way?
            both = all(pd.notna(r[k]) and np.sign(r[k]) == sign for k in ("mom_6m_%", "mom_12_1_%"))
            conf[c] = "high" if both and r["behaviour"] != "mean-reverting" and r["leverage"] == 1 else "medium"
        reasons[c] = (f"tech_score={r['tech_score']:.2f} (momentum rank {int(r['mom_rank'])} of {int(t['tech_score'].notna().sum())}), "
                      f"mom_6m={r['mom_6m_%']}%, mom_12_1={r['mom_12_1_%']}%, vs_ma50={r['vs_ma50_%']}%, "
                      f"rsi14={r['rsi14']:.0f}")
        vol_ok = pd.notna(r["volume_ratio"]) and r["volume_ratio"] >= VOLUME_CONFIRM
        timing[c] = _timing_note(r["behaviour"], r["breakout_20d"], vol_ok, r["rsi14"], above)

    for c, (base, sign) in UNDERLYING.items():                 # leveraged / inverse: signal of the twin
        if c not in t.index:
            continue
        bv = views.get(base, "neutral")
        views[c] = bv if sign > 0 else FLIP[bv]
        bs = t.loc[base, "tech_score"] if base in t.index else np.nan     # score of the twin (inverse = 1 - score)
        t.loc[c, "tech_score"] = round(bs if sign > 0 else 1 - bs, 2) if pd.notna(bs) else np.nan
        conf[c] = "-" if views[c] == "neutral" else "medium"     # never "high": daily-reset leverage adds risk
        reasons[c] = (f"{'inverse of' if sign < 0 else 'leveraged'} {base}: {base} view is {bv} "
                      f"({reasons.get(base, '')})")
        timing[c] = "daily-reset leverage: losses compound when the market goes sideways, hold only short term"

    t["tech_view"] = pd.Series(views)
    t["confidence"] = pd.Series(conf)
    t["timing_note"] = pd.Series(timing)
    t["reason"] = pd.Series(reasons)
    t.insert(0, "as_of", as_of.date())
    return t.sort_values(["tech_score"], ascending=False, na_position="last")


# ---------------------------------------------------------------- theme views (same format as the macro agent)
def theme_views(signals: pd.DataFrame) -> dict:
    """One net technical view per theme, from the unleveraged ETFs of that theme."""
    out = {}
    base = signals[(signals["leverage"] == 1) & ~signals.index.isin(CASH_LIKE) & signals["tech_score"].notna()]
    for theme, g in base.groupby("theme"):
        s = g["tech_score"].mean()
        above = (g["vs_ma50_%"] > 0).mean()
        view = "positive" if s >= POSITIVE_SCORE and above >= 0.5 else "negative" if s <= NEGATIVE_SCORE and above < 0.5 else "neutral"
        out[theme] = {"view": view,
                      "reason": f"avg tech_score={s:.2f}, {above:.0%} of its ETFs above their 50-day average "
                                f"({', '.join(g.index)})",
                      "sources": list(g.index)}
    return out


# ---------------------------------------------------------------- text for the Portfolio Manager prompt
SUMMARY_COLUMNS = ["tech_view", "confidence", "tech_score", "mom_rank", "mom_6m_%", "mom_12_1_%",
                   "vs_ma50_%", "rsi14", "breakout_20d", "behaviour", "timing_note"]

METHOD = (
    "Computed in Python by the Technical Analysis agent from adjusted closing prices (T-1 close). "
    "tech_score = average percentile rank (0 worst, 1 best) of 6-month and 12-1-month momentum across our ETFs: "
    "in our 2022-2026 backtest this was the ONLY indicator with a stable predictive power for the next 5-10 trading days. "
    "tech_view: positive = tech_score >= 0.67 AND price above its 50-day average; negative = tech_score <= 0.33 AND below; "
    "else neutral. Leveraged/inverse ETFs follow their unleveraged twin (inverse = flipped). "
    "breakout_20d, rsi14 and timing_note are weak signals on their own: use them only to time an entry, never as the main reason. "
    "Momentum is a probability edge, not a certainty: it often fails at turning points.")


def summary_text(signals: pd.DataFrame, tviews: dict) -> str:
    themes = "\n".join(f"- {t}: {v['view']} ({v['reason']})" for t, v in tviews.items())
    table = signals[SUMMARY_COLUMNS].reset_index().to_csv(index=False)
    return (f"{METHOD}\n\nTechnical view per theme:\n{themes}\n\n"
            f"Technical signals per ETF (as of {signals['as_of'].iloc[0]}):\n{table}")


# ---------------------------------------------------------------- checks the Portfolio Manager's validation can use
def technical_conflicts(target_weights: dict, signals: pd.DataFrame, reasons: dict | None = None,
                        current_weights: dict | None = None) -> list[str]:
    """Problems if the proposal BUYS an ETF whose technical view is negative without saying why.
    Same logic as Francesco's macro check: the reason must contain 'Contrary to technical signal because'."""
    errors, current_weights = [], current_weights or {}
    for c, w in target_weights.items():
        if c not in signals.index or w <= current_weights.get(c, 0) + 0.005:
            continue
        if signals.loc[c, "tech_view"] == "negative":
            text = (reasons or {}).get(c, "").lower()
            if "contrary to technical signal" not in text:
                errors.append(f"{c}: its technical view is NEGATIVE ({signals.loc[c, 'reason']}) - remove it or "
                              "explain in its reason: 'Contrary to technical signal because ...'")
    return errors


# ---------------------------------------------------------------- evidence: which indicators predict returns?
def ic_table(prices: pd.DataFrame, horizons=(5, 10), start="2022-01-01") -> pd.DataFrame:
    """Information coefficient: every `h` days, rank-correlation between an indicator and the next-h-day
    return across ETFs. Mean IC > 0 with t-stat > 2 = the indicator has a real (if small) predictive power.
    Future returns use CLOSE prices (what the competition pays: no dividends)."""
    panels = indicator_panels(prices)
    panels["tech_score"] = momentum_score(panels)
    panels["low_vol_60d"] = -panel(prices, "adj_close").pct_change(fill_method=None).rolling(60).std()
    close = panel(prices, "close").ffill(limit=5)
    rows = []
    for h in horizons:
        fwd = close.shift(-h) / close - 1
        dates = [d for d in close.index[::h] if d >= pd.Timestamp(start) and d in fwd.dropna(how="all").index]
        for name, sig in panels.items():
            if name == "volume_ratio":
                continue
            with warnings.catch_warnings():                       # constant columns (e.g. no breakout that day) -> NaN, skipped
                warnings.simplefilter("ignore")
                ics = pd.Series({d: sig.loc[d].rank().corr(fwd.loc[d].rank()) for d in dates if d in sig.index}).dropna()
            if len(ics) < 10:
                continue
            by_year = ics.groupby(ics.index.year).mean()
            rows.append({"indicator": name, "horizon_days": h, "mean_IC": round(ics.mean(), 3),
                         "t_stat": round(ics.mean() / ics.std() * np.sqrt(len(ics)), 2),
                         "hit_rate": round((ics > 0).mean(), 2), "n_periods": len(ics),
                         "positive_years": f"{int((by_year > 0).sum())}/{len(by_year)}"})
    return pd.DataFrame(rows).sort_values(["horizon_days", "t_stat"], ascending=[True, False])


# ---------------------------------------------------------------- evidence: replay the competition on past data
TRADING_OFFSETS = (0, 3, 5, 8, 10)     # Mon 7, Thu 10, Mon 14, Thu 17, Mon 21 Dec = trading days 0,3,5,8,10
FINAL_OFFSET = 12                      # final valuation Wed 23 Dec


def simulate_competitions(prices: pd.DataFrame, top_n=5, max_swaps=2, step=5, start="2022-02-01",
                          capital=10_000.0, min_order=500.0) -> pd.DataFrame:
    """Replays our competition many times on history, with its real rules:
    5 trading days in ~12 sessions, max 5 orders per day, orders at the previous close, portfolio valued
    at CLOSE prices (dividends not credited), no leverage, no borrowing.
    Strategy (technical only, to test the signal): equal weight in the `top_n` ETFs with the best tech_score
    that are above their 50-day average; on later days replace at most `max_swaps` holdings that dropped out.
    Benchmark: 100% WORLD bought on day 0."""
    panels = indicator_panels(prices)
    score = momentum_score(panels)
    lev = prices.drop_duplicates("code").set_index("code")["leverage"]
    unlevered = [c for c in score.columns if lev.get(c, 1) == 1]
    close = panel(prices, "close").ffill(limit=5)
    dates = close.index
    first = dates.searchsorted(pd.Timestamp(start))
    rows = []
    for i in range(first + 1, len(dates) - FINAL_OFFSET, step):
        cash, units = capital, {}
        for k, off in enumerate(TRADING_OFFSETS):
            d = dates[i + off - 1]                                  # signal + execution price = previous close
            px = close.loc[d]
            ok = score.loc[d, unlevered].dropna()
            ok = ok[(panels["vs_ma50"].loc[d, ok.index] > 0) & px[ok.index].notna()]
            wanted = list(ok.nlargest(top_n).index)
            value = cash + sum(u * px[c] for c, u in units.items())
            if k == 0:
                sells, buys = [], wanted[:top_n]
            else:
                sells = [c for c in units if c not in wanted][:max_swaps]
                buys = [c for c in wanted if c not in units][:len(sells) + (top_n - len(units))]
                buys = buys[:max(0, 5 - len(sells))]                # max 5 orders per day
            for c in sells:
                cash += units.pop(c) * px[c]
            slot = value / top_n
            for c in buys:
                amount = min(slot, cash)
                if amount >= min_order:
                    units[c] = amount / px[c]
                    cash -= amount
        end = dates[i + FINAL_OFFSET]
        final = cash + sum(u * close.loc[end, c] for c, u in units.items())
        world = close["WORLD"]
        rows.append({"start": dates[i].date(), "end": end.date(),
                     "strategy_%": round((final / capital - 1) * 100, 2),
                     "world_%": round((world.loc[end] / world.loc[dates[i - 1]] - 1) * 100, 2)})
    out = pd.DataFrame(rows)
    out["excess_%"] = out["strategy_%"] - out["world_%"]
    return out


def simulation_summary(sim: pd.DataFrame) -> dict:
    f = lambda x, n=2: round(float(x), n)
    return {"windows": len(sim), "beat_WORLD_%": f((sim["excess_%"] > 0).mean() * 100, 1),
            "avg_excess_%": f(sim["excess_%"].mean()), "median_excess_%": f(sim["excess_%"].median()),
            "avg_strategy_%": f(sim["strategy_%"].mean()), "avg_world_%": f(sim["world_%"].mean()),
            "worst_strategy_%": f(sim["strategy_%"].min()), "worst_world_%": f(sim["world_%"].min()),
            "best_strategy_%": f(sim["strategy_%"].max())}


# ---------------------------------------------------------------- main entry point
def run_technical_agent(prices: pd.DataFrame | None = None, prices_path="data/prices.csv", as_of=None) -> dict:
    prices = load_prices(prices_path) if prices is None else prices[prices["date"] < today_paris()]
    panels = indicator_panels(prices)
    signals = signal_table(prices, panels, as_of)
    tviews = theme_views(signals)
    return {"as_of": str(signals["as_of"].iloc[0]), "signals": signals, "theme_views": tviews,
            "summary": summary_text(signals, tviews), "method": METHOD}
