from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from .. import security, schemas

router = APIRouter(prefix="/auth", tags=["auth"])

# Pre-computed bcrypt hash of "admin123" — avoids running bcrypt on every cold start.
# In production, replace with a real user management system.
_ADMIN_HASHED_PASSWORD = (
    "$2b$12$FagauQNsqQSnJYIXGxiZJuEyZJgvQT7jDoNf7EyCByQ1qxfYdMNVS"
)

FAKE_USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": _ADMIN_HASHED_PASSWORD,
        "disabled": False,
    }
}

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = FAKE_USERS_DB.get(form_data.username)
    if not user or not security.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = security.create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: str = Depends(security.get_current_user)):
    return {"username": current_user}
