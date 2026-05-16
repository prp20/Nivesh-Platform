# nivesh-client/app/services/token_refresh.py
"""
Proactive JWT access token refresh.

refresh_if_expiring_soon(db, window_seconds=300):
    Called by APScheduler every 5 minutes.
    Reads expires_at from auth_tokens (id=1).
    If time remaining < window_seconds, POSTs /api/v1/auth/refresh.
    Updates auth_tokens with new access_token and expires_at.
    Returns True if refreshed, False if not needed or not logged in.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.auth import AuthToken
from ..services.http_client import SessionExpiredError

logger = logging.getLogger(__name__)


async def refresh_if_expiring_soon(
    db: AsyncSession,
    window_seconds: int = 300,
) -> bool:
    """
    Proactively refresh the access token if it expires within window_seconds.

    Returns True if a refresh was performed.
    Returns False if token is still valid, or no user is logged in.
    Raises SessionExpiredError if the refresh token itself is rejected (user must re-login).
    On server unreachable: logs warning, returns False (retried in 5 min by scheduler).
    """
    result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    row = result.scalar_one_or_none()
    if not row or not row.refresh_token:
        return False  # Not logged in — nothing to do

    # Normalise to UTC-aware datetime
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    time_remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()

    if time_remaining > window_seconds:
        logger.debug(
            "Token valid for %.0f more seconds — skipping proactive refresh",
            time_remaining,
        )
        return False

    logger.info(
        "Token expiring in %.0f seconds (threshold=%d) — refreshing proactively",
        time_remaining,
        window_seconds,
    )

    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=15
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": row.refresh_token},
            )
            if resp.status_code == 401:
                raise SessionExpiredError(
                    "Refresh token rejected — user must log in again"
                )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Proactive token refresh skipped — server unreachable: %s", e)
        return False

    new_expires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    await db.execute(
        update(AuthToken)
        .where(AuthToken.id == 1)
        .values(
            access_token=data["access_token"],
            expires_at=new_expires,
        )
    )
    await db.commit()
    logger.info("Access token refreshed — new expiry: %s", new_expires.isoformat())
    return True
