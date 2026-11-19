from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.deps import ApiError
from app.ingestion.csv_loader import CsvValidationError, sniff_header, validate_upload
from app.ingestion.registry import available_sources, detect_source
from app.models.anomaly import Anomaly
from app.models.dataset import Dataset, DatasetStatus, ImportJob, ImportJobStatus
from app.models.email_event import EmailEvent
from app.models.metrics import (
    ApplicationMetrics,
    BounceReasonMetrics,
    DailyEmailMetrics,
    DomainMetrics,
    HourlyEmailMetrics,
    InfrastructureMetrics,
    RecipientMetrics,
    SenderMetrics,
    SubjectMetrics,
)
from app.services.storage import get_storage_service
from fastapi import status

# Every table with a dataset_id FK, in an order that's safe to delete in
# (none of these reference each other, only `datasets` -- but `datasets`
# itself must go last).
_DATASET_CHILD_TABLES = [
    Anomaly,
    ApplicationMetrics,
    BounceReasonMetrics,
    DailyEmailMetrics,
    DomainMetrics,
    EmailEvent,
    HourlyEmailMetrics,
    InfrastructureMetrics,
    RecipientMetrics,
    SenderMetrics,
    SubjectMetrics,
    ImportJob,
]


def create_dataset(
    db: Session,
    *,
    file_name: str,
    content: bytes,
    source: str = "zoho_mail",
    is_whatsapp: bool = False,
    dataset_name: str | None = None,
) -> Dataset:
    try:
        validate_upload(file_name, len(content))
    except CsvValidationError as exc:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_FILE", str(exc)) from exc

    if source not in available_sources():
        raise ApiError(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_SOURCE", f"Unsupported source '{source}'")

    # `is_whatsapp` is an explicit declaration from the upload form -- it
    # always wins over sniffing. Otherwise (the upload form today never
    # sends anything but the bare "zoho_mail" default) sniff the file's own
    # header row to route it to the right adapter instead of always
    # assuming Zoho.
    effective_default = "whatsapp_gateway" if is_whatsapp else source
    detected_source = detect_source(sniff_header(content), default=effective_default)

    dataset = Dataset(
        name=dataset_name or file_name,
        source=detected_source,
        file_name=file_name,
        file_path="",  # set after storage below
        status=DatasetStatus.UPLOADING,
    )
    db.add(dataset)
    db.flush()

    storage = get_storage_service()
    file_path = storage.save(dataset.id, file_name, content)
    dataset.file_path = file_path
    dataset.status = DatasetStatus.QUEUED
    db.flush()

    return dataset


def create_import_job(db: Session, *, dataset_id: uuid.UUID) -> ImportJob:
    job = ImportJob(dataset_id=dataset_id, status=ImportJobStatus.QUEUED)
    db.add(job)
    db.flush()
    return job


def get_dataset_or_404(db: Session, *, dataset_id: uuid.UUID) -> Dataset:
    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if dataset is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "DATASET_NOT_FOUND", "Dataset was not found")
    return dataset


def list_datasets(db: Session) -> list[Dataset]:
    return list(db.execute(select(Dataset).order_by(Dataset.created_at.desc())).scalars())


def delete_dataset(db: Session, *, dataset_id: uuid.UUID) -> None:
    """Deletes a dataset and everything derived from it (events, all metrics
    tables, anomalies, import jobs) plus its stored raw file. None of the
    dataset_id FKs cascade at the DB level, so every child table is cleared
    explicitly before the dataset row itself."""
    dataset = get_dataset_or_404(db, dataset_id=dataset_id)

    for model in _DATASET_CHILD_TABLES:
        db.execute(delete(model).where(model.dataset_id == dataset_id))

    db.delete(dataset)
    db.commit()

    get_storage_service().delete(dataset_id)
