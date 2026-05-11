"""Metric formatters for LLM prompt context."""


def pct(v, decimals: int = 2) -> str:
    """Format a decimal ratio as a percentage string, e.g. 0.123 → '12.30%'."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def ratio(v, decimals: int = 2) -> str:
    """Format a ratio/score, e.g. 1.234 → '1.23'."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def crore(v) -> str:
    """Format a value in crores, e.g. 4500.5 → '₹4,500.50 Cr'."""
    if v is None:
        return "N/A"
    try:
        return f"₹{float(v):,.2f} Cr"
    except (TypeError, ValueError):
        return "N/A"


def price(v) -> str:
    """Format a stock price in INR."""
    if v is None:
        return "N/A"
    try:
        return f"₹{float(v):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def score(v, out_of: int = 100) -> str:
    """Format a score with its denominator, e.g. 72.5 → '72.50/100'."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}/{out_of}"
    except (TypeError, ValueError):
        return "N/A"


def na(v) -> str:
    """Return 'N/A' for None, else stringify."""
    return "N/A" if v is None else str(v)
