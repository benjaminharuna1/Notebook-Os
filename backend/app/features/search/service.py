import anyio

from app.core.database import get_chroma_client
from app.features.embedding.providers.factory import (
    resolve_collection_name,
    resolve_embedding_provider,
)
from app.features.search.schemas import SearchRequest, SearchResponse, SearchResult
from app.features.settings.service import SettingsService


class SearchService:
    def __init__(self, db):
        self.db = db
        self.settings_service = SettingsService(db)

    def _resolve(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        embedder = resolve_embedding_provider(user_settings)
        collection_name = resolve_collection_name(user_settings)
        return embedder, collection_name

    def _search_sync(self, req: SearchRequest, user_id: str) -> dict:
        """All blocking work (embedding + Chroma query) in one call so it can
        run off the event loop."""
        embedder, collection_name = self._resolve(user_id)
        query_embedding = embedder.embed([req.query])[0]

        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(name=collection_name)

        where = {"user_id": user_id}
        if req.project_id:
            where["project_id"] = req.project_id
        if req.document_ids:
            where["document_id"] = {"$in": req.document_ids}

        return collection.query(
            query_embeddings=[query_embedding],
            n_results=req.top_k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

    async def search(self, req: SearchRequest, user_id: str) -> SearchResponse:
        results = await anyio.to_thread.run_sync(self._search_sync, req, user_id)

        if not results["ids"] or not results["ids"][0]:
            return SearchResponse(results=[])

        items = []
        for i in range(len(results["ids"][0])):
            items.append(
                SearchResult(
                    chunk_id=results["ids"][0][i],
                    content=results["documents"][0][i],
                    score=1.0 - results["distances"][0][i],
                    document_id=results["metadatas"][0][i].get("document_id", ""),
                    document_title=results["metadatas"][0][i].get("source_title", ""),
                    page_number=results["metadatas"][0][i].get("page_number", 0),
                )
            )

        return SearchResponse(results=items)
