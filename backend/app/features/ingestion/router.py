from fastapi import APIRouter, Depends, UploadFile, File

from app.core.dependencies import get_current_user, get_db
from app.features.ingestion.schemas import IngestionResponse, IngestionStatus
from app.features.ingestion.service import IngestionService

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/file", response_model=IngestionResponse)
async def ingest_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = IngestionService(db)
    return await service.ingest(file, current_user["id"])


@router.get("/ingest/status/{document_id}", response_model=IngestionStatus)
async def get_ingestion_status(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = IngestionService(db)
    return await service.get_status(document_id, current_user["id"])
