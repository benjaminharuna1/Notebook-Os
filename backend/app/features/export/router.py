import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.features.export import dossier, snapshot as snapshot_mod, workbook

router = APIRouter(tags=["export"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name or "").strip("-").lower() or "project"


def _build_snapshot(db, user_id: str, project_id: str):
    snapshot = snapshot_mod.build(db, user_id, project_id)
    if not snapshot.papers:
        raise HTTPException(status_code=400, detail="This project has no papers to export yet.")
    return snapshot


def _attachment(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/projects/{project_id}/export/workbook")
async def export_workbook(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    snapshot = await run_in_threadpool(_build_snapshot, db, current_user["id"], project_id)
    data = await run_in_threadpool(workbook.render, snapshot)
    filename = f"literature-mapping-{_slug(snapshot.project_name)}.xlsx"
    return Response(content=data, media_type=XLSX_MEDIA, headers=_attachment(filename))


@router.get("/projects/{project_id}/export/dossier")
async def export_dossier(
    project_id: str,
    include_answers: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    snapshot = await run_in_threadpool(_build_snapshot, db, current_user["id"], project_id)
    data = await run_in_threadpool(dossier.render, snapshot, include_answers)
    filename = f"{_slug(snapshot.project_name)}-dossier.docx"
    return Response(content=data, media_type=DOCX_MEDIA, headers=_attachment(filename))
