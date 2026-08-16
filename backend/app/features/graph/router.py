import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.database import get_sqlite_connection
from app.core.dependencies import get_current_user, get_db
from app.features.graph import jobs
from app.features.graph.llm_service import GraphLLMService
from app.features.graph.schemas import (
    DocumentThemesList,
    GenerationJob,
    GraphCheckpoint,
    GraphCheckpointDetail,
    GraphCheckpointList,
    GraphCheckpointUpdate,
    GraphGenerateRequest,
    GraphResponse,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphSummaryRequest,
    TrackedConcept,
    TrackedConceptCreate,
    TrackedConceptList,
)
from app.features.graph.service import GraphService
from app.features.graph.tracked_service import TrackedConceptsService

router = APIRouter(tags=["graph"])


def _service_factory():
    return GraphService(get_sqlite_connection())


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    document_ids: str = Query(""),
    depth: int = Query(2),
    project_id: str | None = Query(None),
    force: bool = Query(False),
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
        force=force,
    )


@router.post("/graph/generate", response_model=GenerationJob)
async def start_generation(
    req: GraphGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    job_id = jobs.start_generation(
        _service_factory,
        current_user["id"],
        req.project_id,
        req.document_ids,
        req.depth,
        req.force,
    )
    return jobs.get_job(job_id)


@router.get("/graph/history", response_model=GraphCheckpointList)
async def list_graph_history(
    project_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    return GraphCheckpointList(checkpoints=service.list_history(current_user["id"], project_id))


@router.get("/graph/history/{checkpoint_id}", response_model=GraphCheckpointDetail)
async def get_graph_checkpoint(
    checkpoint_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    checkpoint = service.get_checkpoint(current_user["id"], checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.patch("/graph/history/{checkpoint_id}", response_model=GraphCheckpoint)
async def update_graph_checkpoint(
    checkpoint_id: str,
    req: GraphCheckpointUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    updated = service.set_favourite(current_user["id"], checkpoint_id, req.is_favourite)
    if updated is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return updated


@router.delete("/graph/history/{checkpoint_id}", response_model=dict)
async def delete_graph_checkpoint(
    checkpoint_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    if not service.delete_checkpoint(current_user["id"], checkpoint_id):
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return {"success": True}


@router.post("/graph/search", response_model=GraphSearchResponse)
async def search_graph_concepts(
    req: GraphSearchRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphLLMService(db)
    return await service.refine_query(current_user["id"], req.project_id, req.query)


@router.post("/graph/concepts/summary")
async def summarize_graph_concept(
    req: GraphSummaryRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphLLMService(db)

    async def generate():
        try:
            sources = service.summary_sources(
                current_user["id"], req.project_id, req.label.strip()
            )
            if not sources:
                raise ValueError(f'No passages found for "{req.label}" in this project')
            model = service.active_model(current_user["id"])
            if not model:
                raise ValueError("No active model configured — pick one in Settings")
            provider = service.model_service.get_provider(model, current_user["id"])
            system, prompt = service.summary_prompt(req.label.strip(), sources)
            async for chunk in provider.stream_chat(
                system, [{"role": "user", "content": prompt}]
            ):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            source_data = [
                {
                    "title": s["title"],
                    "page": s["page"],
                    "doc_id": s["document_id"],
                    "snippet": s["content"][:140],
                }
                for s in sources
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': source_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            yield f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/graph/themes", response_model=DocumentThemesList)
async def get_document_themes(
    project_id: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = GraphService(db)
    return DocumentThemesList(documents=service.detect_themes(current_user["id"], project_id, limit))


@router.get("/graph/concepts/tracked", response_model=TrackedConceptList)
async def list_tracked_concepts(
    project_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = TrackedConceptsService(db)
    return TrackedConceptList(concepts=service.list(current_user["id"], project_id))


@router.post("/graph/concepts/tracked", response_model=TrackedConcept)
async def add_tracked_concept(
    req: TrackedConceptCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = TrackedConceptsService(db)
    try:
        return service.add(current_user["id"], req.project_id, req.concept)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/graph/concepts/tracked/{concept_id}", response_model=dict)
async def remove_tracked_concept(
    concept_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = TrackedConceptsService(db)
    if not service.remove(current_user["id"], concept_id):
        raise HTTPException(status_code=404, detail="Tracked concept not found")
    return {"success": True}
