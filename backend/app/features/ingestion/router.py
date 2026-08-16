from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import get_current_user, get_db
from app.features.ingestion.schemas import (
    IngestionBatchReprocess,
    IngestionResponse,
    IngestionStatus,
)
from app.features.ingestion.service import IngestionService
from app.features.settings.service import SettingsService

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/reprocess")
async def reprocess_documents(
    req: IngestionBatchReprocess,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    service = IngestionService(db, settings_dict=user_settings)
    processed = 0
    errors = []
    for document_id in req.document_ids:
        try:
            service.reprocess(document_id, current_user["id"], settings_dict=user_settings)
            processed += 1
        except Exception as exc:
            errors.append({"document_id": document_id, "error": str(getattr(exc, "detail", exc))})
    return {"success": True, "processed": processed, "errors": errors}


@router.post("/ingest/file", response_model=IngestionResponse)
async def ingest_file(
    file: UploadFile = File(...),
    project_id: str = Form(""),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    service = IngestionService(db, settings_dict=user_settings)
    return await service.ingest(file, current_user["id"], project_id=project_id or None)


@router.get("/ingest/status/{document_id}", response_model=IngestionStatus)
async def get_ingestion_status(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = IngestionService(db)
    return await service.get_status(document_id, current_user["id"])


@router.post("/ingest/{document_id}/pause")
async def pause_ingestion(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = IngestionService(db)
    return service.pause(document_id, current_user["id"])


@router.post("/ingest/{document_id}/resume")
async def resume_ingestion(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = IngestionService(db)
    return service.resume(document_id, current_user["id"])


@router.post("/ingest/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    service = IngestionService(db, settings_dict=user_settings)
    return service.reprocess(document_id, current_user["id"])
