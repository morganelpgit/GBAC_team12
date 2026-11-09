"""
Data Agent - Download daily prices for the 50 ETFs from Yahoo Finance.

Install (once):
    pip install yfinance pandas requests

Usage, in this order:
    python download_etfs.py tickers  -> find each ETF's Yahoo symbol from its ISIN + exchange
                                        and save it to data/tickers.csv (check it by hand)
    python download_etfs.py full     -> download the full price history (start of the project)
    python download_etfs.py update   -> append only the missing days (before each trading day)
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# 1. ETF UNIVERSE
# ISIN: (short code, name, theme, exchange)
# Exchange -> Yahoo suffix: Xetra = .DE, Euronext Brussels = .BR, Euronext Milan = .MI
# All these listings trade in EUR.
# ---------------------------------------------------------------------------
ETFS = {
    # Benchmark
    "IE00B4L5Y983": ("WORLD", "iShares Core MSCI World UCITS ETF USD (Acc)", "Global equity (benchmark)", "Xetra"),
    # Equity by region
    "IE00B5BMR087": ("S&P 500", "iShares Core S&P 500 UCITS ETF USD (Acc)", "US equity", "Xetra"),
    "LU0908500753": ("EUROPE 600", "Amundi Core Stoxx Europe 600 UCITS ETF Acc", "European equity", "Xetra"),
    "IE00B53L3W79": ("EURO STOXX 50", "iShares Core EURO STOXX 50 UCITS ETF EUR (Acc)", "European equity", "Xetra"),
    "FR0010655746": ("IBEX 35", "Amundi IBEX 35 UCITS ETF Acc", "European equity", "Xetra"),
    "FR0000021842": ("BEL 20", "Amundi BEL 20 UCITS ETF Dist", "Home market", "Brussels"),
    # Factors & income
    "IE00BF4RFH31": ("WORLD SMALL CAP", "iShares MSCI World Small Cap UCITS ETF USD (Acc)", "Size & style factors", "Xetra"),
    "IE00B8FHGS14": ("WORLD MIN VOL", "iShares Edge MSCI World Minimum Volatility UCITS ETF USD (Acc)", "Size & style factors", "Xetra"),
    "NL0011683594": ("DIVIDEND LEADERS", "VanEck Morningstar Developed Markets Dividend Leaders UCITS ETF", "Size & style factors", "Xetra"),
    "IE000U9J8HX9": ("NASDAQ INCOME", "NASDAQ Equity Premium Income Active UCITS ETF USD (Dist)", "Income strategies", "Xetra"),
    # Tech
    "IE00B53SZB19": ("NASDAQ", "iShares NASDAQ 100 UCITS ETF USD (Acc)", "Equity / Tech", "Xetra"),
    "IE000I8KRLL9": ("SEMIS", "iShares MSCI Global Semiconductors UCITS ETF USD (Acc)", "Equity / Tech", "Xetra"),
    "IE00BYPLS672": ("CYBERSEC", "L&G Cyber Security UCITS ETF USD Acc", "Equity / Tech", "Xetra"),
    "IE00BQ70R696": ("BIOTECH", "Invesco NASDAQ Biotech UCITS ETF", "Equity / Tech", "Xetra"),
    "IE00BYZK4552": ("ROBOTICS", "iShares Automation & Robotics UCITS ETF USD (Acc)", "Equity / Tech", "Xetra"),
    "IE000YU9K6K2": ("SPACE", "VanEck Space Innovators UCITS ETF A USD (Acc)", "Frontier tech", "Xetra"),
    "IE0007Y8Y157": ("QUANTUM", "VanEck Quantum Computing UCITS ETF A USD (Acc)", "Frontier tech", "Xetra"),
    # Sectors
    "LU1829219390": ("EURO BANKS", "Amundi Euro Stoxx Banks UCITS ETF Acc", "Financials", "Xetra"),
    "IE00BM67HK77": ("HEALTH CARE", "Xtrackers MSCI World Health Care UCITS ETF 1C", "Health care", "Xetra"),
    # Emerging markets
    "IE00BKM4GZ66": ("EMMKT", "iShares Core MSCI Emerging Markets IMI UCITS ETF USD (Acc)", "Emerging markets", "Xetra"),
    "IE00B02KXK85": ("CHINA LC", "iShares China Large Cap UCITS ETF (Dist)", "Emerging markets", "Xetra"),
    "IE00BZCQB185": ("INDIA", "iShares MSCI India UCITS ETF USD (Acc)", "Emerging markets", "Xetra"),
    "LU1900066975": ("KOREA", "Amundi MSCI Korea UCITS ETF Acc", "Emerging markets", "Xetra"),
    "IE00B0M63516": ("BRAZIL", "iShares MSCI Brazil UCITS ETF USD (Dist)", "Emerging markets", "Xetra"),
    "IE00BQT3WG13": ("CHINA A", "iShares MSCI China A UCITS ETF USD (Acc)", "Emerging markets", "Xetra"),
    # Energy & transition
    "IE00BM67HM91": ("WORLD ENERGY", "Xtrackers MSCI World Energy UCITS ETF 1C", "Energy & commodities", "Xetra"),
    "IE00B6R51Z18": ("OIL & GAS E&P", "iShares Oil & Gas Exploration & Production UCITS ETF USD (Acc)", "Energy & commodities", "Xetra"),
    "IE000M7V94E1": ("URANIUM", "VanEck Uranium and Nuclear Technologies UCITS ETF A", "Energy transition", "Xetra"),
    "IE00BK5BCH80": ("CLEAN ENERGY", "L&G Clean Energy UCITS ETF USD (Acc)", "Energy transition", "Xetra"),
    "FR0010930644": ("HYDROGEN", "Amundi Global Hydrogen UCITS ETF EUR (Acc)", "Energy transition", "Xetra"),
    # Metals
    "IE0003Z9E2Y3": ("COPPER MINERS", "Global X Copper Miners UCITS ETF USD (Acc)", "Industrial & strategic metals", "Xetra"),
    "IE0002PG6CA6": ("RARE EARTHS", "VanEck Rare Earth and Strategic Metals UCITS ETF USD (Acc)", "Industrial & strategic metals", "Xetra"),
    "IE00B4ND3602": ("GOLD", "iShares Physical Gold ETC", "Precious metals", "Xetra"),
    "IE00BQQP9F84": ("GOLD MINERS", "VanEck Gold Miners UCITS ETF", "Precious metals", "Xetra"),
    "IE000UL6CLP7": ("SILVER MINERS", "Global X Silver Miners UCITS ETF USD (Acc)", "Precious metals", "Xetra"),
    # Bonds & cash
    "LU1109942653": ("HIGHY BOND", "Xtrackers II EUR High Yield Corporate Bond UCITS ETF 1D", "Fixed income / Bonds", "Xetra"),
    "LU1407890620": ("US TREASURY 20Y", "Amundi US Treasury Bond Long Dated UCITS ETF (Dist)", "Fixed income / Bonds", "Xetra"),
    "IE00BG47KH54": ("GLOBAL AGG BOND", "Vanguard Global Aggregate Bond UCITS ETF EUR Hedged (Acc)", "Fixed income / Bonds", "Xetra"),
    "IE00B4WXJJ64": ("EUR GOVT BOND", "iShares Core EUR Govt Bond UCITS ETF EUR (Dist)", "Fixed income / Bonds", "Xetra"),
    "LU1190417599": ("OVERNIGHT CASH", "Amundi Smart Overnight Return UCITS ETF EUR (Acc)", "Money market (cash)", "Xetra"),
    # Defensive
    "IE000YYE6WK5": ("DEFENSE", "VanEck Defense UCITS ETF A", "Defensive sector", "Xetra"),
    "IE00BM67HN09": ("STAPLES", "Xtrackers MSCI World Consumer Staples UCITS ETF 1C", "Defensive sector", "Xetra"),
    # Crypto
    "XS2940466316": ("BITCOIN", "iShares Bitcoin ETP", "Digital assets", "Xetra"),
    "IE00BMDKNW35": ("CRYPTO EQUITY", "VanEck Crypto and Blockchain Innovators UCITS ETF USD (Acc)", "Digital assets", "Xetra"),
    # Leveraged & inverse (high risk)
    "FR0010424143": ("STOXX SHORT", "Amundi EURO STOXX 50 Daily (-2x) Inverse UCITS ETF Acc", "Leveraged & inverse", "Xetra"),
    "IE00B8JVMZ80": ("COPPER LVG", "WisdomTree Copper 3x Daily Leveraged", "Leveraged & inverse", "Milan"),
    "IE00B94QLN63": ("PALLADIUM LVG", "WisdomTree Palladium 2x Daily Leveraged", "Leveraged & inverse", "Milan"),
    "IE00BLRPRL42": ("NASDAQ 3X", "WisdomTree NASDAQ 100 3x Daily Leveraged", "Leveraged & inverse", "Xetra"),
    "LU0322251520": ("S&P 500 SHORT", "Xtrackers S&P 500 Inverse Daily Swap UCITS ETF 1C", "Leveraged & inverse", "Xetra"),
    "FR0010468983": ("EURO STOXX 2X", "Amundi EURO STOXX 50 Daily (2x) Leveraged UCITS ETF Acc", "Leveraged & inverse", "Xetra"),
}
ETFS = dict(list(ETFS.items())[:2])  # TEST: keep only the first 2 ETFs -- comment out this line for the full run

YAHOO_SUFFIX = {"Xetra": ".DE", "Brussels": ".BR", "Milan": ".MI"}
FIGI_EXCHANGE = {"Xetra": "GY", "Brussels": "BB", "Milan": "IM"}  # OpenFIGI (Bloomberg) exchange codes

START_DATE = "2021-01-01"  # about 5 years of history
DATA_DIR = Path("data")
TICKERS_FILE = DATA_DIR / "tickers.csv"
PRICES_FILE = DATA_DIR / "prices.csv"


# ---------------------------------------------------------------------------
# 2. FIND YAHOO SYMBOLS FROM ISIN + EXCHANGE
# ---------------------------------------------------------------------------
def openfigi_tickers() -> dict:
    """ISIN + exchange -> ticker on that exchange, using the free OpenFIGI API.
    Returns {isin: 'EUNL.DE', ...}. Without an API key: 10 ISINs per request, 25 requests/minute."""
    isins = list(ETFS.keys())
    result = {}
    for i in range(0, len(isins), 10):
        batch = isins[i:i + 10]
        jobs = [{"idType": "ID_ISIN", "idValue": isin,
                 "exchCode": FIGI_EXCHANGE[ETFS[isin][3]]} for isin in batch]
        try:
            r = requests.post("https://api.openfigi.com/v3/mapping", json=jobs, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"   OpenFIGI error: {e}")
            continue
        for isin, answer in zip(batch, r.json()):
            data = answer.get("data") or []
            if data and data[0].get("ticker"):
                result[isin] = data[0]["ticker"] + YAHOO_SUFFIX[ETFS[isin][3]]
        time.sleep(3)  # stay under the 25 requests/minute limit
    return result


def yahoo_search(isin: str, name: str, suffix: str) -> tuple[str, list]:
    """Fallback: search Yahoo by ISIN, then by name, and keep the listing with the right suffix."""
    all_found = []
    for query in (isin, name):
        try:
            quotes = yf.Search(query, max_results=25).quotes
        except Exception as e:
            print(f"   Yahoo error for '{query}': {e}")
            continue
        found = [q.get("symbol", "") for q in quotes]
        all_found += found
        matches = [s for s in found if s.endswith(suffix)]
        if matches:
            return matches[0], all_found
        time.sleep(0.5)
    return "", all_found


def find_tickers():
    """1) OpenFIGI: ISIN + exchange -> symbol.  2) Otherwise, Yahoo search.
    Output: data/tickers.csv -- review it and fix by hand if needed."""
    print("Looking up symbols via OpenFIGI...")
    figi = openfigi_tickers()
    rows = []
    for isin, (code, name, theme, exchange) in ETFS.items():
        symbol, candidates = figi.get(isin, ""), []
        if not symbol:
            symbol, candidates = yahoo_search(isin, name, YAHOO_SUFFIX[exchange])
            time.sleep(0.5)  # be gentle with Yahoo
        print(f"{'OK  ' if symbol else 'MISSING'} {code:<18} {isin}  ->  {symbol or 'FIND BY HAND'}")
        if not symbol and candidates:
            print(f"   (Yahoo suggests: {', '.join(dict.fromkeys(candidates))})")
        rows.append({"isin": isin, "code": code, "name": name, "theme": theme,
                     "exchange": exchange, "yahoo": symbol})

    DATA_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(TICKERS_FILE, index=False)
    missing = sum(1 for r in rows if not r["yahoo"])
    print(f"\nSaved to {TICKERS_FILE}. {missing} symbol(s) to fill in by hand.")


def load_tickers() -> pd.DataFrame:
    if not TICKERS_FILE.exists():
        sys.exit("Run this first: python download_etfs.py tickers")
    t = pd.read_csv(TICKERS_FILE).fillna("")
    return t[t["yahoo"] != ""]


# ---------------------------------------------------------------------------
# 3. DOWNLOAD PRICES
# ---------------------------------------------------------------------------
def download(start: str) -> pd.DataFrame:
    """Returns a 'long' table: one row per (date, ETF)."""
    tickers = load_tickers()
    raw = yf.download(
        tickers["yahoo"].tolist(),
        start=start,
        auto_adjust=True,   # prices adjusted for dividends and splits
        group_by="ticker",
        progress=False,
        threads=True,
    )

    rows = []
    for _, t in tickers.iterrows():
        if t["yahoo"] not in raw.columns.get_level_values(0):
            print(f"WARNING: no data for {t['code']} ({t['yahoo']})")
            continue
        df = raw[t["yahoo"]][["Close", "Volume"]].dropna(subset=["Close"]).copy()
        if df.empty:
            print(f"WARNING: no data for {t['code']} ({t['yahoo']})")
            continue
        df = df.reset_index().rename(columns={"Date": "date", "Close": "price", "Volume": "volume"})
        for col in ["isin", "code", "theme", "yahoo"]:
            df[col] = t[col]
        rows.append(df)

    data = pd.concat(rows, ignore_index=True)
    return data[["date", "code", "isin", "yahoo", "theme", "price", "volume"]]


def add_returns(data: pd.DataFrame) -> pd.DataFrame:
    data = data.sort_values(["code", "date"])
    data["return"] = data.groupby("code")["price"].pct_change()
    return data


def full():
    data = add_returns(download(START_DATE))
    DATA_DIR.mkdir(exist_ok=True)
    data.to_csv(PRICES_FILE, index=False)
    print(f"Done: {data['code'].nunique()} ETFs, {len(data)} rows saved to {PRICES_FILE}")


def update():
    if not PRICES_FILE.exists():
        sys.exit("No price file yet: run 'python download_etfs.py full' first")
    old = pd.read_csv(PRICES_FILE, parse_dates=["date"])
    start = (old["date"].max() - pd.Timedelta(days=5)).strftime("%Y-%m-%d")  # small overlap, nothing missed
    data = pd.concat([old.drop(columns="return"), download(start)])
    data = data.drop_duplicates(subset=["date", "code"], keep="last")
    data = add_returns(data)
    data.to_csv(PRICES_FILE, index=False)
    print(f"Done: data up to date until {data['date'].max().date()}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    {"tickers": find_tickers, "full": full, "update": update}.get(mode, full)()