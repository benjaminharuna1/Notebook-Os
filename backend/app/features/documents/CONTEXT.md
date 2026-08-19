# documents — document CRUD and file management

One job: list, retrieve, serve, and delete documents. Also handles orphan detection and cleanup.

## Inputs

| Input | Source | Notes |
|---|---|---|
| page, limit, search, file_type | Query params | Paginated list with filters |
| project_id | Query param | Scope to project |
| document_id | URL param | Single document operations |
| DocumentBatchDelete | Body | List of document_ids to delete |

## Process

1. **List** — paginated query with search/file_type/project filters; triggers APA recomputation per project
2. **Get** — fetch single document + chunk count
3. **Delete** — remove from DB, ChromaDB vectors, disk file, graph checkpoints, and rebuild literature map
4. **Batch delete** — same as delete but for multiple documents
5. **File serve** — resolve path safely within UPLOAD_DIR, return FileResponse
6. **Orphan detection** — find indexed docs without literature entries or failed docs; clean deletes them

## Outputs

| Output | Type | Notes |
|---|---|---|
| Document list | `{documents: [...], total, page, pages}` | Paginated |
| Document detail | `{id, title, chunk_count, ...}` | Single doc |
| FileResponse | PDF/DOCX/etc | Served from disk |
| Orphan list | `[{id, title, reason}]` | For cleanup UI |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints for documents |
| `service.py` | DocumentService: CRUD, file serving, orphan management |
| `repository.py` | SQLite queries for documents |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
