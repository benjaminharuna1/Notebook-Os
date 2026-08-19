from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_db

router = APIRouter(tags=["FEATURE_NAME"])


@router.get("/FEATURE_NAME/example")
async def example_endpoint(db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    return {"status": "ok"}
