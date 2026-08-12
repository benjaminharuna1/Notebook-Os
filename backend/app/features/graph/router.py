from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_auth
from app.features.graph.service import GraphService

router = APIRouter(tags=["graph"], dependencies=[Depends(require_auth)])


@router.get("/graph")
async def get_graph(document_ids: str = Query(""), depth: int = Query(2)):
    service = GraphService()
    ids = document_ids.split(",") if document_ids else []
    return service.build_graph(document_ids=ids, depth=depth)
