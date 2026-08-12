from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.features.search.schemas import SearchRequest, SearchResponse
from app.features.search.service import SearchService

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    service = SearchService()
    return await service.search(req, current_user["id"])
