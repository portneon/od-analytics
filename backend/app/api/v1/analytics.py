from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import application as application_analytics
from app.analytics import bounces as bounces_analytics
from app.analytics import domains as domains_analytics
from app.analytics import infrastructure as infra_analytics
from app.analytics import overview as overview_analytics
from app.analytics import recipients as recipients_analytics
from app.analytics import senders as senders_analytics
from app.analytics import subjects as subjects_analytics
from app.analytics import timeline as timeline_analytics
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import ok, paginated
from app.services.dataset_service import get_dataset_or_404

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["analytics"])


def _verify_access(db: Session, user: CurrentUser, dataset_id: uuid.UUID) -> None:
    get_dataset_or_404(db, tenant_id=user.tenant_id, dataset_id=dataset_id)


@router.get("/analytics/overview")
def analytics_overview(dataset_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _verify_access(db, user, dataset_id)
    return ok(overview_analytics.get_overview(db, user.tenant_id, dataset_id))


@router.get("/analytics/timeline")
def analytics_timeline(
    dataset_id: uuid.UUID,
    granularity: str = Query(default="daily", pattern="^(daily|hourly|day_of_week)$"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    if granularity == "hourly":
        data = timeline_analytics.get_hourly_timeline(db, user.tenant_id, dataset_id)
    elif granularity == "day_of_week":
        data = timeline_analytics.get_day_of_week_timeline(db, user.tenant_id, dataset_id)
    else:
        data = timeline_analytics.get_daily_timeline(db, user.tenant_id, dataset_id)
    return ok(data, meta={"granularity": granularity})


@router.get("/analytics/domains")
def analytics_domains(
    dataset_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="total_emails"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    return paginated(domains_analytics.list_domains(db, user.tenant_id, dataset_id, page=page, page_size=page_size, sort_by=sort_by))


@router.get("/analytics/recipients")
def analytics_recipients(
    dataset_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="total_emails"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    return paginated(recipients_analytics.list_recipients(db, user.tenant_id, dataset_id, page=page, page_size=page_size, sort_by=sort_by))


@router.get("/analytics/subjects")
def analytics_subjects(
    dataset_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="total_emails"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    return paginated(subjects_analytics.list_subjects(db, user.tenant_id, dataset_id, page=page, page_size=page_size, sort_by=sort_by))


@router.get("/analytics/senders")
def analytics_senders(
    dataset_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="total_emails"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    return paginated(senders_analytics.list_senders(db, user.tenant_id, dataset_id, page=page, page_size=page_size, sort_by=sort_by))


@router.get("/analytics/bounces")
def analytics_bounces(dataset_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _verify_access(db, user, dataset_id)
    return ok(bounces_analytics.list_bounce_reasons(db, user.tenant_id, dataset_id))


@router.get("/analytics/infrastructure")
def analytics_infrastructure(
    dataset_id: uuid.UUID,
    component_type: str | None = Query(default=None, pattern="^(remote_mta|relay_server|remote_ip)$"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _verify_access(db, user, dataset_id)
    return ok(infra_analytics.list_infrastructure(db, user.tenant_id, dataset_id, component_type))


@router.get("/analytics/applications")
def analytics_applications(dataset_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _verify_access(db, user, dataset_id)
    return ok(application_analytics.list_application_metrics(db, user.tenant_id, dataset_id))
