"""RBAC + auth stub for the MVP.

Implements a minimal JWT-bearer auth scheme with three roles: admin,
operator, viewer (spec section 18). This is intentionally simple for the
MVP: a single `/api/auth/login` route issues a JWT for a user looked up in
a small in-memory/DB-backed table. It is enough to gate write endpoints
(probe point CRUD, alert approval, scenario approval) behind a role check
without building a full identity provider.

Do not use the default JWT_SECRET_KEY in production -- set a real secret
via the JWT_SECRET_KEY env var.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

Role = Literal["admin", "operator", "viewer"]

ROLE_RANK: dict[Role, int] = {"viewer": 0, "operator": 1, "admin": 2}

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(subject: str, role: Role) -> str:
    settings = get_settings()
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class CurrentUser:
    def __init__(self, username: str, role: Role) -> None:
        self.username = username
        self.role = role


def _decode_token(token: str) -> CurrentUser:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc
    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in ROLE_RANK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return CurrentUser(username=username, role=role)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser | None:
    """Returns the current user if a valid bearer token is present, else None.

    MVP note: auth is enforced per-endpoint via `require_role`, not globally,
    so that read-only dashboard endpoints keep working without a login flow
    while write/approval endpoints are protected.
    """
    if credentials is None:
        return None
    return _decode_token(credentials.credentials)


def require_role(minimum_role: Role):
    """FastAPI dependency factory: raises 401/403 unless the caller holds at
    least `minimum_role` (admin > operator > viewer)."""

    async def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> CurrentUser:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = _decode_token(credentials.credentials)
        if ROLE_RANK[user.role] < ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role >= {minimum_role}",
            )
        return user

    return dependency
