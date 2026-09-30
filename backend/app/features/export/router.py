"""Two export resources, each available as Word or Excel.

`dossier` is the project write-up: a summary of what is missing, the compiled
APA bibliography, and the per-paper notes. `references` is that bibliography on
its own, as RIS (for a reference manager), Word or Excel.

Exports contain documents only. Saved conversations and answers are deliberately
not part of any artifact.
"""

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.features.export import dossier, references, snapshot as snapshot_mod

router = APIRouter(tags=["export"])

ExportFormat = Literal["docx", "xlsx"]
# The reference list also comes as RIS, the format a reference manager imports.
ReferenceFormat = Literal["docx", "xlsx", "ris"]

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ris": "application/x-research-info-systems",
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
    format: ReferenceFormat = Query("ris"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    snapshot = await run_in_threadpool(_build_snapshot, db, current_user["id"], project_id)
    render = {
        "ris": references.render_ris,
        "docx": references.render_docx,
        "xlsx": references.render_xlsx,
    }[format]
    data = await run_in_threadpool(render, snapshot)
    return _respond(data, format, f"{_slug(snapshot.project_name)}-references")
