from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from ..database import get_db, session_factory
from .. import crud, schemas, sync

router = APIRouter(prefix="/metrics", tags=["metrics"])

async def background_sync_wrapper(scheme_code: str, job_id: str):
    """Worker function for background synchronization."""
    async with session_factory() as session:
        await sync.sync_fund_data(session, scheme_code, job_id=job_id)

@router.get("/{scheme_code}", response_model=schemas.FundMetricsResponse)
async def get_metrics(
    scheme_code: str, 
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db)
):
    """Retrieve fund metrics, triggering a background sync if data is stale."""
    # 1. Fetch existing metrics and latest job status
    metrics = await crud.get_fund_metrics(session, scheme_code)
    latest_job = await crud.get_latest_sync_job(session, scheme_code)
    
    should_refresh = False
    if not metrics:
        should_refresh = True
    else:
        # Cache for 24 hours
        time_since_calc = datetime.now() - metrics.metrics_calculated_at.replace(tzinfo=None)
        if time_since_calc > timedelta(hours=24):
            should_refresh = True

    # 2. Strict Locking: Don't refresh if a job is already RUNNING (within 10m timeout)
    sync_job_id = latest_job.id if latest_job else None
    sync_status = latest_job.status if latest_job else None
    sync_message = latest_job.message if latest_job else None

    if latest_job and latest_job.status == "RUNNING":
        if datetime.now() - latest_job.updated_at.replace(tzinfo=None) > timedelta(minutes=10):
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
async def get_sync_status(scheme_code: str, session: AsyncSession = Depends(get_db)):
    """Get the latest sync job status for a fund. Returns None if no job exists."""
    job = await crud.get_latest_sync_job(session, scheme_code)
    return job

@router.post("/{scheme_code}/compute", status_code=200)
async def compute_metrics_endpoint(
    scheme_code: str, 
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db)
):
    """Manually trigger a background metrics recomputation."""
    latest_job = await crud.get_latest_sync_job(session, scheme_code)
    
    # Strict Locking: Already running check
    if latest_job and latest_job.status == "RUNNING":
        if datetime.now() - latest_job.updated_at.replace(tzinfo=None) <= timedelta(minutes=10):
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
