"""Background jobs.

`process_dataset_task` runs the full pipeline stages sequentially
(INGEST -> CLASSIFY [inline in ingestion] -> CALCULATE_METRICS ->
CALCULATE_RECIPIENT_RISK -> DETECT_ANOMALIES) via FastAPI's BackgroundTasks.
They're logically separate stages (and logged/tracked as such via ImportJob
progress) but chained in one task rather than split into separate queued
jobs -- simpler operationally for a single-dataset import, with no loss of
observability since each stage's row counts are logged and any stage
failure still marks the whole job FAILED with the responsible stage in the
error message.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.analytics.aggregation import calculate_all_metrics
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.ingestion.csv_loader import CsvValidationError
from app.ingestion.pipeline import run_ingestion_pipeline
from app.intelligence.anomaly_detection import detect_anomalies
from app.intelligence.risk_scoring import calculate_recipient_risk
from app.models.dataset import Dataset, DatasetStatus, ImportJob, ImportJobStatus

logger = get_logger(__name__)


def process_dataset_task(dataset_id: str, import_job_id: str) -> dict:
    db = SessionLocal()
    stage = "initialization"
    try:
        dataset = db.get(Dataset, uuid.UUID(dataset_id))
        job = db.get(ImportJob, uuid.UUID(import_job_id))
        if dataset is None or job is None:
            raise RuntimeError(f"Dataset or ImportJob not found: {dataset_id}/{import_job_id}")

        dataset.status = DatasetStatus.PROCESSING
        job.status = ImportJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        stage = "ingestion"
        result = run_ingestion_pipeline(db, dataset_id=dataset.id, file_path=dataset.file_path, source=dataset.source)

        dataset.row_count = result.total_rows
        dataset.date_start = result.date_start
        dataset.date_end = result.date_end
        dataset.quality_report = result.quality_report.model_dump(mode="json")

        job.total_rows = result.total_rows
        job.processed_rows = result.processed_rows
        job.failed_rows = result.failed_rows
        job.duplicate_rows = result.duplicate_rows
        db.commit()

        stage = "calculate_metrics"
        calculate_all_metrics(db, dataset.id)
        db.commit()

        stage = "calculate_recipient_risk"
        calculate_recipient_risk(db, dataset.id)
        db.commit()

        stage = "detect_anomalies"
        detect_anomalies(db, dataset.id)
        db.commit()

        # Zero valid events (e.g. a file whose columns don't map to the
        # canonical schema at all) means the dataset has no usable data --
        # that's a failure, not a "partial" success, even though every row
        # technically went through the pipeline without raising.
        if result.processed_rows == 0:
            dataset.status = DatasetStatus.FAILED
            job.status = ImportJobStatus.FAILED
            job.error_message = "No valid rows could be parsed from this file -- check that its columns match the expected schema."[:2000]
        elif result.failed_rows > 0:
            dataset.status = DatasetStatus.PARTIAL
            job.status = ImportJobStatus.PARTIAL
        else:
            dataset.status = DatasetStatus.COMPLETED
            job.status = ImportJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("dataset.processing.complete", dataset_id=dataset_id, status=dataset.status.value)
        return {"dataset_id": dataset_id, "status": dataset.status.value}

    except CsvValidationError as exc:
        db.rollback()
        _mark_failed(db, dataset_id, import_job_id, f"[{stage}] {exc}")
        raise
    except Exception as exc:  # noqa: BLE001 - job failure must be recorded, then re-raised for logs
        db.rollback()
        _mark_failed(db, dataset_id, import_job_id, f"[{stage}] {exc}")
        logger.error("dataset.processing.failed", dataset_id=dataset_id, stage=stage, error=str(exc))
        raise
    finally:
        db.close()


def _mark_failed(db, dataset_id: str, import_job_id: str, message: str) -> None:
    dataset = db.get(Dataset, uuid.UUID(dataset_id))
    job = db.get(ImportJob, uuid.UUID(import_job_id))
    if dataset:
        dataset.status = DatasetStatus.FAILED
    if job:
        job.status = ImportJobStatus.FAILED
        job.error_message = message[:2000]
        job.completed_at = datetime.now(timezone.utc)
    db.commit()
