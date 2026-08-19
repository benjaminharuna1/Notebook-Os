# Search Feature Contract

Semantic + keyword search over indexed document chunks.

## What it does

Provides a search interface at `/search` for querying the document corpus. Returns ranked chunks with source attribution (semantic or keyword match), scores, and page numbers.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/search` | POST | Execute search query |

Request body: `{ query, top_k, project_id }`

## State managed

No global store — search results managed in component-local state.

## Components

No feature-specific components — search UI is built in the route page.

## Types

- `SearchResult`: chunk_id, content, score, document_id, document_title, page_number, source (`semantic` | `keyword`)
- `SearchResponse`: results[]
