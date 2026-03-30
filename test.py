"""
mutual_fund_aum.py
==================
Fetch Mutual Fund AUM & NAV data from free, no-auth APIs.

Sources:
  1. MFapi.in         — All schemes list + scheme details + historical NAV
  2. Captnemo/Kuvera  — AUM, expense ratio, fund manager, returns (by ISIN)
  3. AMFI NAVAll.txt  — Official daily NAV for all 9000+ schemes

Usage:
  python mutual_fund_aum.py

Requirements:
  pip install requests pandas
"""

import requests
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

BASE_MFAPI    = "https://api.mfapi.in"
BASE_CAPTNEMO = "https://mf.captnemo.in"
AMFI_NAV_URL  = "https://www.amfiindia.com/spages/NAVAll.txt"

HEADERS = {"User-Agent": "Mozilla/5.0 (MutualFundFetcher/1.0)"}

# ─────────────────────────────────────────────────────────────────────────────
# 1. MFapi — Scheme List & Details
# ─────────────────────────────────────────────────────────────────────────────

def get_all_schemes() -> pd.DataFrame:
    """
    Fetch all mutual fund schemes from MFapi.
    Returns DataFrame with columns: schemeCode, schemeName, isinGrowth, isinDivReinvestment
    """
    resp = requests.get(f"{BASE_MFAPI}/mf", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def get_scheme_details(scheme_code: int) -> dict:
    """
    Fetch full details + historical NAV for a scheme by AMFI scheme code.
    Returns dict with keys: meta, latest_nav, nav_history (DataFrame)

    Example scheme codes:
      120503 — Axis ELSS Tax Saver Fund - Direct Growth
      119598 — SBI Bluechip Fund - Direct Growth
      118989 — Mirae Asset Large Cap Fund - Direct Growth
    """
    resp = requests.get(f"{BASE_MFAPI}/mf/{scheme_code}", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    nav_df = pd.DataFrame(data.get("data", []))
    if not nav_df.empty:
        nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")

    return {
        "meta":        data.get("meta", {}),
        "latest_nav":  data["data"][0] if data.get("data") else None,
        "nav_history": nav_df,
    }


def get_latest_nav(scheme_code: int) -> dict:
    """
    Fetch only the latest NAV for a scheme (faster than full details).
    Returns: {meta: {...}, data: [{date, nav}]}
    """
    resp = requests.get(f"{BASE_MFAPI}/mf/{scheme_code}/latest", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search_schemes_mfapi(keyword: str) -> pd.DataFrame:
    """
    Search all MFapi schemes by keyword in scheme name.
    Returns filtered DataFrame.
    """
    df = get_all_schemes()
    mask = df["schemeName"].str.contains(keyword, case=False, na=False)
    return df[mask].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Captnemo/Kuvera — AUM by ISIN
# ─────────────────────────────────────────────────────────────────────────────

def get_aum_by_isin(isin: str) -> dict | None:
    """
    Fetch AUM, expense ratio, fund manager, and returns for a fund by ISIN.
    Uses Kuvera data via Captnemo's static API.

    NOTE: Only works for ISINs listed on the Kuvera platform.
          Use get_nav_by_isin() as a fallback for non-Kuvera ISINs.

    Returns dict with AUM data, or None if ISIN not found.
    """
    resp = requests.get(f"{BASE_CAPTNEMO}/kuvera/{isin}", headers=HEADERS, timeout=10)

    if resp.status_code == 404:
        print(f"  [WARN] ISIN {isin} not found on Kuvera. Falling back to /nav/ endpoint.")
        return None

    resp.raise_for_status()
    data = resp.json()

    # Response is a LIST — index [0]
    fund = data[0] if isinstance(data, list) and data else {}

    return {
        "isin":           isin,
        "name":           fund.get("name"),
        "aum_cr":         fund.get("aum"),            # AUM in crores
        "category":       fund.get("category"),
        "fund_type":      fund.get("fund_type"),
        "fund_category":  fund.get("fund_category"),
        "expense_ratio":  fund.get("expense_ratio"),
        "fund_manager":   fund.get("fund_manager"),
        "fund_rating":    fund.get("fund_rating"),
        "last_nav":       fund.get("last_nav"),        # {date, nav}
        "returns":        fund.get("returns"),         # {inception, year_1, year_3, year_5}
        "maturity_type":  fund.get("maturity_type"),
        "start_date":     fund.get("start_date"),
        "volatility":     fund.get("volatility"),
    }


def get_nav_by_isin(isin: str) -> dict | None:
    """
    Fetch NAV + full historical NAV series for ANY valid ISIN.
    Broader than get_aum_by_isin — works for all AMFI-registered funds.

    Returns dict with: isin, name, latest_nav, nav_date, nav_history (DataFrame)
    """
    resp = requests.get(f"{BASE_CAPTNEMO}/nav/{isin}", headers=HEADERS, timeout=15)

    if resp.status_code == 404:
        print(f"  [WARN] ISIN {isin} not found on Captnemo.")
        return None

    resp.raise_for_status()
    data = resp.json()

    hist = data.get("historical_nav", [])
    nav_df = pd.DataFrame(hist, columns=["date", "nav"]) if hist else pd.DataFrame()

    return {
        "isin":        data.get("ISIN"),
        "name":        data.get("name"),
        "latest_nav":  data.get("nav"),
        "nav_date":    data.get("date"),
        "nav_history": nav_df,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. AMFI Official — NAVAll.txt (all 9000+ schemes, daily updated)
# ─────────────────────────────────────────────────────────────────────────────

def get_amfi_nav_all() -> pd.DataFrame:
    """
    Download and parse AMFI's official daily NAV text file.
    Source: https://www.amfiindia.com/spages/NAVAll.txt (updated every business day)

    Returns DataFrame with columns:
      amc, category, scheme_code, isin_growth, isin_dividend,
      scheme_name, net_asset_value, repurchase_price, sale_price, date
    """
    resp = requests.get(AMFI_NAV_URL, headers=HEADERS, timeout=30)
    print(resp.text)
    resp.raise_for_status()

    rows = []
    current_amc      = None
    current_category = None

    for line in resp.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(";")

        if len(parts) < 7:
            # Detect AMC name vs scheme category lines
            if any(line.startswith(prefix) for prefix in
                   ("Open Ended", "Close Ended", "Interval", "Exchange")):
                current_category = line
            else:
                current_amc = line
            continue

        rows.append({
            "amc":               current_amc,
            "category":          current_category,
            "scheme_code":       parts[0].strip(),
            "isin_growth":       parts[1].strip() if parts[1].strip() != "-" else None,
            "isin_dividend":     parts[2].strip() if parts[2].strip() != "-" else None,
            "scheme_name":       parts[3].strip(),
            "net_asset_value":   parts[4].strip(),
            "repurchase_price":  parts[5].strip(),
            "sale_price":        parts[6].strip(),
            "date":              parts[7].strip() if len(parts) > 7 else None,
        })
    print(rows)
    df = pd.DataFrame(rows)
    df["net_asset_value"]  = pd.to_numeric(df["net_asset_value"],  errors="coerce")
    df["repurchase_price"] = pd.to_numeric(df["repurchase_price"], errors="coerce")
    df["sale_price"]       = pd.to_numeric(df["sale_price"],       errors="coerce")
    return df


def search_schemes_by_name(keyword: str, df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Search AMFI NAV data by keyword in scheme name.
    Pass an existing df to avoid re-downloading (recommended for multiple searches).
    """
    if df is None:
        df = get_amfi_nav_all()
    mask = df["scheme_name"].str.contains(keyword, case=False, na=False)
    return df[mask].reset_index(drop=True)


def get_schemes_by_amc(amc_keyword: str, df: pd.DataFrame = None) -> pd.DataFrame:
    """Filter all schemes for a specific AMC (e.g. 'SBI', 'HDFC', 'Axis')."""
    if df is None:
        df = get_amfi_nav_all()
    mask = df["amc"].str.contains(amc_keyword, case=False, na=False)
    return df[mask].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Combined Pipeline — Search by Name → Get Full Info
# ─────────────────────────────────────────────────────────────────────────────

def get_fund_full_info(scheme_name_keyword: str, amfi_df: pd.DataFrame = None) -> dict:
    """
    Full pipeline:
      1. Search AMFI data by scheme name keyword
      2. Extract ISIN
      3. Try Kuvera for AUM, expense ratio, fund manager, returns
      4. Fallback to Captnemo /nav/ if Kuvera doesn't have it
      5. Return consolidated result

    Args:
      scheme_name_keyword: Partial name to search (e.g. "Axis ELSS", "SBI Bluechip")
      amfi_df: Pre-downloaded AMFI DataFrame (pass to avoid re-downloading)

    Returns dict with all available fund data.
    """
    print(f"\n{'='*60}")
    print(f"  Searching: '{scheme_name_keyword}'")
    print(f"{'='*60}")

    # Step 1: Find scheme in AMFI data
    matches = search_schemes_by_name(scheme_name_keyword, amfi_df)
    if matches.empty:
        return {"error": f"No scheme found matching '{scheme_name_keyword}'"}

    scheme = matches.iloc[0]
    isin   = scheme["isin_growth"]
    print(f"  Scheme   : {scheme['scheme_name']}")
    print(f"  AMC      : {scheme['amc']}")
    print(f"  ISIN     : {isin}")
    print(f"  AMFI NAV : ₹{scheme['net_asset_value']} (as of {scheme['date']})")

    result = {
        "scheme_name":  scheme["scheme_name"],
        "amc":          scheme["amc"],
        "category":     scheme["category"],
        "scheme_code":  scheme["scheme_code"],
        "isin":         isin,
        "amfi_nav":     scheme["net_asset_value"],
        "nav_date":     scheme["date"],
    }

    if not isin:
        print("  [INFO] No ISIN available — skipping AUM fetch.")
        return result

    # Step 2: Try Kuvera for AUM
    kuvera = get_aum_by_isin(isin)
    if kuvera:
        result.update({
            "aum_cr":        kuvera["aum_cr"],
            "fund_type":     kuvera["fund_type"],
            "fund_category": kuvera["fund_category"],
            "expense_ratio": kuvera["expense_ratio"],
            "fund_manager":  kuvera["fund_manager"],
            "fund_rating":   kuvera["fund_rating"],
            "returns":       kuvera["returns"],
            "volatility":    kuvera["volatility"],
            "start_date":    kuvera["start_date"],
        })
        print(f"  AUM      : ₹{kuvera['aum_cr']} Cr")
        print(f"  Manager  : {kuvera['fund_manager']}")
        print(f"  Exp Ratio: {kuvera['expense_ratio']}%")
        print(f"  Rating   : {kuvera['fund_rating']} ⭐")
        if kuvera.get("returns"):
            r = kuvera["returns"]
            print(f"  Returns  : 1Y={r.get('year_1')}%  3Y={r.get('year_3')}%  5Y={r.get('year_5')}%")
    else:
        # Step 3: Fallback — /nav/ endpoint
        nav_data = get_nav_by_isin(isin)
        if nav_data:
            result["nav_history_count"] = len(nav_data["nav_history"])
            print(f"  [Fallback] Got {len(nav_data['nav_history'])} historical NAV records.")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — Demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── 3. AUM by ISIN (Kuvera) ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("AUM by ISIN (Kuvera) — Edelweiss Banking & PSU Debt")
    print("=" * 60)
    aum = get_aum_by_isin("INF109KC1W58")
    if aum:
        for k, v in aum.items():
            print(f"  {k:20s}: {v}")


    # Optional: Export to CSV
    # summary_df.to_csv("mutual_fund_aum_report.csv", index=False)
    # print("\nExported to mutual_fund_aum_report.csv")