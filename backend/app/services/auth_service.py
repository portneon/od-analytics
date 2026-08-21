from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import ApiError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from fastapi import status


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


def register_tenant_and_admin(db: Session, *, tenant_name: str, name: str, email: str, password: str) -> tuple[Tenant, User]:
    email = email.strip().lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "EMAIL_ALREADY_REGISTERED", "A user with this email already exists")

    base_slug = _slugify(tenant_name)
    slug = base_slug
    suffix = 1
    while db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none() is not None:
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    tenant = Tenant(name=tenant_name, slug=slug)
    db.add(tenant)
    db.flush()

    user = User(tenant_id=tenant.id, email=email, name=name, role=UserRole.ADMIN, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return tenant, user


def authenticate(db: Session, *, email: str, password: str) -> tuple[User, str]:
    email = email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Invalid email or password")

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value)
    return user, token
