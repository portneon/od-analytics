from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.analytics.entities import list_entity_metrics
from app.models.dimensions import Subject
from app.models.metrics import SubjectMetrics


def list_subjects(db: Session, dataset_id: uuid.UUID, **kwargs) -> dict:
    return list_entity_metrics(
        db,
        metrics_model=SubjectMetrics,
        dimension_model=Subject,
        dimension_id_col_name="subject_id",
        name_col="subject",
        dataset_id=dataset_id,
        extra_fields={"unique_recipients": "unique_recipients"},
        **kwargs,
    )
