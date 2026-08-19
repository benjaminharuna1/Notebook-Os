# Ingestion Feature Contract

File upload and processing pipeline UI with queue management.

## What it does

Handles PDF/document uploads via drag-and-drop or file picker. Manages upload queue with real-time progress tracking. Provides pause/resume/reprocess controls for individual documents.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest/file` | POST (multipart) | Upload file for processing |
| `/ingest/status/{docId}` | GET | Poll processing status |
| `/ingest/{docId}/pause` | POST | Pause processing |
| `/ingest/{docId}/resume` | POST | Resume processing |
| `/ingest/{docId}/reprocess` | POST | Reprocess a single document |
| `/ingest/reprocess` | POST | Batch reprocess documents |

## State managed

| Store | Type | Purpose |
|---|---|---|
| `uploadQueue` | `UploadItem[]` | Active upload queue with progress/status |

`uploadQueue` provides `add(file)`, `patch(id, partial)`, `remove(id)` methods.

## Components

| Component | Purpose |
|---|---|
| `FileDropzone.svelte` | Drag-and-drop / click-to-upload area |
| `UploadQueue.svelte` | Visual queue showing upload progress and status |

## Special patterns

- **Multipart upload**: Uses `FormData` with direct `fetch()` (bypasses `api.post`) to support file uploads
- **Auth token**: Reads directly from `auth/store.ts` token for upload authorization
- **Status polling**: Components poll `getIngestionStatus()` to track processing progress
- **Queue management**: Each upload gets a UUID, tracked through queued → processing → done/error
