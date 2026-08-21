from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.services import report_service
from app.services.dataset_service import get_dataset_or_404

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["reports"])


@router.post("/reports")
def generate_report(
    dataset_id: uuid.UUID,
    format: str = Query(default="pdf", pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    dataset = get_dataset_or_404(db, tenant_id=user.tenant_id, dataset_id=dataset_id)
    report = report_service.build_report_data(db, user.tenant_id, dataset)

    if format == "csv":
        content = report_service.render_csv(report)
        return Response(
            content=content, media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="report-{dataset_id}.csv"'},
        )

    content = report_service.render_pdf(report)
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{dataset_id}.pdf"'},
    )
