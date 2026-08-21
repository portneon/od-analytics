from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import ok
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    tenant, user = auth_service.register_tenant_and_admin(
        db, tenant_name=payload.tenant_name, name=payload.name, email=payload.email, password=payload.password
    )
    db.commit()
    _, token = auth_service.authenticate(db, email=payload.email, password=payload.password)
    return ok({
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role.value},
        "tenant": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug},
    })


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate(db, email=payload.email, password=payload.password)
    return ok({
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role.value},
    })
