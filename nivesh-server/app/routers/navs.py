from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas, security
from ..utils import envelope

router = APIRouter(prefix="/navs", tags=["navs"])


@router.post("/{scheme_code}/bulk", status_code=201)
async def upload_bulk_nav(
    scheme_code: str,
    payload: schemas.BulkNavUpload,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(security.get_current_user),
):
    count = await crud.bulk_insert_fund_navs(session, scheme_code, payload.data)
    return {"message": f"Successfully processed {count} NAV records"}


@router.get("/{scheme_code}")
async def get_nav_history(
    scheme_code: str,
    limit: int = Query(100, ge=1, le=5000),
    from_date: Optional[date] = Query(
        None,
        description="Return NAVs on or after this date (YYYY-MM-DD) — for delta sync",
    ),
    session: AsyncSession = Depends(get_db),
    current_user=Depends(security.get_current_user),
):
    """
    Retrieve NAV history for a fund.

    Supports delta sync via from_date: pass the date of your last sync
    and only newer records are returned. Wrap response includes meta.from_date
    so the client can track sync state.
    """
    rows = await crud.get_fund_nav_history(session, scheme_code, limit, from_date)
    return envelope.ok(
        [schemas.FundNavHistoryRead.model_validate(r) for r in rows],
        meta={"from_date": str(from_date) if from_date else None, "count": len(rows)},
    )
