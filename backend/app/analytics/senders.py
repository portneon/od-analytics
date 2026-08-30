from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.analytics.entities import list_entity_metrics
from app.models.dimensions import Sender
from app.models.metrics import SenderMetrics


def list_senders(db: Session, dataset_id: uuid.UUID, **kwargs) -> dict:
    return list_entity_metrics(
        db,
        metrics_model=SenderMetrics,
        dimension_model=Sender,
        dimension_id_col_name="sender_id",
        name_col="email",
        dataset_id=dataset_id,
        extra_fields={"unique_recipients": "unique_recipients", "unique_subjects": "unique_subjects"},
        **kwargs,
    )
