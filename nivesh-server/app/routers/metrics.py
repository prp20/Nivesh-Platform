import re

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from ..database import get_db, session_factory
from .. import crud, schemas, sync, security  # security used for auth deps

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Scheme codes from AMFI are numeric strings (e.g. "119533").
# Reject anything that doesn't look like a valid code before hitting the DB
# or spawning a sync job.
_SCHEME_CODE_RE = re.compile(r"^\w{1,50}$")


def _validate_scheme_code(scheme_code: str) -> None:
    if not _SCHEME_CODE_RE.match(scheme_code):
        raise HTTPException(status_code=400, detail="Invalid scheme_code format.")


async def background_sync_wrapper(scheme_code: str, job_id: str):
    """Worker function for background synchronization."""
    async with session_factory() as session:
        await sync.sync_fund_data(session, scheme_code, job_id=job_id)

@router.get("/{scheme_code}", response_model=schemas.FundMetricsResponse)
async def get_metrics(
    scheme_code: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Retrieve fund metrics, triggering a background sync if data is stale."""
    _validate_scheme_code(scheme_code)

    # 1. Fetch existing metrics and latest job status
    metrics = await crud.get_fund_metrics(session, scheme_code)
    latest_job = await crud.get_latest_sync_job(session, scheme_code)
    
    should_refresh = False
    now = datetime.now(timezone.utc)
    
    if not metrics:
        should_refresh = True
    else:
        # Cache for 24 hours - handle potentially naive timestamps from DB
        calc_at = metrics.metrics_calculated_at
        if calc_at.tzinfo is None:
            calc_at = calc_at.replace(tzinfo=timezone.utc)
            
        time_since_calc = now - calc_at
        if time_since_calc > timedelta(hours=24):
            should_refresh = True

    # 2. Strict Locking: Don't refresh if a job is already RUNNING (within 10m timeout)
    sync_job_id = latest_job.id if latest_job else None
    sync_status = latest_job.status if latest_job else None
    sync_message = latest_job.message if latest_job else None

    if latest_job and latest_job.status == "RUNNING":
        # Handle naive updated_at
        updated_at = latest_job.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
            
        if now - updated_at > timedelta(minutes=10):
            # Safe to assume orphaned if no update in 10 mins
            should_refresh = True
        else:
            should_refresh = False
            sync_status = "RUNNING"

    if should_refresh:
        job, created = await crud.create_sync_job(session, scheme_code)
        sync_job_id = job.id
        sync_status = job.status
        sync_message = job.message
        if created:
            background_tasks.add_task(background_sync_wrapper, scheme_code, job.id)
            
    return {
        "metrics": metrics,
        "sync_job_id": sync_job_id,
        "sync_status": sync_status,
        "sync_message": sync_message
    }

@router.get("/{scheme_code}/status", response_model=Optional[schemas.SyncJobRead])
async def get_sync_status(
    scheme_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Get the latest sync job status for a fund. Returns None if no job exists."""
    job = await crud.get_latest_sync_job(session, scheme_code)
    return job

@router.post("/{scheme_code}/compute", status_code=200)
async def compute_metrics_endpoint(
    scheme_code: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Manually trigger a background metrics recomputation."""
    _validate_scheme_code(scheme_code)
    latest_job = await crud.get_latest_sync_job(session, scheme_code)
    now = datetime.now(timezone.utc)
    
    # Strict Locking: Already running check
    if latest_job and latest_job.status == "RUNNING":
        updated_at = latest_job.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
            
        if now - updated_at <= timedelta(minutes=10):
            return {
                "message": "Sync already in progress", 
                "job_id": latest_job.id,
                "sync_status": "RUNNING",
                "sync_message": latest_job.message
            }
    
    # Start or join job
    job, created = await crud.create_sync_job(session, scheme_code)
    if created:
        background_tasks.add_task(background_sync_wrapper, scheme_code, job.id)
        return {
            "message": "Background sync started", 
            "job_id": job.id,
            "sync_status": "RUNNING",
            "sync_message": "Initializing sync..."
        }
    else:
        return {
            "message": "Sync already in progress", 
            "job_id": job.id,
            "sync_status": "RUNNING",
            "sync_message": job.message
        }
