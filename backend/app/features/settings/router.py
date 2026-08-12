from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_db
from app.features.settings.schemas import SettingsUpdate, SettingsResponse
from app.features.settings.service import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = SettingsService(db)
    return service.get_settings(current_user["id"])


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = SettingsService(db)
    return service.update_settings(current_user["id"], req)
