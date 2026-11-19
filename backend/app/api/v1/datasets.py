from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ok
from app.services import dataset_service
from app.workers.tasks import process_dataset_task

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _serialize(dataset) -> dict:
    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "source": dataset.source,
        "file_name": dataset.file_name,
        "row_count": dataset.row_count,
        "date_start": dataset.date_start.isoformat() if dataset.date_start else None,
        "date_end": dataset.date_end.isoformat() if dataset.date_end else None,
        "status": dataset.status.value,
        "schema_version": dataset.schema_version,
        "created_at": dataset.created_at.isoformat(),
        "updated_at": dataset.updated_at.isoformat(),
    }


@router.post("/upload")
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    name: str | None = Form(default=None),
    source: str = Form(default="zoho_mail"),
    is_whatsapp: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    upload_files: list[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file and file not in upload_files:
        upload_files.append(file)

    if not upload_files:
        raise HTTPException(status_code=400, detail="No file provided")

    results = []
    for f in upload_files:
        content = await f.read()
        ds_name = name if (len(upload_files) == 1 and name) else (f.filename or "upload.csv").rsplit(".", 1)[0]
        dataset = dataset_service.create_dataset(
            db, file_name=f.filename or "upload.csv", content=content, source=source, is_whatsapp=is_whatsapp, dataset_name=ds_name
        )
        job = dataset_service.create_import_job(db, dataset_id=dataset.id)
        db.commit()

        background_tasks.add_task(process_dataset_task, str(dataset.id), str(job.id))

        results.append({"dataset_id": str(dataset.id), "job_id": str(job.id), "status": "QUEUED"})

    if len(results) == 1:
        return ok(results[0])
    return ok({"datasets": results, "count": len(results)})


@router.post("/upload-multiple")
async def upload_multiple_datasets(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    source: str = Form(default="zoho_mail"),
    is_whatsapp: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    results = []
    for f in files:
        content = await f.read()
        ds_name = (f.filename or "upload.csv").rsplit(".", 1)[0]
        dataset = dataset_service.create_dataset(
            db, file_name=f.filename or "upload.csv", content=content, source=source, is_whatsapp=is_whatsapp, dataset_name=ds_name
        )
        job = dataset_service.create_import_job(db, dataset_id=dataset.id)
        db.commit()

        background_tasks.add_task(process_dataset_task, str(dataset.id), str(job.id))

        results.append({"dataset_id": str(dataset.id), "job_id": str(job.id), "status": "QUEUED"})

    return ok({"datasets": results, "count": len(results)})


@router.get("")
def list_datasets(db: Session = Depends(get_db)):
    datasets = dataset_service.list_datasets(db)
    return ok([_serialize(d) for d in datasets])


@router.get("/{dataset_id}")
def get_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    dataset = dataset_service.get_dataset_or_404(db, dataset_id=dataset_id)
    return ok(_serialize(dataset))


@router.get("/{dataset_id}/status")
def get_dataset_status(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    dataset = dataset_service.get_dataset_or_404(db, dataset_id=dataset_id)
    return ok({"dataset_id": str(dataset.id), "status": dataset.status.value, "row_count": dataset.row_count})


@router.get("/{dataset_id}/quality")
def get_dataset_quality(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    dataset = dataset_service.get_dataset_or_404(db, dataset_id=dataset_id)
    return ok(dataset.quality_report or {})


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    dataset_service.delete_dataset(db, dataset_id=dataset_id)
    return ok({"dataset_id": str(dataset_id), "deleted": True})
