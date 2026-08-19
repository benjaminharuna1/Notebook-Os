# Literature Feature Contract

Literature mapping — build, browse, export structured paper metadata.

## What it does

Manages the literature mapping workflow: build literature maps from documents, browse per-paper entries (objective, methodology, findings, limitations), edit metadata, export to Excel/DOCX, stream summaries for clusters and papers.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects/{id}/literature/build` | POST | Start literature build job |
| `/projects/{id}/literature/jobs/{jobId}` | GET | Poll job status |
| `/projects/{id}/literature/map` | GET | Get literature map (graph + clusters) |
| `/projects/{id}/literature/entries` | GET | List all literature entries |
| `/projects/{id}/literature/entries/{paperId}` | GET | Get single entry |
| `/projects/{id}/literature/entries/{paperId}` | PATCH | Update entry fields |
| `/projects/{id}/literature/entries/{paperId}/regenerate` | POST | Regenerate one entry |
| `/projects/{id}/literature/entries/{paperId}/metadata` | GET/PATCH | View/edit paper metadata |
| `/projects/{id}/literature/entries/{paperId}/candidates/apply` | POST | Apply metadata candidate |
| `/projects/{id}/literature/entries/{paperId}/summarize` | POST (SSE) | Stream paper summary |
| `/projects/{id}/literature/clusters/summary` | POST (SSE) | Stream cluster summary |
| `/projects/{id}/literature/export` | GET | Export literature map (xlsx) |
| `/projects/{id}/literature/references/export.docx` | GET | Export references (docx) |
| `/projects/{id}/literature/regenerate` | POST | Batch regenerate metadata |
| `/projects/{id}/literature/status` | GET | Check readiness (model + network) |
| `/search` | POST | Search papers for linking |
| `/projects/{id}/documents/{docId}/file` | GET | Fetch PDF blob for viewer |

## State managed

No dedicated store — relies on route-level data loading and local component state.

## Special patterns

- **SSE streaming**: `streamClusterSummary()` and `streamPaperSummary()` for LLM-generated summaries
- **File downloads**: `exportLiteratureMap()` and `exportReferencesDocx()` trigger browser downloads via blob URLs
- **PDF viewer**: `getDocumentFileUrl()` fetches PDF as blob for inline viewing
- **Type reuse**: Imports `GraphNode`, `GraphEdge`, `LiteratureEntry` from `graph/types.ts`
- **Metadata candidates**: External metadata sources suggested with confidence scores — user picks one
