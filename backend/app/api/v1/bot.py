"""Endpoint for external bot/automation integrations (e.g. a Zoho Cliq bot)
that hand over a CSV and want a finished report back in one round trip,
rather than driving the upload -> poll-status -> fetch-report flow the web
app itself uses. Runs the exact same pipeline as a normal upload
(`process_dataset_task`), just awaited inline instead of backgrounded, so
the response only comes back once the dataset is fully processed.

Unauthenticated access to every other endpoint is fine today because the
app only runs on a private network -- this one is meant to be reachable
from the public internet (Cliq's Deluge runtime calls it from Zoho's
cloud), so it's gated on a shared-secret header instead.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ApiError
from app.schemas.common import ok
from app.services import dataset_service
from app.services.bot_summary import build_bot_summary
from app.workers.tasks import process_dataset_task
from fastapi import status

router = APIRouter(prefix="/bot", tags=["bot"])


def _require_bot_api_key(x_bot_api_key: str | None = Header(default=None, alias="X-Bot-Api-Key")) -> None:
    if not settings.BOT_API_KEY:
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "BOT_API_DISABLED", "BOT_API_KEY is not configured on this server")
    if x_bot_api_key != settings.BOT_API_KEY:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_API_KEY", "Missing or invalid X-Bot-Api-Key header")


@router.post("/analyze-csv", dependencies=[Depends(_require_bot_api_key)])
async def analyze_csv(
    file: UploadFile = File(...),
    source: str = Form(default="zoho_mail"),
    is_whatsapp: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    content = await file.read()
    ds_name = (file.filename or "upload.csv").rsplit(".", 1)[0]

    dataset = dataset_service.create_dataset(
        db, file_name=file.filename or "upload.csv", content=content, source=source, is_whatsapp=is_whatsapp, dataset_name=ds_name
    )
    job = dataset_service.create_import_job(db, dataset_id=dataset.id)
    db.commit()

    # Synchronous on purpose: the caller (a Deluge bot script) wants the
    # finished summary in this same response, not a dataset_id to poll.
    # For very large files this can take tens of seconds -- if that starts
    # exceeding the caller's own timeout, this needs to move to the async
    # upload+poll flow (POST /datasets/upload + GET /datasets/{id}/status)
    # instead of staying a single blocking call.
    process_dataset_task(str(dataset.id), str(job.id))

    db.refresh(dataset)
    summary = build_bot_summary(db, dataset)
    return ok(summary)
