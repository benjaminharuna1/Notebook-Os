# Documents Feature Contract

Document library — list, view, delete, and manage orphaned documents.

## What it does

Provides the document library UI at `/library/[docId]`. Lists documents with pagination, search, and file-type filtering. Shows PDF viewer for individual documents. Handles orphan detection and cleanup.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/documents` | GET | List documents (paginated, filterable) |
| `/documents/{id}` | GET | Get single document details |
| `/documents/{id}` | DELETE | Delete single document |
| `/projects/{id}/documents/batch/delete` | POST | Batch delete documents |
| `/projects/{id}/documents/orphans` | GET | Find orphaned documents |
| `/projects/{id}/documents/clean-orphans` | POST | Delete all orphans |

## State managed

No dedicated store — components fetch data on mount and manage local state.

## Components

| Component | Purpose |
|---|---|
| `DocumentList.svelte` | Paginated table of documents with actions |
| `PdfViewer.svelte` | In-browser PDF rendering for document preview |

## Types

- `Document`: id, title, filename, file_type, file_size, page_count, status, created_at, indexed_at
- `DocumentList`: documents[], total, page
- `OrphanInfo`: id, title, reason (`indexed_without_entry` | `failed_permanently`), file_size
