"""Generic paginated entity-metrics listing, shared by recipients/domains/
subjects/senders analytics endpoints -- they're structurally identical
(a metrics table joined to its dimension table for the display name),
so one implementation avoids four near-duplicate query functions.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import settings

_SORTABLE_FIELDS = {"total_emails", "delivery_rate", "bounce_rate", "failure_rate", "successful", "hard_bounces", "soft_bounces", "failures"}


def list_entity_metrics(
    db: Session,
    *,
    metrics_model,
    dimension_model,
    dimension_id_col_name: str,
    name_col: str,
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    page: int = 1,
    page_size: int | None = None,
    sort_by: str = "total_emails",
    sort_desc: bool = True,
    extra_fields: dict[str, Any] | None = None,
) -> dict:
    page_size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    sort_by = sort_by if sort_by in _SORTABLE_FIELDS else "total_emails"
    sort_col = getattr(metrics_model, sort_by)

    dimension_id_col = getattr(metrics_model, dimension_id_col_name)
    name_col_obj = getattr(dimension_model, name_col)

    base_stmt: Select = (
        select(metrics_model, name_col_obj)
        .join(dimension_model, dimension_id_col == dimension_model.id)
        .where(metrics_model.tenant_id == tenant_id, metrics_model.dataset_id == dataset_id)
    )

    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

    order_col = sort_col.desc() if sort_desc else sort_col.asc()
    rows = db.execute(base_stmt.order_by(order_col).offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for metrics_row, name in rows:
        item = {
            "id": str(getattr(metrics_row, dimension_id_col_name)),
            "name": name,
            "total_emails": metrics_row.total_emails,
            "successful": metrics_row.successful,
            "hard_bounces": metrics_row.hard_bounces,
            "soft_bounces": metrics_row.soft_bounces,
            "failures": metrics_row.failures,
            "delivery_rate": metrics_row.delivery_rate,
            "bounce_rate": metrics_row.bounce_rate,
            "failure_rate": metrics_row.failure_rate,
        }
        if extra_fields:
            for out_key, attr_name in extra_fields.items():
                item[out_key] = getattr(metrics_row, attr_name, None)
        items.append(item)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }
