from fastapi import APIRouter, Depends

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
    return service.list_models(current_user["id"])


@router.post("/models/switch")
async def switch_model(
    req: SwitchModelRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelService(db)
    return service.switch_model(current_user["id"], req.model_id)


@router.get("/models/ollama/available")
async def list_ollama_models():
    service = ModelService(None)
    return service.list_ollama_available()
