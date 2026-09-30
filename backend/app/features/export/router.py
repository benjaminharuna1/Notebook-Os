"""Three export resources, each rendered from a read-only snapshot.

`dossier` is the project write-up: a summary of what is missing, the compiled
APA bibliography, and the per-paper notes. `references` is that bibliography on
its own. `conversation` is one saved chat session — the questions, the answers,
and the sources each answer rested on.

The project resources contain documents only; a saved conversation is exported
through its own resource rather than folded into an artifact.
"""

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.features.export import conversation, dossier, references, snapshot as snapshot_mod

router = APIRouter(tags=["export"])

ExportFormat = Literal["docx", "xlsx"]
ConversationFormat = Literal["docx"]

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name or "").strip("-").lower() or "project"


def _build_snapshot(db, user_id: str, project_id: str):
    snapshot = snapshot_mod.build(db, user_id, project_id)
    if not snapshot.papers:
        raise HTTPException(status_code=400, detail="This project has no papers to export yet.")
    return snapshot


def _respond(data: bytes, export_format: str, stem: str) -> Response:
    return Response(
        content=data,
        media_type=MEDIA_TYPES[export_format],
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.{export_format}"'
        },
    )


@router.get("/projects/{project_id}/export/dossier")
async def export_dossier(
    project_id: str,
    format: ExportFormat = Query("docx"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    snapshot = await run_in_threadpool(_build_snapshot, db, current_user["id"], project_id)
    render = dossier.render_docx if format == "docx" else dossier.render_xlsx
    data = await run_in_threadpool(render, snapshot)
    return _respond(data, format, f"{_slug(snapshot.project_name)}-dossier")


@router.get("/projects/{project_id}/export/references")
async def export_references(
    project_id: str,
    format: ExportFormat = Query("docx"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    snapshot = await run_in_threadpool(_build_snapshot, db, current_user["id"], project_id)
    render = references.render_docx if format == "docx" else references.render_xlsx
    data = await run_in_threadpool(render, snapshot)
    return _respond(data, format, f"{_slug(snapshot.project_name)}-references")


@router.get("/projects/{project_id}/export/conversation/{session_id}")
async def export_conversation(
    project_id: str,
    session_id: str,
    format: ConversationFormat = Query("docx"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    report = await run_in_threadpool(
        conversation.build, db, current_user["id"], session_id
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if not report.messages:
        raise HTTPException(status_code=400, detail="This conversation is empty.")
    data = await run_in_threadpool(conversation.render_docx, report)
    return _respond(data, format, f"{_slug(report.title)}-conversation")
