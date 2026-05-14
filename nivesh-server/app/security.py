"""
Security and authentication utilities.

Provides JWT-based authentication, password hashing, and FastAPI dependencies.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=settings.ENABLE_AUTH,
)


# ── Password hashing ──────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _bcrypt.hashpw(
        password.encode("utf-8"), _bcrypt.gensalt()
    ).decode("utf-8")


# Keep alias for callers that import hash_password
hash_password = get_password_hash


# ── Token creation ────────────────────────────────────────────────────────────

def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a short-lived JWT access token."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _make_token({**data, "type": "access"}, delta)


def create_refresh_token(username: str) -> str:
    """Create a long-lived JWT refresh token."""
    return _make_token(
        {"sub": username, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ── Token verification ────────────────────────────────────────────────────────

def _decode_token(token: str, expected_type: str) -> Optional[str]:
    """Decode a JWT and return the 'sub' claim, or None if invalid."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[str]:
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> Optional[str]:
    return _decode_token(token, "refresh")


# ── FastAPI auth dependency ───────────────────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate the Bearer token and return the AdminUser ORM object.

    When ENABLE_AUTH=False (dev mode), returns the string "dev_user" so
    existing route signatures that type-hint the return as str still work.
    When ENABLE_AUTH=True, validates the JWT and fetches the user from DB.
    Raises 401 if the token is missing, invalid, expired, or user is inactive.
    """
    if not settings.ENABLE_AUTH:
        return "dev_user"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    # Support both old-style tokens (no type claim) and new tokens (type=access)
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: Optional[str] = payload.get("sub")
        if not username:
            raise credentials_exception
        token_type = payload.get("type")
        # Reject refresh tokens used as access tokens
        if token_type == "refresh":
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception

    # Fetch user from DB
    from .models import AdminUser
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    return user


async def require_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Enforce admin-level authentication (same as get_current_user for now)."""
    user = await get_current_user(token, db)
    return user
