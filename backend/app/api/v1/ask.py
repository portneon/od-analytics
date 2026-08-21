from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.orchestrator import ask_question
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import ok
from app.services.dataset_service import get_dataset_or_404

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/ask")
def ask(dataset_id: uuid.UUID, payload: AskRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    get_dataset_or_404(db, tenant_id=user.tenant_id, dataset_id=dataset_id)
    result = ask_question(db, tenant_id=user.tenant_id, dataset_id=dataset_id, question=payload.question)
    return ok(result)
