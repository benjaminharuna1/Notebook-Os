# embedding — vector embedding generation

One job: convert text chunks into vectors and store them in ChromaDB + SQLite.

## Inputs

| Input | Source | Notes |
|---|---|---|
| chunks | List of `{id, content, ...}` | From processing pipeline |
| document_id | String | Parent document |
| user_id | String | Owner scoping |
| project_id | String | Optional project scope |
| settings_dict | User settings | Selects embedding provider/model |

## Process

1. **Resolve provider** — factory picks fastembed/openai/etc based on user settings
2. **Embed** — batch-embed all chunk texts into vectors
3. **Store Chroma** — add ids, embeddings, metadatas, documents to collection
4. **Store SQLite** — INSERT OR REPLACE into chunks table (for graph/other features)

## Outputs

| Output | Type | Notes |
|---|---|---|
| ChromaDB vectors | Collection | Named by provider:model |
| SQLite chunks | chunks table | For graph and other features |

## Key files

| File | Purpose |
|---|---|
| `service.py` | EmbeddingService: embed + store in ChromaDB + SQLite |
| `providers/factory.py` | Resolves embedding provider from settings |
| `schemas.py` | EmbeddingRequest, EmbeddingResponse (unused by pipeline) |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
