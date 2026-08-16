from typing import List

from app.core.config import settings
from app.features.processing.chunker import RecursiveCharacterChunker
from app.features.processing.cleaner import TextCleaner
from app.shared.id_utils import generate_id


class ProcessingService:
    def __init__(self, settings_dict: dict | None = None):
        settings_dict = settings_dict or {}
        chunk_size = settings_dict.get("chunk_size")
        chunk_overlap = settings_dict.get("chunk_overlap")
        self.cleaner = TextCleaner()
        self.chunker = RecursiveCharacterChunker(
            chunk_size=chunk_size if chunk_size is not None else settings.CHUNK_SIZE,
            chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP,
        )

    def process(self, text: str, document_id: str, pages: List[str] | None = None) -> List[dict]:
        result = []
        index = 0
        sources = pages if pages is not None else [text]
        for page_number, page_text in enumerate(sources, start=1):
            cleaned = self.cleaner.clean(page_text)
            for chunk in self.chunker.chunk(cleaned):
                result.append({
                    "id": generate_id(),
                    "document_id": document_id,
                    "chunk_index": index,
                    "content": chunk["text"],
                    "page_number": page_number if pages is not None else None,
                    "char_start": chunk.get("char_start"),
                    "char_end": chunk.get("char_end"),
                    "token_count": chunk.get("token_count", 0),
                })
                index += 1
        return result
