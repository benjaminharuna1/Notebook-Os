import json
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.core.database import get_sqlite_connection
from app.core.dependencies import get_current_user, get_db
from app.features.literature import jobs
from app.features.literature.llm_service import LiteratureLLMService
from app.features.literature.schemas import (
    LiteratureBuildJob,
    LiteratureCandidateApply,
    LiteratureClusterSummaryRequest,
    LiteratureEntry,
    LiteratureEntryUpdate,
    LiteratureMapResponse,
    LiteratureMetadataUpdate,
    LiteratureRegenerateRequest,
)
from app.features.literature.service import LiteratureService

router = APIRouter(tags=["literature"])


def _service_factory():
    return LiteratureService(get_sqlite_connection())


def _cluster_label(cluster_id: str) -> str:
    return f"Cluster {cluster_id[1:]}" if cluster_id.startswith("c") else cluster_id


@router.post("/projects/{project_id}/literature/build", response_model=LiteratureBuildJob)
async def build_literature_map(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    job_id = jobs.start_build(_service_factory, current_user["id"], project_id)
    return jobs.get_job(job_id)


@router.get("/projects/{project_id}/literature/jobs/{job_id}", response_model=LiteratureBuildJob)
async def get_literature_build_status(
    project_id: str,
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Build job not found")
    return job


@router.get("/projects/{project_id}/literature/map", response_model=LiteratureMapResponse)
async def get_literature_map(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    return service.get_map(current_user["id"], project_id)


@router.get("/projects/{project_id}/literature/entries", response_model=List[LiteratureEntry])
async def get_literature_entries(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    return service.entries(current_user["id"], project_id)


@router.get(
    "/projects/{project_id}/literature/entries/{paper_id}",
    response_model=LiteratureEntry,
)
async def get_literature_entry(
    project_id: str,
    paper_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    entry = service.get_entry(paper_id, current_user["id"])
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="No literature mapping yet for this paper",
        )
    return entry


@router.patch("/projects/{project_id}/literature/entries/{paper_id}", response_model=LiteratureEntry)
async def update_literature_entry(
    project_id: str,
    paper_id: str,
    req: LiteratureEntryUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    if service.get_entry(paper_id, current_user["id"]) is None:
        paper = next(
            (p for p in service.papers(current_user["id"], project_id) if p["id"] == paper_id),
            None,
        )
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found in this project")
        service.upsert_entry(paper_id, current_user["id"], project_id, {}, auto=True)
    fields = req.model_dump(exclude_unset=True)
    entry = service.upsert_entry(paper_id, current_user["id"], project_id, fields, auto=False)
    return entry


@router.post(
    "/projects/{project_id}/literature/entries/{paper_id}/regenerate",
    response_model=LiteratureEntry,
)
async def regenerate_literature_entry(
    project_id: str,
    paper_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureLLMService(db)
    try:
        entry = await service.summarize_paper(current_user["id"], project_id, paper_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if entry is None:
        raise HTTPException(status_code=404, detail="Paper not found in this project")
    return entry


@router.get("/projects/{project_id}/literature/entries/{paper_id}/metadata")
async def get_paper_metadata(
    project_id: str,
    paper_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    metadata = service.get_metadata(paper_id, current_user["id"], project_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found in this project")
    return metadata


@router.patch("/projects/{project_id}/literature/entries/{paper_id}/metadata")
async def update_paper_metadata(
    project_id: str,
    paper_id: str,
    req: LiteratureMetadataUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    metadata = service.update_metadata(
        paper_id, current_user["id"], project_id, req.model_dump(exclude_unset=True)
    )
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found in this project")
    return metadata


@router.post("/projects/{project_id}/literature/entries/{paper_id}/candidates/apply")
async def apply_literature_candidate(
    project_id: str,
    paper_id: str,
    req: LiteratureCandidateApply,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    metadata = service.apply_candidate(paper_id, current_user["id"], project_id, req.index)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper or candidate not found")
    return metadata


@router.post("/projects/{project_id}/literature/regenerate")
async def regenerate_literature_metadata(
    project_id: str,
    req: LiteratureRegenerateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    import asyncio

    service = LiteratureService(db)
    results = await asyncio.to_thread(
        service.regenerate_metadata,
        current_user["id"],
        project_id,
        req.paper_ids,
    )
    return {"processed": len(results), "results": results}


@router.get("/projects/{project_id}/literature/export")
async def export_literature_map(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureService(db)
    data = service.export_workbook(current_user["id"], project_id)

    row = db.execute(
        "SELECT name FROM projects WHERE id = ? AND user_id = ?",
        (project_id, current_user["id"]),
    ).fetchone()
    project_name = (row["name"] if row else "project") or "project"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", project_name).strip("-").lower() or "project"
    filename = f"literature-mapping-{slug}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/literature/references/export.docx")
async def export_literature_references(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    row = db.execute(
        "SELECT name FROM projects WHERE id = ? AND user_id = ?",
        (project_id, current_user["id"]),
    ).fetchone()
    project_name = (row["name"] if row else "project") or "project"

    service = LiteratureService(db)
    data = service.export_references_docx(current_user["id"], project_id, project_name)

    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", project_name).strip("-").lower() or "project"
    filename = f"{slug}-references.docx"
    return Response(
        content=data,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/projects/{project_id}/literature/clusters/summary")
async def summarize_literature_cluster(
    project_id: str,
    req: LiteratureClusterSummaryRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    service = LiteratureLLMService(db)

    async def generate():
        try:
            sources = service.cluster_sources(current_user["id"], req.project_id, req.cluster_id)
            if not sources:
                raise ValueError(f"No passages found for cluster {req.cluster_id} in this project")
            model = service.active_model(current_user["id"])
            if not model:
                raise ValueError("No active model configured — pick one in Settings")
            provider = service.model_service.get_provider(model, current_user["id"])
            system, prompt = service.cluster_prompt(_cluster_label(req.cluster_id), sources)
            async for chunk in provider.stream_chat(
                system, [{"role": "user", "content": prompt}]
            ):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            source_data = [
                {
                    "title": source["title"],
                    "page": source["page"],
                    "doc_id": source["document_id"],
                    "snippet": source["content"][:140],
                }
                for source in sources
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': source_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            yield f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
