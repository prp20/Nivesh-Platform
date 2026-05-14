import re

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from ..database import get_db, session_factory
from .. import crud, schemas, sync, security

router = APIRouter(prefix="/metrics", tags=["metrics"])

_SCHEME_CODE_RE = re.compile(r"^\w{1,50}$")


def _validate_scheme_code(scheme_code: str) -> None:
    if not _SCHEME_CODE_RE.match(scheme_code):
        raise HTTPException(status_code=400, detail="Invalid scheme_code format.")


async def background_sync_wrapper(scheme_code: str, job_id: int):
    """Worker function for background synchronization."""
    async with session_factory() as session:
        await sync.sync_fund_data(session, scheme_code, job_id=job_id)


@router.get("/{scheme_code}", response_model=schemas.FundMetricsResponse)
async def get_metrics(
    scheme_code: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(security.get_current_user),
):
    """Retrieve fund metrics, triggering a background sync if data is stale."""
    _validate_scheme_code(scheme_code)

    metrics = await crud.get_fund_metrics(session, scheme_code)
    latest_run = await crud.get_latest_etl_run(session, "amfi_nav", entity_id=scheme_code)

    should_refresh = False
    now = datetime.now(timezone.utc)

    if not metrics:
        should_refresh = True
    else:
        calc_at = metrics.metrics_calculated_at
        if calc_at.tzinfo is None:
            calc_at = calc_at.replace(tzinfo=timezone.utc)
        if now - calc_at > timedelta(hours=24):
            should_refresh = True

    # Don't refresh if a job is already RUNNING (within 10m timeout)
    sync_job_id = latest_run.id if latest_run else None
    sync_status = latest_run.status if latest_run else None
    sync_message = latest_run.error_msg if latest_run else None

    if latest_run and latest_run.status == "RUNNING":
        started_at = latest_run.started_at
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        if started_at and now - started_at > timedelta(minutes=10):
            should_refresh = True  # Orphaned job — safe to restart
        else:
            should_refresh = False
            sync_status = "RUNNING"

    if should_refresh:
        run, created = await crud.start_etl_run(
            session, "amfi_nav", entity_id=scheme_code, triggered_by="manual"
        )
        sync_job_id = run.id
        sync_status = run.status
        sync_message = run.error_msg
        if created:
            background_tasks.add_task(background_sync_wrapper, scheme_code, run.id)

    return {
        "metrics": metrics,
        "sync_job_id": sync_job_id,
        "sync_status": sync_status,
        "sync_message": sync_message,
    }


@router.get("/{scheme_code}/status")
async def get_sync_status(
    scheme_code: str,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(security.get_current_user),
):
    """Get the latest ETL run status for a fund. Returns None if no run exists."""
    run = await crud.get_latest_etl_run(session, "amfi_nav", entity_id=scheme_code)
    if not run:
        return None
    return schemas.EtlRunRead.model_validate(run)


@router.post("/{scheme_code}/compute", status_code=200)
async def compute_metrics_endpoint(
    scheme_code: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(security.get_current_user),
):
    """Manually trigger a background metrics recomputation."""
    _validate_scheme_code(scheme_code)
    latest_run = await crud.get_latest_etl_run(session, "amfi_nav", entity_id=scheme_code)
    now = datetime.now(timezone.utc)

    if latest_run and latest_run.status == "RUNNING":
        started_at = latest_run.started_at
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if started_at and now - started_at <= timedelta(minutes=10):
            return {
                "message": "Sync already in progress",
                "job_id": latest_run.id,
                "sync_status": "RUNNING",
            }

    run, created = await crud.start_etl_run(
        session, "amfi_nav", entity_id=scheme_code, triggered_by="manual"
    )
    if created:
        background_tasks.add_task(background_sync_wrapper, scheme_code, run.id)
        return {
            "message": "Background sync started",
            "job_id": run.id,
            "sync_status": "RUNNING",
        }
    else:
        return {
            "message": "Sync already in progress",
            "job_id": run.id,
            "sync_status": "RUNNING",
        }
