# processing — text cleaning and chunking

One job: clean extracted text and split it into chunks ready for embedding.

## Inputs

| Input | Source | Notes |
|---|---|---|
| text | From extractor | Raw PDF text |
| document_id | From ingestion | Parent document |
| pages | Optional list | Per-page text from PDFExtractor |
| settings_dict | User settings | chunk_size, chunk_overlap overrides |

## Process

1. **Clean** — TextCleaner removes artifacts, normalizes whitespace
2. **Chunk** — RecursiveCharacterChunker splits by chunk_size with overlap
3. **Annotate** — each chunk gets id, document_id, chunk_index, page_number, char offsets, token_count

## Outputs

| Output | Type | Notes |
|---|---|---|
| Chunks | `[{id, document_id, chunk_index, content, page_number, char_start, char_end, token_count}]` | Ready for embedding |

## Key files

| File | Purpose |
|---|---|
| `service.py` | ProcessingService: orchestrates clean → chunk pipeline |
| `cleaner.py` | TextCleaner: artifact removal, whitespace normalization |
| `chunker.py` | RecursiveCharacterChunker: configurable size/overlap |
| `schemas.py` | Chunk model (output format) |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
