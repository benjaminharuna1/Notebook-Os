from typing import List


class RecursiveCharacterChunker:
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 128):
        self.chunk_size = max(1, int(chunk_size))
        self.chunk_overlap = min(max(0, int(chunk_overlap)), self.chunk_size - 1)

    def chunk(self, text: str) -> List[dict]:
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_text = text[start:end]
            chunks.append({
                "text": chunk_text,
                "char_start": start,
                "char_end": end,
                "token_count": len(chunk_text) // 4,
            })
            start += self.chunk_size - self.chunk_overlap

        return chunks
