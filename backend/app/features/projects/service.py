from pathlib import Path

from app.core.database import get_chroma_client
from app.core.exceptions import AppException
from app.features.projects.repository import ProjectRepository, new_project_id


class ProjectService:
    def __init__(self, db):
        self.repo = ProjectRepository(db)

    def create_project(self, user_id: str, name: str, description: str = ""):
        name = (name or "").strip()
        if not name:
            raise AppException("Project name is required", status_code=422)

        project_id = new_project_id()
        self.repo.create(project_id, user_id, name, description)
        return self.get_project(project_id, user_id)

    def list_projects(self, user_id: str):
        return {"projects": self.repo.list(user_id)}

    def get_project(self, project_id: str, user_id: str):
        row = self.repo.get(project_id, user_id)
        if not row:
            raise AppException("Project not found", status_code=404)
        return dict(row)

    def update_project(self, project_id: str, user_id: str, name=None, description=None):
        self.get_project(project_id, user_id)
        self.repo.update(project_id, user_id, name=name, description=description)
        return self.get_project(project_id, user_id)

    def delete_project(self, project_id: str, user_id: str):
        self.get_project(project_id, user_id)

        documents = self.repo.list_documents(project_id)
        doc_ids = [d["id"] for d in documents]

        # Remove vectors for every collection (embedding models may have changed).
        chroma = get_chroma_client()
        for collection in chroma.list_collections():
            stale = collection.get(where={"document_id": {"$in": doc_ids}}, include=[])
            if stale.get("ids"):
                collection.delete(ids=stale["ids"])

        # Remove the stored files.
        for doc in documents:
            path = Path(doc["file_path"])
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

        self.repo.delete(project_id, user_id)
        return {"success": True}
