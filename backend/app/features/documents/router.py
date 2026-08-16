from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.core.dependencies import get_current_user, get_db
from app.features.documents.schemas import DocumentBatchDelete
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
    project_id: str = Query(""),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db)
    return service.list_documents(
        current_user["id"],
        page=page,
        limit=limit,
        search=search,
        file_type=file_type,
        project_id=project_id or None,
    )


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


@router.post("/projects/{project_id}/documents/batch/delete")
async def delete_documents_batch(
    project_id: str,
    req: DocumentBatchDelete,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    collection_name = resolve_collection_name(user_settings)
    service = DocumentService(db)
    return service.delete_documents(
        req.document_ids,
        current_user["id"],
        project_id,
        collection_name=collection_name,
    )


@router.get("/projects/{project_id}/documents/{document_id}/file")
async def get_document_file(
    project_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db)
    path, media_type = service.get_document_file(document_id, current_user["id"], project_id)
    return FileResponse(path=path, media_type=media_type)
