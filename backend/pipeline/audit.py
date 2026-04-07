# backend/pipeline/audit.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncpg
from app.config import settings


class _AuditRecord:
    def __init__(self):
        self.records_out = 0
        self.error_msg   = None
        self.status      = "RUNNING"


@asynccontextmanager
async def audit_job(job_name: str, stock_id: int = None):
    """
    Context manager for audit job tracking.
    Usage:
        async with audit_job('price_daily_ingestion', stock_id=123) as audit:
            audit.records_out = 500
    """
    record = _AuditRecord()
    audit_id = await _insert_audit(job_name, stock_id)
    try:
        yield record
        record.status = "SUCCESS"
    except Exception as e:
        record.status    = "FAILED"
        record.error_msg = str(e)
        raise
    finally:
        await _close_audit(audit_id, record)


async def _insert_audit(job_name: str, stock_id: int = None) -> int:
    """Insert a new audit record and return its ID."""
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        sql = """
            INSERT INTO pipeline_audit (job_name, stock_id, status, started_at)
            VALUES ($1, $2, 'RUNNING', NOW())
            RETURNING id
        """
        row = await conn.fetchrow(sql, job_name, stock_id)
        return row["id"]
    finally:
        await conn.close()


async def _close_audit(audit_id: int, record: _AuditRecord) -> None:
    """Close an audit record with final status and metrics."""
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        sql = """
            UPDATE pipeline_audit
            SET status=$1, ended_at=NOW(), records_out=$2, error_msg=$3
            WHERE id=$4
        """
        await conn.execute(sql, record.status, record.records_out, record.error_msg, audit_id)
    finally:
        await conn.close()
