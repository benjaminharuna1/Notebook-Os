from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user
from app.features.actions import registry as actions

router = APIRouter(tags=["actions"])


@router.get("/actions")
async def list_actions(current_user: dict = Depends(get_current_user)):
    """Lists the current user's actions (in-flight and recent), newest first."""
    return {"actions": actions.list_for_user(current_user["id"])}


@router.post("/actions/{action_id}/pause")
async def pause_action(action_id: str, current_user: dict = Depends(get_current_user)):
    action = actions.pause(action_id, current_user["id"])
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found or cannot be paused")
    return action


@router.post("/actions/{action_id}/resume")
async def resume_action(action_id: str, current_user: dict = Depends(get_current_user)):
    action = actions.resume(action_id, current_user["id"])
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found or cannot be resumed")
    return action
