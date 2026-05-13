"""
Response envelope helpers for delta-sync compatible API responses.

All time-series and list endpoints wrap their data in a standard envelope:
  {"status": "ok", "data": [...], "meta": {...}}

This lets the client distinguish between full and delta responses,
detect offline/stale states, and track sync progress.
"""

from typing import Any, Optional


def ok(data: Any, *, meta: Optional[dict] = None) -> dict:
    """
    Wrap any data in a standard success envelope.

    Usage:
        return envelope.ok(rows, meta={"from_date": str(from_date)})
    """
    return {"status": "ok", "data": data, "meta": meta or {}}


def paginated(
    data: Any,
    *,
    total: int,
    page: int,
    page_size: int,
    **extra_meta: Any,
) -> dict:
    """
    Wrap paginated data with standard pagination meta.

    Usage:
        return envelope.paginated(items, total=count, page=page, page_size=limit)
    """
    return {
        "status": "ok",
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            **extra_meta,
        },
    }
