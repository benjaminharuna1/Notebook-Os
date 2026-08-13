from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_db
from app.features.skills.schemas import (
    SkillEnableRequest,
    SkillInstallRequest,
    SkillManifest,
)
from app.features.skills.service import SkillsService

router = APIRouter(tags=["skills"])


@router.get("/skills")
def list_installed(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return {"skills": SkillsService(db).list_installed(current_user["id"])}


@router.get("/skills/catalog")
def list_catalog(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return {"catalog": SkillsService(db).list_catalog(current_user["id"])}


@router.post("/skills/install")
def install_skill(
    req: SkillInstallRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return SkillsService(db).install(current_user["id"], req.skill_id)


@router.post("/skills/{skill_id}/enable")
def enable_skill(
    skill_id: str,
    req: SkillEnableRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return SkillsService(db).set_enabled(current_user["id"], skill_id, req.enabled)


@router.delete("/skills/{skill_id}")
def uninstall_skill(
    skill_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return SkillsService(db).uninstall(current_user["id"], skill_id)


@router.post("/skills/import")
def import_skill(
    manifest: SkillManifest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return SkillsService(db).import_skill(current_user["id"], manifest)
