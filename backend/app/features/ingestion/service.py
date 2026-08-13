from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.exceptions import AppException
from app.features.ingestion.extractors.pdf import PDFExtractor
from app.features.ingestion.schemas import IngestionResponse, IngestionStatus
from app.features.processing.service import ProcessingService
from app.features.embedding.service import EmbeddingService
from app.shared.file_utils import ensure_dir
from app.shared.id_utils import generate_id

SUPPORTED_EXTENSIONS = {"pdf"}
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class IngestionService:
    def __init__(self, db, settings_dict: dict | None = None):
        self.db = db
        self.settings_dict = settings_dict or {}
        self.extractors = {"pdf": PDFExtractor()}

    async def ingest(self, file, user_id: str) -> IngestionResponse:
        content = await file.read()

        if len(content) > MAX_SIZE:
            raise AppException(
                f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
                status_code=413,
            )

        original_name = Path(file.filename or "upload.pdf").name
        ext = original_name.rsplit(".", 1)[-1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise AppException(
                f"Unsupported file type: .{ext}. Supported types: {', '.join(SUPPORTED_EXTENSIONS)}",
                status_code=400,
            )

        doc_id = generate_id()
        upload_dir = ensure_dir(settings.UPLOAD_DIR)
        # Stored name is fully server-controlled to prevent path traversal
        stored_name = f"{doc_id}.{ext}"
        file_path = str(upload_dir / stored_name)
        with open(file_path, "wb") as f:
            f.write(content)

        try:
            extracted = await run_in_threadpool(self.extractors[ext].extract, file_path)
        except Exception as exc:
            Path(file_path).unlink(missing_ok=True)
            raise AppException(f"Could not read file: {exc}", status_code=400) from exc

        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO documents (id, user_id, title, filename, file_path, file_type, file_size, page_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, user_id, extracted.title or original_name, original_name, file_path, ext, len(content), extracted.page_count, "processing"),
        )
        self.db.commit()

        try:
            processing = ProcessingService(self.settings_dict)
            chunks = await run_in_threadpool(processing.process, extracted.text, doc_id)

            embedding = EmbeddingService(self.settings_dict)
            await run_in_threadpool(embedding.embed_chunks, chunks, doc_id, user_id)
        except Exception as exc:
            raise AppException(f"Indexing failed: {exc}", status_code=500) from exc

        cursor.execute("UPDATE documents SET status = 'indexed', indexed_at = datetime('now') WHERE id = ?", (doc_id,))
        self.db.commit()

        return IngestionResponse(document_id=doc_id, status="indexed", estimated_time=0)

    async def get_status(self, document_id: str, user_id: str) -> IngestionStatus:
        cursor = self.db.cursor()
        cursor.execute("SELECT id, status FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise AppException("Document not found", status_code=404)
        return IngestionStatus(document_id=row["id"], status=row["status"], progress=100, chunks_created=0)
