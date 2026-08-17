from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppException
from app.features.documents.repository import DocumentRepository

_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class DocumentService:
    def __init__(self, db):
        self.repo = DocumentRepository(db)

    def list_documents(
        self,
        user_id: str,
        page: int,
        limit: int,
        search: str = "",
        file_type: str = "",
        project_id: str | None = None,
    ):
        return self.repo.list_documents(user_id, page, limit, search, file_type, project_id)

    def get_document(self, document_id: str, user_id: str):
        doc = self.repo.get_by_id(document_id, user_id)
        if not doc:
            raise AppException("Document not found", status_code=404)

        cursor = self.repo.db.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM chunks WHERE document_id = ?", (document_id,))
        chunk_count = cursor.fetchone()["count"]

        return {**dict(doc), "chunk_count": chunk_count}

    def get_document_file(self, document_id: str, user_id: str, project_id: str):
        row = self.repo.db.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ? AND project_id = ?",
            (document_id, user_id, project_id),
        ).fetchone()
        if not row:
            raise AppException("Document not found", status_code=404)

        file_path = row["file_path"]
        if not file_path:
            raise AppException("Document has no stored file", status_code=404)

        resolved = Path(file_path).resolve()
        try:
            resolved.relative_to(Path(settings.UPLOAD_DIR).resolve())
        except ValueError:
            raise AppException("Document file is not accessible", status_code=403)
        if not resolved.is_file():
            raise AppException("Document file is missing on disk", status_code=404)

        media_type = _MEDIA_TYPES.get(resolved.suffix.lower(), "application/octet-stream")
        return resolved, media_type

    def delete_document(self, document_id: str, user_id: str, collection_name: str = "documents"):
        project_id = None
        row = self.repo.db.execute(
            "SELECT project_id FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        if row:
            project_id = row["project_id"]

        self.repo.delete(document_id, user_id)
        chroma = self.repo.get_chroma()
        collection = chroma.get_or_create_collection(name=collection_name)
        collection.delete(where={"document_id": document_id, "user_id": user_id})

        if project_id:
            self._prune_checkpoints(user_id, project_id, [document_id])
            self._rebuild_literature(user_id, project_id)
        return {"success": True}

    def delete_documents(
        self,
        document_ids: list[str],
        user_id: str,
        project_id: str,
        collection_name: str = "documents",
    ):
        """Deletes several documents belonging to a project in one pass.

        Only documents owned by ``user_id`` inside ``project_id`` are touched;
        unknown/foreign ids are ignored. Chroma vectors are purged per document
        and the literature map is rebuilt once at the end.
        """
        if not document_ids:
            return {"success": True, "deleted": 0}

        rows = self.repo.db.execute(
            """SELECT id FROM documents
               WHERE user_id = ? AND project_id = ? AND id IN (%s)"""
            % ",".join("?" * len(document_ids)),
            (user_id, project_id, *document_ids),
        ).fetchall()
        owned = [row["id"] for row in rows]
        if not owned:
            return {"success": True, "deleted": 0}

        chroma = self.repo.get_chroma()
        collection = chroma.get_or_create_collection(name=collection_name)
        for document_id in owned:
            self.repo.delete(document_id, user_id)
            collection.delete(where={"document_id": document_id, "user_id": user_id})

        self._prune_checkpoints(user_id, project_id, owned)
        self._rebuild_literature(user_id, project_id)
        return {"success": True, "deleted": len(owned)}

    @staticmethod
    def _prune_checkpoints(user_id: str, project_id: str, paper_ids: list[str]) -> None:
        """Remove deleted papers from stored literature checkpoints so old
        graph snapshots no longer reference them."""
        try:
            import json as _json
            from app.core.database import get_sqlite_connection

            db = get_sqlite_connection()
            rows = db.execute(
                """SELECT id, graph_json FROM graph_history
                   WHERE user_id = ? AND project_id = ? AND map_type = 'literature'""",
                (user_id, project_id),
            ).fetchall()
            pid_set = set(paper_ids)
            changed = False
            for row in rows:
                try:
                    data = _json.loads(row["graph_json"])
                except (TypeError, ValueError):
                    continue
                if not isinstance(data, dict):
                    continue
                nodes = data.get("nodes") or []
                edges = data.get("edges") or []
                kept_nodes = [
                    n for n in nodes
                    if n.get("id") not in pid_set
                    and (n.get("meta") or {}).get("doc_id") not in pid_set
                ]
                if len(kept_nodes) == len(nodes):
                    continue
                kept_ids = {n["id"] for n in kept_nodes}
                kept_edges = [
                    e for e in edges
                    if e.get("source") in kept_ids and e.get("target") in kept_ids
                ]
                data["nodes"] = kept_nodes
                data["edges"] = kept_edges
                db.execute(
                    "UPDATE graph_history SET graph_json = ? WHERE id = ?",
                    (_json.dumps(data), row["id"]),
                )
                changed = True
            if changed:
                db.commit()
        except Exception:
            pass

    @staticmethod
    def _rebuild_literature(user_id: str, project_id: str) -> None:
        """Rebuilds the project's literature map after a paper is removed so
        its node, edges and checkpoint entries disappear."""
        try:
            from app.core.database import get_sqlite_connection
            from app.features.literature.jobs import start_build
            from app.features.literature.service import LiteratureService

            start_build(
                lambda: LiteratureService(get_sqlite_connection()),
                user_id,
                project_id,
            )
        except Exception:
            pass
