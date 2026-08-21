"""Auth/tenant dependencies.

`tenant_id` is NEVER read from a path/query/body parameter for tenant-owned
data -- it always comes from the authenticated token via `CurrentUser`. Every
repository/analytics call in the API layer must be passed `user.tenant_id`,
not anything the client sent.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import UserRole


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    role: UserRole


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED", "Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Token is invalid or expired") from exc

    return CurrentUser(id=uuid.UUID(payload["sub"]), tenant_id=uuid.UUID(payload["tenant_id"]), role=UserRole(payload["role"]))


def require_role(*allowed: UserRole):
    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise ApiError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "You do not have permission to perform this action")
        return user

    return _check


DbSession = Session
