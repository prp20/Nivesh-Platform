"""
Security and authentication utilities.

Provides JWT-based authentication, password hashing, and role-based access control.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .config import settings

logger = logging.getLogger(__name__)

# Authentication settings from config
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=settings.ENABLE_AUTH,  # Don't auto-error if auth is disabled
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Claims to include in token (typically {"sub": username})
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    """
    Validate JWT token and return username.

    DISABLED: Returns 'dev_user' without validation.
    """
    return "dev_user"

    # if not settings.ENABLE_AUTH:
    #     return "dev_user"
    #
    # credentials_exception = HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Could not validate credentials",
    #     headers={"WWW-Authenticate": "Bearer"},
    # )
    #
    # if not token:
    #     raise credentials_exception
    #
    # try:
    #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #     username: str = payload.get("sub")
    #     if username is None:
    #         raise credentials_exception
    # except JWTError as e:
    #     logger.warning(f"JWT validation failed: {e}")
    #     raise credentials_exception
    #
    # return username


async def require_admin(
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    """
    Enforce admin-level authentication for sensitive operations.

    DISABLED: Returns 'admin_dev' without validation.
    """
    return "admin_dev"

    # # In dev mode, require explicit admin token for sensitive operations
    # if not settings.ENABLE_AUTH:
    #     admin_token = getattr(settings, "ADMIN_TOKEN", None)
    #     if not admin_token:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="Admin token required. Set ADMIN_TOKEN environment variable.",
    #         )
    #     if token != admin_token:
    #         logger.warning("Unauthorized admin access attempt with invalid token")
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="Invalid admin token",
    #         )
    #     return "admin_dev"
    #
    # # Production: validate JWT and check admin role
    # credentials_exception = HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Could not validate credentials",
    #     headers={"WWW-Authenticate": "Bearer"},
    # )
    #
    # if not token:
    #     raise credentials_exception
    #
    # try:
    #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #     username: str = payload.get("sub")
    #     role: str = payload.get("role", "user")  # Default role is 'user'
    #
    #     if username is None:
    #         raise credentials_exception
    #
    #     # Check if user has admin role
    #     if role != "admin":
    #         logger.warning(f"Non-admin user {username} attempted admin operation")
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="Admin access required",
    #         )
    #
    # except JWTError as e:
    #     logger.warning(f"JWT validation failed: {e}")
    #     raise credentials_exception
    #
    # return username
