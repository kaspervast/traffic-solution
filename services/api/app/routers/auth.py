"""Auth endpoint (spec section 18): admin login backing the RBAC that
require_role() already enforces on write endpoints elsewhere. Intentionally
minimal -- one username+password login issuing a JWT. No registration,
password-reset, or refresh-token flow; the initial user is created via
scripts/seed_admin_user.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Role, create_access_token, verify_password
from app.db.models import AppUser
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: Role


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(AppUser).where(AppUser.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        # Same message for "no such user" and "wrong password" -- don't leak
        # which one it was.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(subject=user.username, role=user.role)
    return LoginResponse(access_token=token, username=user.username, role=user.role)
