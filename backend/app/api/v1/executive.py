from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.executive import get_executive_daily_timeline, get_executive_summary
from app.core.database import get_db
from app.schemas.common import ok

router = APIRouter(prefix="/executive", tags=["executive"])


@router.get("/summary")
def executive_summary(db: Session = Depends(get_db)):
    return ok(get_executive_summary(db))


@router.get("/timeline")
def executive_timeline(db: Session = Depends(get_db)):
    return ok(get_executive_daily_timeline(db))
