from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.features.graph.service import GraphService

router = APIRouter(tags=["graph"], dependencies=[Depends(get_current_user)])


@router.get("/graph")
async def get_graph(
    document_ids: str = Query(""),
    depth: int = Query(2),
    project_id: str | None = Query(None),
):
    service = GraphService()
    ids = document_ids.split(",") if document_ids else []
    return service.build_graph(document_ids=ids, depth=depth, project_id=project_id)
