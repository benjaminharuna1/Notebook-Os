from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.features.models.schemas import DownloadModelRequest, SwitchModelRequest
from app.features.models.service import ModelService
from app.features.models import downloads as downloads_service

router = APIRouter(tags=["models"])


@router.get("/models")
async def list_models(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return await run_in_threadpool(service.list_models, current_user["id"])


@router.post("/models/switch")
async def switch_model(
    req: SwitchModelRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return await run_in_threadpool(service.switch_model, current_user["id"], req.model_id)


@router.get("/models/ollama/available")
async def list_ollama_models():
    service = ModelService(None)
    return await run_in_threadpool(service.list_ollama_available)


@router.get("/models/catalog")
async def get_catalog(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return await run_in_threadpool(service.get_catalog, current_user["id"])


@router.post("/models/hf/download")
async def download_hf_model(
    req: DownloadModelRequest,
    current_user: dict = Depends(get_current_user),
):
    return await run_in_threadpool(downloads_service.start_download, req.key)


@router.get("/models/hf/downloads")
async def list_hf_downloads(
    current_user: dict = Depends(get_current_user),
):
    return await run_in_threadpool(downloads_service.get_downloads)


@router.get("/local/status")
async def local_status(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return await run_in_threadpool(service.get_local_status, current_user["id"])
