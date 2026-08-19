# ingestion — PDF upload and processing pipeline

One job: accept PDF uploads, extract text, chunk, embed, and index into the search system.

## Inputs

| Input | Source | Notes |
|---|---|---|
| file | UploadFile | PDF only, max size from config |
| project_id | Form field | Optional project scope |
| document_id | URL param | For status/pause/resume/reprocess |
| document_ids | Body | Batch reprocess |

## Process

1. **Validate** — check file size, extension (.pdf), magic bytes (%PDF header)
2. **Save** — store to disk with server-controlled filename (prevents path traversal)
3. **Queue** — insert document row (status=queued), submit to background job_manager
4. **Extract** — PDFExtractor reads pages and metadata
5. **Process** — ProcessingService cleans text + chunks (recursive character chunker)
6. **Embed** — EmbeddingService batch-embeds and stores in ChromaDB + SQLite
7. **Index** — update status to "indexed", trigger literature map rebuild
8. **Pause/Resume** — cooperative via job_manager checkpoint() calls

## Outputs

| Output | Type | Notes |
|---|---|---|
| IngestionResponse | `{document_id, status, estimated_time}` | Immediate response |
| IngestionStatus | `{document_id, status, progress, error}` | Status polling |
| Document row | SQLite | status: queued→processing→indexed/failed/paused |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints: ingest, status, pause, resume, reprocess |
| `service.py` | IngestionService: full pipeline orchestration |
| `extractors/pdf.py` | PDF text and metadata extraction |
| `jobs.py` | Background job_manager for pipeline execution |
| `schemas.py` | IngestionResponse, IngestionStatus, IngestionBatchReprocess |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
