from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_db
from app.features.documents.service import DocumentService
from app.features.embedding.service import resolve_collection_name
from app.features.settings.service import SettingsService

router = APIRouter(tags=["documents"])


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    file_type: str = Query(""),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db)
    return service.list_documents(current_user["id"], page=page, limit=limit, search=search, file_type=file_type)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db)
    return service.get_document(document_id, current_user["id"])


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    collection_name = resolve_collection_name(user_settings)
    service = DocumentService(db)
    return service.delete_document(document_id, current_user["id"], collection_name=collection_name)
