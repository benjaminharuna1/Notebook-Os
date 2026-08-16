import re

import anyio

from app.core.database import get_chroma_client
from app.features.embedding.providers.factory import (
    resolve_collection_name,
    resolve_embedding_provider,
)
from app.features.search.schemas import SearchRequest, SearchResponse, SearchResult
from app.features.settings.service import SettingsService


class SearchService:
    """Project-wide search across every indexed paper.

    Semantic (embedding) results are merged with lexical keyword matches so
    both statements (``"how does dropout affect generalization"``) and bare
    keywords (``"dropout regularization"``) surface the right passages.
    """

    def __init__(self, db):
        self.db = db
        self.settings_service = SettingsService(db)

    def _resolve(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        embedder = resolve_embedding_provider(user_settings)
        collection_name = resolve_collection_name(user_settings)
        return embedder, collection_name

    def _semantic_sync(self, req: SearchRequest, user_id: str) -> list:
        """All blocking work (embedding + Chroma query) in one call so it can
        run off the event loop."""
        embedder, collection_name = self._resolve(user_id)
        query_embedding = embedder.embed([req.query])[0]

        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(name=collection_name)

        conditions = [{"user_id": user_id}]
        if req.project_id:
            conditions.append({"project_id": req.project_id})
        if req.document_ids:
            conditions.append({"document_id": {"$in": req.document_ids}})
        where = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=req.top_k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

        items = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                items.append(
                    {
                        "chunk_id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "score": 1.0 - results["distances"][0][i],
                        "document_id": results["metadatas"][0][i].get("document_id", ""),
                        "document_title": results["metadatas"][0][i].get("source_title", ""),
                        "page_number": results["metadatas"][0][i].get("page_number", 0),
                        "source": "semantic",
                    }
                )
        return items

    def _keyword_sync(self, req: SearchRequest, user_id: str, limit: int) -> list:
        """Lexical match over chunk text (per-token LIKE), ranked by how many
        of the query's tokens appear. Returns keyword-marked results."""
        query = (req.query or "").strip()
        if not query:
            return []

        tokens = list(dict.fromkeys(re.findall(r"[A-Za-z0-9À-ÿ_'-]{2,}", query.lower())))
        if not tokens:
            tokens = [query.lower()]
        phrase = query.lower()

        scoped = ["d.user_id = ?"]
        params = [user_id]
        if req.project_id:
            scoped.append("d.project_id = ?")
            params.append(req.project_id)
        if req.document_ids:
            scoped.append(f"d.id IN ({','.join('?' * len(req.document_ids))})")
            params.extend(req.document_ids)

        like_conds = ["c.content LIKE ? COLLATE NOCASE"] * len(tokens)
        like_params = [f"%{t}%" for t in tokens]

        sql = (
            "SELECT c.id AS chunk_id, c.content, c.document_id, c.page_number, "
            "d.title AS document_title "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE (" + " OR ".join(like_conds) + ") AND " + " AND ".join(scoped)
            + " ORDER BY c.rowid LIMIT ?"
        )
        rows = self.db.execute(sql, [*like_params, *params, limit * 3]).fetchall()

        scored = []
        for row in rows:
            content = (row["content"] or "").lower()
            hits = sum(1 for token in tokens if token in content)
            bonus = 1.0 if phrase in content else 0.0
            score = round(min(1.0, (hits + bonus) / (len(tokens) + 1)), 3)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)

        items = []
        for score, row in scored[:limit]:
            items.append(
                {
                    "chunk_id": row["chunk_id"],
                    "content": row["content"],
                    "score": score,
                    "document_id": row["document_id"],
                    "document_title": row["document_title"],
                    "page_number": row["page_number"],
                    "source": "keyword",
                }
            )
        return items

    @staticmethod
    def _merge(semantic: list, keyword: list, cap: int) -> list:
        seen = set()
        out = []
        for item in [*semantic, *keyword]:
            if item["chunk_id"] in seen:
                continue
            seen.add(item["chunk_id"])
            out.append(item)
            if len(out) >= cap:
                break
        return out

    async def search(self, req: SearchRequest, user_id: str) -> SearchResponse:
        semantic = await anyio.to_thread.run_sync(self._semantic_sync, req, user_id)

        keyword = []
        if req.include_keyword and (req.query or "").strip():
            keyword = await anyio.to_thread.run_sync(
                self._keyword_sync, req, user_id, max(req.top_k, 10)
            )

        merged = self._merge(semantic, keyword, cap=max(req.top_k * 3, 10))
        return SearchResponse(results=[SearchResult(**item) for item in merged])
