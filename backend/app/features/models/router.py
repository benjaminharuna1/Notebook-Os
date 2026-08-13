from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.features.models.schemas import SwitchModelRequest
from app.features.models.service import ModelService

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


@router.get("/local/status")
async def local_status(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return await run_in_threadpool(service.get_local_status, current_user["id"])
