from typing import List

from app.core.database import get_chroma_client, get_sqlite_connection
from app.features.embedding.providers.factory import (
    resolve_collection_name,
    resolve_embedding_provider,
)


class EmbeddingService:
    def __init__(self, settings_dict: dict | None = None):
        self.settings_dict = settings_dict or {}
        self.provider = resolve_embedding_provider(self.settings_dict)

    def embed_chunks(
        self,
        chunks: List[dict],
        document_id: str,
        user_id: str,
        project_id: str | None = None,
        title: str = "",
    ):
        texts = [c["content"] for c in chunks]
        embeddings = self.provider.embed(texts)

        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(
            name=resolve_collection_name(self.settings_dict)
        )

        ids = [c["id"] for c in chunks]
        metadatas = [
            {
                "user_id": user_id,
                "document_id": document_id,
                "source_title": title,
                "chunk_index": int(c.get("chunk_index", 0)),
                "page_number": int(c.get("page_number") or 0),
            }
            for c in chunks
        ]
        if project_id:
            for meta in metadatas:
                meta["project_id"] = project_id

        collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)

        # Persist chunks to SQLite as well — the knowledge graph (and any
        # other chunk-level feature) reads from the chunks table, not Chroma.
        db = get_sqlite_connection()
        try:
            db.executemany(
                """INSERT OR REPLACE INTO chunks
                   (id, document_id, chunk_index, content, page_number, char_start,
                    char_end, token_count, embedded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                [
                    (
                        c["id"],
                        c["document_id"],
                        int(c.get("chunk_index", 0)),
                        c["content"],
                        int(c.get("page_number") or 0),
                        c.get("char_start"),
                        c.get("char_end"),
                        int(c.get("token_count") or 0),
                    )
                    for c in chunks
                ],
            )
            db.commit()
        finally:
            db.close()
