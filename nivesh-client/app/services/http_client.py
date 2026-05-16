"""
ServerClient — async httpx client for all calls to the Render server.

Responsibilities:
1. Reads access_token from auth_tokens SQLite table
2. Sets Authorization: Bearer header on every request
3. On 401: fetches new access_token using the stored refresh_token
4. On 5xx: retries up to 3 times with 2^n second backoff
5. On connection error: raises OfflineError
6. Updates server_config.is_online on success/failure

Usage (as async context manager):
    async with ServerClient(db) as client:
        data = await client.get("/api/v1/funds")

Usage (one-shot class method):
    data = await ServerClient.fetch(db, "GET", "/api/v1/funds")
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.auth import AuthToken, ServerConfig

logger = logging.getLogger(__name__)


class OfflineError(Exception):
    """Raised when the server cannot be reached."""
    pass


class SessionExpiredError(Exception):
    """Raised when the refresh token is also expired — user must log in again."""
    pass


class ServerClient:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None

    async def __aenter__(self):
        self._token = await self._load_access_token()
        self._client = httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL,
            timeout=30,
            headers=self._auth_headers(),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    def _auth_headers(self) -> dict:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def get(self, path: str, params: dict = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict = None) -> Any:
        return await self._request("POST", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        json: dict = None,
        _retry: int = 0,
    ) -> Any:
        try:
            resp = await self._client.request(
                method, path, params=params, json=json
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            await self._mark_offline()
            raise OfflineError(f"Server unreachable: {e}") from e

        # ── Token expired ──────────────────────────────────────────────────────
        if resp.status_code == 401 and _retry == 0:
            logger.info("Access token expired — refreshing")
            try:
                self._token = await self._refresh_token()
                self._client.headers["Authorization"] = f"Bearer {self._token}"
                return await self._request(method, path, params=params, json=json, _retry=1)
            except SessionExpiredError:
                raise
            except Exception as e:
                raise OfflineError(f"Token refresh failed: {e}") from e

        # ── Server errors: retry up to 3 times with backoff ───────────────────
        if resp.status_code >= 500 and _retry < 3:
            await asyncio.sleep(2 ** _retry)
            return await self._request(method, path, params=params, json=json, _retry=_retry + 1)

        resp.raise_for_status()
        await self._mark_online()
        return resp.json()

    async def _load_access_token(self) -> Optional[str]:
        result = await self.db.execute(
            select(AuthToken).where(AuthToken.id == 1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return row.access_token

    async def _refresh_token(self) -> str:
        """Call /api/v1/auth/refresh with the stored refresh_token."""
        result = await self.db.execute(
            select(AuthToken).where(AuthToken.id == 1)
        )
        token_row = result.scalar_one_or_none()
        if not token_row or not token_row.refresh_token:
            raise SessionExpiredError("No refresh token stored")

        async with httpx.AsyncClient(base_url=settings.NIVESH_SERVER_URL, follow_redirects=True) as c:
            resp = await c.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": token_row.refresh_token},
            )
            if resp.status_code == 401:
                raise SessionExpiredError("Refresh token expired — please log in again")
            resp.raise_for_status()
            data = resp.json()

        # Save new access token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        await self.db.execute(
            update(AuthToken)
            .where(AuthToken.id == 1)
            .values(access_token=data["access_token"], expires_at=expires_at)
        )
        await self.db.commit()
        logger.info("Access token refreshed")
        return data["access_token"]

    async def _mark_online(self):
        await self._set_config("is_online", "true")
        await self._set_config(
            "last_connected_at", datetime.now(timezone.utc).isoformat()
        )

    async def _mark_offline(self):
        await self._set_config("is_online", "false")

    async def _set_config(self, key: str, value: str):
        stmt = sqlite_insert(ServerConfig).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"], set_={"value": value}
        )
        await self.db.execute(stmt)
        await self.db.commit()

    @classmethod
    async def fetch(
        cls, db: AsyncSession, method: str, path: str, **kwargs
    ) -> Any:
        """Convenience one-shot method for simple calls."""
        async with cls(db) as client:
            return await client._request(method, path, **kwargs)
