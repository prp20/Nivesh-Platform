"""
Authentication endpoints.

POST /api/v1/auth/login   — JSON credentials → access_token + HttpOnly refresh cookie
POST /api/v1/auth/refresh — refresh cookie → new access_token
POST /api/v1/auth/logout  — clear refresh cookie (204)
GET  /api/v1/auth/me      — return current user info (requires Bearer token)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..crud import get_user_by_username
from ..security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
)
from ..schemas import LoginRequest, TokenResponse
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # HTTPS-only in prod
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",  # Only sent to auth endpoints
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with username + password.

    Returns a short-lived access_token in the response body.
    Sets an HttpOnly cookie with the refresh_token (never readable by JS).
    """
    user = await get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token(user.username)

    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh_token cookie for a new access_token.

    The refresh_token is read from the HttpOnly cookie — clients never
    need to handle it explicitly.
    """
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    username = decode_refresh_token(refresh_token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue new access token (rolling refresh — re-issue refresh cookie too)
    access_token = create_access_token({"sub": username})
    new_refresh_token = create_refresh_token(username)
    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """
    Clear the refresh_token cookie.
    Access tokens expire naturally — no server-side blocklist needed.
    """
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me")
async def read_users_me(current_user=Depends(get_current_user)):
    """Return the current authenticated user's info."""
    if isinstance(current_user, str):
        # Dev mode (ENABLE_AUTH=False) — return stub
        return {"username": current_user, "is_active": True}
    return {
        "username": current_user.username,
        "is_active": current_user.is_active,
    }
