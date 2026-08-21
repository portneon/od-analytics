from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.executive import get_executive_daily_timeline, get_executive_summary
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import ok

router = APIRouter(prefix="/executive", tags=["executive"])


@router.get("/summary")
def executive_summary(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return ok(get_executive_summary(db, user.tenant_id))


@router.get("/timeline")
def executive_timeline(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return ok(get_executive_daily_timeline(db, user.tenant_id))
