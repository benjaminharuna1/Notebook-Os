# search — semantic retrieval over indexed papers

One job: find the most relevant chunks from indexed papers for a given query.

## Inputs

| Source | Path | When |
|---|---|---|
| Query | `req.query` | Every request |
| Top K | `req.top_k` | Default 15 |
| Project filter | `req.project_id` | Scoped search |
| Document filter | `req.document_ids` | Targeted search |
| User ID | `user_id` | Always |

## Process

1. **Embed query** — `embedding/providers/factory.py` resolves provider from settings
2. **Semantic search** — ChromaDB cosine similarity, returns top_k results
3. **Keyword search** — SQLite LIKE across chunks, ranked by token overlap
4. **Merge** — semantic results first, then keyword fills gaps, deduplicated
5. **Return** — `SearchResponse` with scored chunks

## Outputs

| Output | Destination | Format |
|---|---|---|
| SearchResponse | Chat service / direct API | `results: [{chunk_id, content, score, document_id, document_title, page_number}]` |

## Key files

| File | Purpose |
|---|---|
| `service.py` | Search orchestration (semantic + keyword merge) |
| `vector_store.py` | ChromaDB read/write abstraction |
| `schemas.py` | `SearchRequest`, `SearchResponse`, `SearchResult` |
| `router.py` | `POST /api/v1/search` endpoint |

## Search thresholds (configurable in `core/config.py`)

| Parameter | Value | Notes |
|---|---|---|
| `CHAT_SEARCH_TOP_K` | 15 | Default results to fetch |
| Score filter | `>=0.2` | Soft filter in chat service |
| Expansion threshold | `>=0.25` | For query expansion results |
| Keyword limit | `top_k * 3` | Fetch more for ranking |

## Human check

- Search quality: test with known queries, verify relevant chunks appear
- Score distribution: check that good matches score >0.5, poor matches <0.3
- Performance: ChromaDB queries should complete in <100ms for <10k chunks
