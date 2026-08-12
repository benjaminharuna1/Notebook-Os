from typing import List

from app.features.embedding.providers.ollama import OllamaEmbeddingProvider
from app.core.database import get_chroma_client


class EmbeddingService:
    def __init__(self):
        self.provider = OllamaEmbeddingProvider()

    async def embed_chunks(self, chunks: List[dict], document_id: str, user_id: str):
        texts = [c["content"] for c in chunks]
        embeddings = self.provider.embed(texts)

        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(name="documents")

        ids = [c["id"] for c in chunks]
        metadatas = [
            {
                "user_id": user_id,
                "document_id": document_id,
                "chunk_index": c["chunk_index"],
                "page_number": c.get("page_number", 0),
            }
            for c in chunks
        ]

        collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
