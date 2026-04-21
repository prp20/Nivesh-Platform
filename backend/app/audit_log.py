"""
Audit logging for sensitive operations.

Tracks who performed what action, when, and with what parameters.
Logs to both application logger and database for compliance.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, text

logger = logging.getLogger(__name__)


class AuditLog:
    """Structured audit logging for sensitive operations."""

    # Action types
    PIPELINE_TRIGGER = "PIPELINE_TRIGGER"
    ADMIN_ACTION = "ADMIN_ACTION"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    DATA_EXPORT = "DATA_EXPORT"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"

    @staticmethod
    async def log_action(
        action: str,
        user: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
        error_msg: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Log an action to both file and database.

        Args:
            action: Action type (e.g., PIPELINE_TRIGGER)
            user: Username or service account
            resource: Resource affected (e.g., "pipeline/prices/all")
            details: Dictionary of action parameters
            status: SUCCESS or FAILURE
            error_msg: Error message if status is FAILURE
            db: Optional AsyncSession to log to database
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Structured log for file-based logging
        log_entry = {
            "timestamp": timestamp,
            "action": action,
            "user": user,
            "resource": resource,
            "status": status,
            "details": details or {},
            "error": error_msg,
        }

        # Log to file
        if status == "FAILURE":
            logger.error(
                f"AUDIT: {action} by {user} on {resource} FAILED: {error_msg}",
                extra=log_entry,
            )
        else:
            logger.info(
                f"AUDIT: {action} by {user} on {resource}",
                extra=log_entry,
            )

        # Log to database if session provided
        if db:
            try:
                await AuditLog._log_to_db(
                    db,
                    action=action,
                    user=user,
                    resource=resource,
                    details=details,
                    status=status,
                    error_msg=error_msg,
                )
            except Exception as e:
                logger.error(f"Failed to log audit event to DB: {e}")

    @staticmethod
    async def _log_to_db(
        db: AsyncSession,
        action: str,
        user: str,
        resource: str,
        details: Optional[Dict[str, Any]],
        status: str,
        error_msg: Optional[str],
    ) -> None:
        """Log audit event to database audit_log table."""
        # Insert audit record
        insert_sql = """
        INSERT INTO audit_log
            (action, user_account, resource, details, status, error_message)
        VALUES
            (:action, :user, :resource, :details, :status, :error)
        """

        await db.execute(
            text(insert_sql),
            {
                "action": action,
                "user": user,
                "resource": resource,
                "details": json.dumps(details or {}),
                "status": status,
                "error": error_msg,
            },
        )
        await db.commit()


@asynccontextmanager
async def audit_operation(
    action: str,
    user: str,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    db: Optional[AsyncSession] = None,
):
    """
    Context manager for audit-logged operations.

    Usage:
        async with audit_operation("PIPELINE_TRIGGER", "admin_user", "pipeline/prices/all"):
            await run_daily_price_ingestion()
    """
    try:
        yield
        # Log success after operation completes
        await AuditLog.log_action(
            action=action,
            user=user,
            resource=resource,
            details=details,
            status="SUCCESS",
            db=db,
        )
    except Exception as e:
        # Log failure with error message
        await AuditLog.log_action(
            action=action,
            user=user,
            resource=resource,
            details=details,
            status="FAILURE",
            error_msg=str(e),
            db=db,
        )
        raise
