from app.core.database import get_chroma_client
from app.features.embedding.providers.ollama import OllamaEmbeddingProvider
from app.features.search.schemas import SearchRequest, SearchResponse, SearchResult


class SearchService:
    def __init__(self):
        self.embedder = OllamaEmbeddingProvider()
        self.chroma = get_chroma_client()

    async def search(self, req: SearchRequest, user_id: str) -> SearchResponse:
        query_embedding = self.embedder.embed([req.query])[0]
        collection = self.chroma.get_or_create_collection(name="documents")

        where = {"user_id": user_id}
        if req.document_ids:
            where["document_id"] = {"$in": req.document_ids}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=req.top_k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

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
