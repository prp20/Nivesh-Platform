"""
Converts ScreenerScraper raw output into typed Python dicts.

Input (from ScreenerScraper):
  {
    "headers": ["", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
    "rows": [
      {"": "Revenue", "Mar 2020": "87,939", "Mar 2021": "100,616", ...},
      {"": "Net Profit", "Mar 2020": "(1,234)", ...},
      ...
    ]
  }

Output:
  {
    "periods": ["Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
    "data": {
      "revenue":    [87939.0, 100616.0, ...],
      "net_profit": [-1234.0, ...],
    }
  }
"""

import re
from typing import Optional


# ─── Core number parser ───────────────────────────────────────────────────────

def parse_indian_number(value: str) -> Optional[float]:
    """
    Parse an Indian-formatted number string to float.

    Handles:
      '87,939'      →  87939.0
      '(12,345)'    → -12345.0   (parenthesis = negative in Indian accounting)
      '12.34%'      →  12.34     (strips % sign)
      '1,23,456'    →  123456.0  (lakh format)
      ''            →  None
      '--'          →  None
      '-'           →  None
      'N/A'         →  None
      '0'           →  0.0
    """
    if value is None:
        return None

    value = str(value).strip()

    if value in ("", "-", "--", "N/A", "NA", "n/a", "nil", "Nil"):
        return None

    # Strip percentage sign — caller decides whether to store as-is or /100
    if value.endswith("%"):
        value = value[:-1].strip()

    # Detect and remove parentheses (negative)
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1].strip()

    # Remove all commas (handles both 1,23,456 and 1,234,567 formats)
    value = value.replace(",", "")

    try:
        result = float(value)
        return -result if is_negative else result
    except ValueError:
        return None


# ─── Table normalizer ─────────────────────────────────────────────────────────

def normalize_financial_table(raw: dict, label_col: str = "") -> dict:
    """
    Normalise one statement table from ScreenerScraper output.

    Args:
        raw:       The dict from scraper e.g. raw['profit_and_loss']
        label_col: The column key used as row labels. Default is "" (empty string).

    Returns:
        {
          "periods": ["Mar 2020", "Mar 2021", ...],
          "data":    {"revenue": [87939.0, None, ...], "net_profit": [...], ...}
        }
    """
    if not raw or "headers" not in raw or "rows" not in raw:
        return {"periods": [], "data": {}}

    headers = raw["headers"]
    # periods = all header values that are not the label column
    periods = [h for h in headers if h and h != label_col]

    result = {"periods": periods, "data": {}}

    for row in raw.get("rows", []):
        # Get the row label
        label = str(row.get(label_col, row.get("", ""))).strip()
        if not label:
            continue

        key = _slugify(label)
        values = [parse_indian_number(str(row.get(p, ""))) for p in periods]
        result["data"][key] = values

    return result


def normalize_shareholding(raw: dict) -> list:
    """
    Parse shareholding_pattern output from ScreenerScraper.

    The scraper returns: {"tables": [{"headers": [...], "rows": [...]}]}
    Returns a list of dicts, one per period:
      [{"period": "Sep 2023", "promoter_pct": 68.1, "fii_pct": 14.2, ...}, ...]
    """
    if not raw or "tables" not in raw:
        return []

    records = []
    for table in raw["tables"]:
        headers = table.get("headers", [])
        if not headers:
            continue

        # First column is the category label (Promoters, FIIs, DIIs, Public)
        periods = [h for h in headers if h and h != headers[0]]

        # Build a dict: {category_slug: [values per period]}
        categories = {}
        for row in table.get("rows", []):
            label = str(row.get(headers[0], "")).strip()
            if not label:
                continue
            key = _slugify(label)
            values = [parse_indian_number(str(row.get(p, ""))) for p in periods]
            categories[key] = values

        # One record per period
        for i, period in enumerate(periods):
            records.append({
                "period":        period,
                "promoter_pct":  _pick(categories, ["promoters", "promoter_promoter_group"], i),
                "fii_pct":       _pick(categories, ["foreign_institutional_investors", "fiis", "foreign_portfolio_investors"], i),
                "dii_pct":       _pick(categories, ["domestic_institutional_investors", "diis"], i),
                "public_pct":    _pick(categories, ["public", "public_non_institutional"], i),
                "pledged_pct":   _pick(categories, ["pledged_shares", "promoters_pledge"], i),
            })

    return records


# ─── Validation ───────────────────────────────────────────────────────────────

REQUIRED_PL_KEYS = {"revenue", "net_profit", "operating_profit"}
REQUIRED_BS_KEYS = {"total_assets", "borrowings"}
REQUIRED_CF_KEYS = {"cash_from_operating_activity"}

def validate_pl(data: dict) -> tuple[bool, set]:
    missing = REQUIRED_PL_KEYS - set(data.get("data", {}).keys())
    return len(missing) == 0, missing

def validate_bs(data: dict) -> tuple[bool, set]:
    missing = REQUIRED_BS_KEYS - set(data.get("data", {}).keys())
    return len(missing) == 0, missing


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """'Net Profit' → 'net_profit', 'EBITDA (%)' → 'ebitda'"""
    text = re.sub(r"[^\w\s]", "", text.lower())      # remove punctuation
    text = re.sub(r"\s+", "_", text.strip())         # spaces to underscores
    text = re.sub(r"_+", "_", text).strip("_")       # collapse multiple underscores
    return text

def _pick(categories: dict, keys: list, index: int) -> Optional[float]:
    """Try multiple possible key names for a category."""
    for key in keys:
        vals = categories.get(key)
        if vals is not None and index < len(vals):
            return vals[index]
    return None
