import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db, session_factory
from .. import sync, security

_sync_all_lock = asyncio.Lock()


router = APIRouter(prefix="/sync", tags=["sync"])

async def background_sync_all_wrapper():
    """Worker for background full sync."""
    async with session_factory() as session:
        await sync.sync_all_funds(session)

@router.post("/all")
async def trigger_full_sync(
    background_tasks: BackgroundTasks, 
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user)
):
    """Trigger a background job to sync all funds. Prevents concurrent syncs."""
    if _sync_all_lock.locked():
        raise HTTPException(status_code=409, detail="A full sync is already in progress.")
        
    async def _locked_sync():
        async with _sync_all_lock:
            await background_sync_all_wrapper()
            
    background_tasks.add_task(_locked_sync)
    return {"message": "Sync started in background"}


@router.post("/{scheme_code}")
async def sync_single_fund(
    scheme_code: str, 
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user)
):
    """Sync a single fund immediately."""
    await sync.sync_fund_data(session, scheme_code)
    return {"message": f"Sync completed for {scheme_code}"}
