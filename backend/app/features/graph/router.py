from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_db
from app.features.graph.schemas import GraphResponse
from app.features.graph.service import GraphService

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    document_ids: str = Query(""),
    depth: int = Query(2),
    project_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    ids = document_ids.split(",") if document_ids else []
    return service.build_graph(
        user_id=current_user["id"],
        document_ids=ids,
        depth=depth,
        project_id=project_id,
    )
