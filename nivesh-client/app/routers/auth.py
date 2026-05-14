"""
Auth router — /auth/login, /auth/logout

Forwards login to the Render server, stores JWT tokens in local SQLite.
The React UI never handles tokens directly — all server-bound requests
go through the client FastAPI proxy which injects the Authorization header.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.auth import AuthToken, ServerConfig

# Import shared schemas — do not redefine
from schemas.auth import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Forward login to the Render server.
    Store the returned tokens in local SQLite (id=1 upsert).
    Return the TokenResponse to the caller.

    The React UI calls this endpoint; tokens are stored here in SQLite.
    React never sees the raw tokens — it only uses the returned access_token
    for display (e.g. to know it's authenticated), but all future server
    calls go through /proxy/* which injects the token server-side.
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=15
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": body.username, "password": body.password},
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot reach server — check NIVESH_SERVER_URL and connectivity",
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Server returned {resp.status_code}",
        )

    data = resp.json()

    # Store tokens in SQLite auth_tokens table (single row, id=1)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    stmt = sqlite_insert(AuthToken).values(
        id=1,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
        username=body.username,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "access_token":  data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at":    expires_at,
            "username":      body.username,
        },
    )
    await db.execute(stmt)

    # Record server URL and online status
    for key, val in [
        ("server_url", settings.NIVESH_SERVER_URL),
        ("is_online", "true"),
        ("last_connected_at", datetime.now(timezone.utc).isoformat()),
    ]:
        kv = sqlite_insert(ServerConfig).values(key=key, value=val)
        kv = kv.on_conflict_do_update(
            index_elements=["key"], set_={"value": val}
        )
        await db.execute(kv)

    await db.commit()
    logger.info(f"User '{body.username}' logged in — tokens stored in SQLite")

    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        token_type="bearer",
        expires_in=data["expires_in"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: AsyncSession = Depends(get_db)):
    """
    Clear stored tokens from SQLite.
    Best-effort server notification — local logout still succeeds if offline.
    """
    result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    token_row = result.scalar_one_or_none()

    if token_row:
        try:
            async with httpx.AsyncClient(
                base_url=settings.NIVESH_SERVER_URL, timeout=5
            ) as client:
                await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {token_row.access_token}"},
                    json={"refresh_token": token_row.refresh_token},
                )
        except Exception:
            pass  # Best-effort — local logout always succeeds

    await db.execute(delete(AuthToken).where(AuthToken.id == 1))
    await db.commit()
    logger.info("User logged out — tokens cleared from SQLite")
