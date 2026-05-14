from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ============================================================================
# AUTH SCHEMAS
# ============================================================================

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    is_active: bool = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    username: str
    password: str
