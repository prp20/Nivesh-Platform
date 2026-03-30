"""
mutual_fund_fetch.py
--------------------
Sample run: fetches NAV, NAV history, Expense Ratio (TER),
Sharpe Ratio, and Sortino Ratio for Indian mutual funds.

Install deps:
    pip install requests pandas numpy tabulate

Usage:
    python mutual_fund_fetch.py
"""

import requests
import pandas as pd
import numpy as np
from tabulate import tabulate

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MFAPI_BASE        = "https://api.mfapi.in/mf"
KUVERA_BASE       = "https://mf.captnemo.in/kuvera"
RISK_FREE_ANNUAL  = 0.065        # ~6.5% India 91-day T-bill yield
TRADING_DAYS      = 252          # for annualisation
LOOKBACK_DAYS     = 365 * 3      # 3-year window for ratio calculation


# ─────────────────────────────────────────────
# FUNDS TO ANALYSE
# ─────────────────────────────────────────────
FUNDS = [
    {
        "name":        "HDFC Flexi Cap Fund – Direct Growth",
        "scheme_code": "119598",
        "isin":        "INF179K01VD6",
    },
    {
        "name":        "Mirae Asset Large Cap Fund – Direct Growth",
        "scheme_code": "118834",
        "isin":        "INF769K01EF3",
    },
    {
        "name":        "Parag Parikh Flexi Cap – Direct Growth",
        "scheme_code": "122639",
        "isin":        "INF879O01019",
    },
]


# ─────────────────────────────────────────────
# DATA FETCHERS
# ─────────────────────────────────────────────

def fetch_nav_history(scheme_code: str) -> pd.DataFrame:
    """Returns a DataFrame with columns [date, nav], sorted ascending."""
    url = f"{MFAPI_BASE}/{scheme_code}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    df = pd.DataFrame(payload["data"])             # [{date, nav}, ...]
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna().sort_values("date").reset_index(drop=True)
    return df


def fetch_latest_nav(scheme_code: str) -> dict:
    """Returns latest {date, nav} dict."""
    url = f"{MFAPI_BASE}/{scheme_code}/latest"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"][0]


def fetch_expense_ratio(isin: str) -> float | None:
    """Fetches TER from the Kuvera/captnemo API (free, no auth)."""
    url = f"{KUVERA_BASE}/{isin}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print(data)
        if isinstance(data, list) and len(data) > 0:
            fund_obj = data[0]             # ✅ unpack the first element
            ter = fund_obj.get("expense_ratio")
        return ter
    except Exception:
        return None


# ─────────────────────────────────────────────
# RATIO COMPUTATION
# ─────────────────────────────────────────────

def compute_risk_ratios(nav_df: pd.DataFrame, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """
    Computes Sharpe and Sortino ratios from NAV history.

    Args:
        nav_df:       DataFrame [date, nav] sorted ascending.
        lookback_days: Number of calendar days to look back.
    Returns:
        dict with sharpe_ratio, sortino_ratio, annualised_return,
        annualised_volatility.
    """
    cutoff = nav_df["date"].max() - pd.Timedelta(days=lookback_days)
    df = nav_df[nav_df["date"] >= cutoff].copy()

    df["daily_return"] = df["nav"].pct_change()
    returns = df["daily_return"].dropna()

    if len(returns) < 30:
        return {k: None for k in
                ["sharpe_ratio", "sortino_ratio",
                 "annualised_return_pct", "annualised_volatility_pct"]}

    rfr_daily      = RISK_FREE_ANNUAL / TRADING_DAYS
    excess         = returns - rfr_daily
    ann_return     = returns.mean() * TRADING_DAYS
    ann_volatility = returns.std() * np.sqrt(TRADING_DAYS)

    # Sharpe
    sharpe = (excess.mean() / returns.std()) * np.sqrt(TRADING_DAYS)

    # Sortino – only penalises downside returns
    downside     = excess[excess < 0]
    downside_std = np.sqrt((downside ** 2).mean()) if len(downside) > 0 else np.nan
    sortino      = (excess.mean() / downside_std) * np.sqrt(TRADING_DAYS) \
                   if not np.isnan(downside_std) else None

    return {
        "sharpe_ratio":             round(float(sharpe),       4),
        "sortino_ratio":            round(float(sortino), 4) if sortino else None,
        "annualised_return_pct":    round(ann_return * 100,    2),
        "annualised_volatility_pct":round(ann_volatility * 100,2),
    }


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────

def analyse_fund(fund: dict) -> dict:
    print(f"\n  ▶  Fetching: {fund['name']} (scheme={fund['scheme_code']})")

    nav_df     = fetch_nav_history(fund["scheme_code"])
    latest_nav = fetch_latest_nav(fund["scheme_code"])
    ter        = fetch_expense_ratio(fund["isin"])
    print(ter)
    ratios     = compute_risk_ratios(nav_df)

    result = {
        "Fund":                     fund["name"],
        "Scheme Code":              fund["scheme_code"],
        "ISIN":                     fund["isin"],
        "Latest NAV (₹)":           latest_nav["nav"],
        "NAV Date":                 latest_nav["date"],
        "NAV History (rows)":       len(nav_df),
        "Oldest NAV Date":          str(nav_df["date"].min().date()),
        "Expense Ratio (TER %)":    ter if ter else "N/A",
        "Sharpe Ratio (3Y)":        ratios["sharpe_ratio"],
        "Sortino Ratio (3Y)":       ratios["sortino_ratio"],
        "Ann. Return % (3Y)":       ratios["annualised_return_pct"],
        "Ann. Volatility % (3Y)":   ratios["annualised_volatility_pct"],
    }
    return result


def main():
    print("=" * 65)
    print("  Indian Mutual Fund Analyser — Free Data Sources")
    print(f"  Risk-Free Rate: {RISK_FREE_ANNUAL*100:.1f}%  |  Lookback: 3 Years")
    print("=" * 65)

    results = []
    for fund in FUNDS:
        try:
            results.append(analyse_fund(fund))
        except Exception as exc:
            print(f"  ✗  Failed for {fund['name']}: {exc}")

    if not results:
        print("\nNo data fetched — check your internet connection.")
        return

    # ── Summary table ──────────────────────────────────────────────
    summary_keys = [
        "Fund", "Latest NAV (₹)", "NAV Date",
        "Expense Ratio (TER %)", "Sharpe Ratio (3Y)",
        "Sortino Ratio (3Y)", "Ann. Return % (3Y)"
    ]
    table = [{k: r[k] for k in summary_keys} for r in results]

    print("\n\n── SUMMARY ─────────────────────────────────────────────────\n")
    print(tabulate(table, headers="keys", tablefmt="rounded_outline",
                   numalign="right", stralign="left"))

    # ── Detailed output ────────────────────────────────────────────
    print("\n\n── DETAILED PROFILE ────────────────────────────────────────")
    for r in results:
        print(f"\n  {r['Fund']}")
        print(f"    Scheme Code    : {r['Scheme Code']}")
        print(f"    ISIN           : {r['ISIN']}")
        print(f"    Latest NAV     : ₹{r['Latest NAV (₹)']}  ({r['NAV Date']})")
        print(f"    History        : {r['NAV History (rows)']} data points  "
              f"(since {r['Oldest NAV Date']})")
        print(f"    TER            : {r['Expense Ratio (TER %)']}%")
        print(f"    Sharpe (3Y)    : {r['Sharpe Ratio (3Y)']}")
        print(f"    Sortino (3Y)   : {r['Sortino Ratio (3Y)']}")
        print(f"    Ann. Return    : {r['Ann. Return % (3Y)']}%")
        print(f"    Ann. Volatility: {r['Ann. Volatility % (3Y)']}%")

    # ── Optional: export NAV history of first fund to CSV ─────────
    first_fund = FUNDS[0]
    nav_df = fetch_nav_history(first_fund["scheme_code"])
    csv_path = f"nav_history_{first_fund['scheme_code']}.csv"
    nav_df.to_csv(csv_path, index=False)
    print(f"\n\n  ✓ NAV history exported → {csv_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()