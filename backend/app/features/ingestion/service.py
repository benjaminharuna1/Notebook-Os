from app.core.config import settings
from app.core.database import get_chroma_client
from app.features.ingestion.extractors.pdf import PDFExtractor
from app.features.ingestion.schemas import IngestionResponse, IngestionStatus
from app.features.processing.service import ProcessingService
from app.features.embedding.service import EmbeddingService
from app.shared.file_utils import ensure_dir
from app.shared.id_utils import generate_id


class IngestionService:
    def __init__(self, db):
        self.db = db
        self.extractors = {"pdf": PDFExtractor()}

    async def ingest(self, file, user_id: str) -> IngestionResponse:
        doc_id = generate_id()
        upload_dir = ensure_dir(settings.UPLOAD_DIR)

        file_path = str(upload_dir / file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        ext = file.filename.rsplit(".", 1)[-1].lower()
        extractor = self.extractors.get(ext)
        if not extractor:
            raise ValueError(f"Unsupported file type: {ext}")

        extracted = extractor.extract(file_path)

        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO documents (id, user_id, title, filename, file_path, file_type, file_size, page_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, user_id, extracted.title or file.filename, file.filename, file_path, ext, len(content), extracted.page_count, "processing"),
        )
        self.db.commit()

        processing = ProcessingService()
        chunks = processing.process(extracted.text, doc_id)

        embedding = EmbeddingService()
        await embedding.embed_chunks(chunks, doc_id, user_id)

        cursor.execute("UPDATE documents SET status = 'indexed', indexed_at = datetime('now') WHERE id = ?", (doc_id,))
        self.db.commit()

        return IngestionResponse(document_id=doc_id, status="processing", estimated_time=30)

    async def get_status(self, document_id: str, user_id: str) -> IngestionStatus:
        cursor = self.db.cursor()
        cursor.execute("SELECT id, status FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Document not found")
        return IngestionStatus(document_id=row["id"], status=row["status"], progress=100, chunks_created=0)
