import logging
import re
from pathlib import Path

from app.core.config import settings
from app.core.database import get_chroma_client, get_sqlite_connection
from app.core.exceptions import AppException
from app.features.embedding.providers.factory import resolve_collection_name
from app.features.embedding.service import EmbeddingService
from app.features.ingestion.extractors.pdf import PDFExtractor
from app.features.ingestion.jobs import job_manager
from app.features.ingestion.schemas import IngestionResponse, IngestionStatus
from app.features.processing.service import ProcessingService
from app.shared.file_utils import ensure_dir
from app.shared.id_utils import generate_id

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {"pdf"}
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
PDF_MAGIC = b"%PDF"

# Statuses a job can live in while the pipeline may be poked.
_ACTIVE_STATUSES = {"queued", "processing"}
_REPROCESSABLE_STATUSES = {"indexed", "failed"}


def _sanitize_filename(name: str) -> str:
    """Strip control characters, HTML, and path-unsafe glyphs from filenames."""
    name = re.sub(r"<[^>]+>", "", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\.{2,}", ".", name)
    name = name.strip(". ")
    return name or "upload.pdf"


class IngestionService:
    def __init__(self, db, settings_dict: dict | None = None):
        self.db = db
        self.settings_dict = settings_dict or {}
        self.extractors = {"pdf": PDFExtractor()}

    async def ingest(self, file, user_id: str, project_id: str | None = None) -> IngestionResponse:
        """Validate + persist the file, then queue it for background processing."""
        content = await file.read()

        if len(content) > MAX_SIZE:
            raise AppException(
                f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
                status_code=413,
            )

        if len(content) == 0:
            raise AppException("File is empty", status_code=400)

        original_name = Path(file.filename or "upload.pdf").name
        ext = original_name.rsplit(".", 1)[-1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise AppException(
                f"Unsupported file type: .{ext}. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                status_code=400,
            )

        # Verify PDF magic bytes — catches non-PDF files disguised with .pdf extension
        if not content[:4].startswith(PDF_MAGIC):
            raise AppException(
                "File does not appear to be a valid PDF (missing %PDF header)",
                status_code=400,
            )

        project_id = self._require_project(user_id, project_id)

        doc_id = generate_id()
        if project_id:
            upload_dir = ensure_dir(Path(settings.UPLOAD_DIR) / "projects" / project_id)
        else:
            upload_dir = ensure_dir(settings.UPLOAD_DIR)
        # Stored name is fully server-controlled to prevent path traversal
        stored_name = f"{doc_id}.{ext}"
        file_path = str(upload_dir / stored_name)
        with open(file_path, "wb") as f:
            f.write(content)

        safe_name = _sanitize_filename(original_name)

        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO documents (id, user_id, project_id, title, filename, file_path, file_type, file_size, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued')""",
            (doc_id, user_id, project_id, safe_name, safe_name, file_path, ext, len(content)),
        )
        self.db.commit()

        # Processing happens in the background; the response returns immediately.
        job_manager.submit(
            doc_id, self.run_pipeline, doc_id, user_id, self.settings_dict
        )

        return IngestionResponse(document_id=doc_id, status="queued", estimated_time=0)

    def run_pipeline(self, doc_id: str, user_id: str, settings_dict: dict) -> None:
        """Full extract → chunk → embed pipeline, executed in a worker thread.

        Uses its own DB connection so it never shares a request-bound one.
        Cooperatively pauses between work units via the job manager.
        """
        conn = get_sqlite_connection()
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ? AND user_id = ?",
                (doc_id, user_id),
            ).fetchone()
            if not row:
                return

            # If the user paused before the thread got going, respect that now.
            job_manager.checkpoint(doc_id)
            self._set_status(conn, doc_id, "processing")

            extractor = self.extractors.get(row["file_type"])
            if extractor is None:
                raise AppException(f"Unsupported file type: {row['file_type']}")
            extracted = extractor.extract(row["file_path"])
            job_manager.checkpoint(doc_id)

            chunks = ProcessingService(settings_dict).process(extracted.text, doc_id, extracted.pages)
            job_manager.checkpoint(doc_id)

            conn.execute(
                "UPDATE documents SET title = ?, page_count = ? WHERE id = ?",
                (extracted.title or row["filename"], extracted.page_count, doc_id),
            )
            conn.commit()

            # Drop stale vectors from any earlier run/failed attempt for this doc.
            self._delete_vectors(doc_id, settings_dict)
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            conn.commit()

            embedding = EmbeddingService(settings_dict)
            batch_size = settings.EMBED_BATCH_SIZE
            job_manager.set_progress(doc_id, len(chunks), 0)
            for start in range(0, len(chunks), batch_size):
                job_manager.checkpoint(doc_id)
                batch = chunks[start : start + batch_size]
                embedding.embed_chunks(
                    batch,
                    doc_id,
                    user_id,
                    project_id=row["project_id"],
                    title=extracted.title or row["filename"],
                )
                job_manager.set_progress(doc_id, len(chunks), start + len(batch))

            conn.execute(
                "UPDATE documents SET status = 'indexed', indexed_at = datetime('now'), error = NULL WHERE id = ?",
                (doc_id,),
            )
            conn.commit()

            # Keep the literature map in sync: every newly indexed paper
            # triggers a background rebuild for its project.
            self._maybe_build_literature(user_id, row["project_id"])
        except Exception as exc:
            message = getattr(exc, "detail", None) or str(exc)
            logger.exception("ingestion pipeline failed for %s", doc_id)
            try:
                conn.execute(
                    "UPDATE documents SET status = 'failed', error = ? WHERE id = ?",
                    (message, doc_id),
                )
                conn.commit()
            except Exception:
                logger.exception("could not persist failed status for %s", doc_id)
        finally:
            conn.close()

    def pause(self, document_id: str, user_id: str) -> dict:
        self._require_document(document_id, user_id)
        status = self._status(document_id, user_id)
        if status not in _ACTIVE_STATUSES:
            raise AppException(
                f"Document is '{status}'; only running jobs can be paused",
                status_code=409,
            )
        if not job_manager.pause(document_id):
            raise AppException("No active processing job", status_code=409)
        self._set_status(self.db, document_id, "paused")
        return {"success": True, "status": "paused"}

    def resume(self, document_id: str, user_id: str) -> dict:
        self._require_document(document_id, user_id)
        if self._status(document_id, user_id) != "paused":
            raise AppException("Document is not paused", status_code=409)
        if not job_manager.resume(document_id):
            raise AppException("No paused processing job", status_code=409)
        self._set_status(self.db, document_id, "processing")
        return {"success": True, "status": "processing"}

    def reprocess(self, document_id: str, user_id: str, settings_dict: dict | None = None) -> dict:
        self._require_document(document_id, user_id)
        if self._status(document_id, user_id) not in _REPROCESSABLE_STATUSES:
            raise AppException(
                "Only finished or failed documents can be reprocessed",
                status_code=409,
            )
        conn = self.db
        conn.execute(
            "UPDATE documents SET status = 'queued', indexed_at = NULL, error = NULL WHERE id = ?",
            (document_id,),
        )
        conn.commit()
        job_manager.submit(
            document_id, self.run_pipeline, document_id, user_id, settings_dict or self.settings_dict
        )
        return {"success": True, "status": "queued"}

    async def get_status(self, document_id: str, user_id: str) -> IngestionStatus:
        self._require_document(document_id, user_id)
        status = self._status(document_id, user_id)
        progress = self._compute_progress(document_id, status)
        return IngestionStatus(
            document_id=document_id,
            status=status,
            progress=progress,
            chunks_created=0,
            error=self._error(document_id, user_id),
        )

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _maybe_build_literature(user_id: str, project_id: str | None) -> None:
        """Kicks off a background literature map rebuild after a paper indexes.

        Local imports avoid an import cycle; failures are logged and never fail
        the ingestion job itself.
        """
        if not project_id:
            return
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
            logger.exception("literature auto-build failed to start for project %s", project_id)

    def _require_project(self, user_id: str, project_id: str | None) -> str | None:
        if not project_id:
            return None
        row = self.db.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if not row:
            raise AppException("Project not found", status_code=404)
        return project_id

    @staticmethod
    def _set_status(conn, document_id: str, status: str) -> None:
        conn.execute("UPDATE documents SET status = ? WHERE id = ?", (status, document_id))
        conn.commit()

    def _require_document(self, document_id: str, user_id: str) -> None:
        if not self._status(document_id, user_id):
            raise AppException("Document not found", status_code=404)

    def _status(self, document_id: str, user_id: str) -> str | None:
        row = self.db.execute(
            "SELECT status FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        return row["status"] if row else None

    def _error(self, document_id: str, user_id: str) -> str | None:
        row = self.db.execute(
            "SELECT error FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        return row["error"] if row else None

    def _compute_progress(self, document_id: str, status: str) -> int:
        if status == "indexed":
            return 100
        if status in _ACTIVE_STATUSES or status == "paused":
            progress = job_manager.progress(document_id)
            if progress and progress[1]:
                return min(99, int(progress[0] / progress[1] * 100))
        return 0

    def _delete_vectors(self, document_id: str, settings_dict: dict) -> None:
        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(
            name=resolve_collection_name(settings_dict)
        )
        stale = collection.get(where={"document_id": document_id}, include=[])
        if stale.get("ids"):
            collection.delete(ids=stale["ids"])
