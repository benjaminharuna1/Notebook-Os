from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_db
from app.features.projects.schemas import Project, ProjectCreate, ProjectUpdate
from app.features.projects.service import ProjectService

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=Project)
def create_project(
    req: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return ProjectService(db).create_project(current_user["id"], req.name, req.description)


@router.get("/projects")
def list_projects(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return ProjectService(db).list_projects(current_user["id"])


@router.get("/projects/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return ProjectService(db).get_project(project_id, current_user["id"])


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(
    project_id: str,
    req: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return ProjectService(db).update_project(
        project_id, current_user["id"], name=req.name, description=req.description
    )


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    return ProjectService(db).delete_project(project_id, current_user["id"])
