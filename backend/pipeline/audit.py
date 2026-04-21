import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncpg
from app.config import settings
from app.database import raw_connection

logger = logging.getLogger(__name__)




class _AuditRecord:
    def __init__(self, audit_id: int, records_in: int = 0):
        self.audit_id    = audit_id
        self.records_in  = records_in
        self.records_out = 0
        self.error_msg   = None
        self.status      = "RUNNING"

    async def update_progress(self, records_out: int):
        """Immediately updates processed records count in the database (using pool)."""
        if self.audit_id == -1:
            return
        self.records_out = records_out
        try:
            async with raw_connection() as conn:
                sql = "UPDATE pipeline_audit SET records_out=$1 WHERE id=$2"
                await conn.execute(sql, self.records_out, self.audit_id)
        except Exception as e:
            logger.warning(f"Failed to update audit progress: {e}")




@asynccontextmanager
async def audit_job(job_name: str, stock_id: int = None, records_in: int = 0):
    """
    Context manager for audit job tracking with incremental progress support.
    Usage:
        async with audit_job('price_daily_ingestion', records_in=500) as audit:
            for item in items:
                # ... process ...
                await audit.update_progress(count)
    """
    try:
        audit_id = await _insert_audit(job_name, stock_id, records_in)
    except Exception as e:
        logger.warning(f"Could not start audit for {job_name}: {e}")
        audit_id = -1

    record = _AuditRecord(audit_id, records_in)
    try:
        yield record
        record.status = "SUCCESS"
    except Exception as e:
        record.status    = "FAILED"
        record.error_msg = str(e)
        raise
    finally:
        if audit_id != -1:
            await _close_audit(audit_id, record)



async def _insert_audit(job_name: str, stock_id: int = None, records_in: int = 0) -> int:
    """Insert a new audit record and return its ID."""
    async with raw_connection() as conn:
        sql = """
            INSERT INTO pipeline_audit (job_name, stock_id, status, started_at, records_in)
            VALUES ($1, $2, 'RUNNING', NOW(), $3)
            RETURNING id
        """
        row = await conn.fetchrow(sql, job_name, stock_id, records_in)
        return row["id"]



async def _close_audit(audit_id: int, record: _AuditRecord) -> None:
    """Close an audit record with final status and metrics."""
    async with raw_connection() as conn:
        sql = """
            UPDATE pipeline_audit
            SET status=$1, ended_at=NOW(), records_out=$2, error_msg=$3
            WHERE id=$4
        """
        await conn.execute(sql, record.status, record.records_out, record.error_msg, audit_id)

