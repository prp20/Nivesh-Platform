from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import sync

router = APIRouter(prefix="/sync", tags=["sync"])

@router.post("/all")
async def trigger_full_sync(background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_db)):
    """Trigger a background job to sync all funds."""
    background_tasks.add_task(sync.sync_all_funds, session)
    return {"message": "Sync started in background"}

@router.post("/{scheme_code}")
async def sync_single_fund(scheme_code: str, session: AsyncSession = Depends(get_db)):
    """Sync a single fund immediately."""
    await sync.sync_fund_data(session, scheme_code)
    return {"message": f"Sync completed for {scheme_code}"}
