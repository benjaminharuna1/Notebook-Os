from typing import List

from app.core.config import settings
from app.features.processing.chunker import RecursiveCharacterChunker
from app.features.processing.cleaner import TextCleaner
from app.shared.id_utils import generate_id


class ProcessingService:
    def __init__(self):
        self.cleaner = TextCleaner()
        self.chunker = RecursiveCharacterChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    def process(self, text: str, document_id: str) -> List[dict]:
        cleaned = self.cleaner.clean(text)
        chunks = self.chunker.chunk(cleaned)
        result = []
        for i, chunk in enumerate(chunks):
            result.append({
                "id": generate_id(),
                "document_id": document_id,
                "chunk_index": i,
                "content": chunk["text"],
                "page_number": chunk.get("page_number"),
                "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
                "token_count": chunk.get("token_count", 0),
            })
        return result
