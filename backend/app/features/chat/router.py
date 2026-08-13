from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_db
from app.features.chat.schemas import ChatRequest
from app.features.chat.service import ChatService
from app.features.settings.service import SettingsService

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    settings_service = SettingsService(db)
    user_settings = settings_service.get_settings(current_user["id"]).settings
    service = ChatService(db, settings_dict=user_settings)
    return await service.stream_chat(req, current_user["id"])


@router.get("/chat/sessions")
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ChatService(db)
    return service.list_sessions(current_user["id"])


@router.get("/chat/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ChatService(db)
    return service.get_session(session_id, current_user["id"])


@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ChatService(db)
    return service.delete_session(session_id, current_user["id"])
