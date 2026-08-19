# Graph Feature Contract

Knowledge graph visualization and concept exploration with SSE-powered summaries.

## What it does

Renders an interactive knowledge graph (nodes + edges) from document concepts. Supports generation jobs, checkpoint history, concept tracking, theme extraction, and streamed concept summaries.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/graph` | GET | Fetch graph data (nodes, edges) |
| `/graph/generate` | POST | Start graph generation job |
| `/graph/history` | GET | List graph checkpoints |
| `/graph/history/{id}` | GET | Get checkpoint with full graph |
| `/graph/history/{id}` | PATCH | Toggle favourite |
| `/graph/history/{id}` | DELETE | Delete checkpoint |
| `/graph/themes` | GET | Per-document theme extraction |
| `/graph/search` | POST | Refine search query against graph |
| `/graph/concepts/summary` | POST (SSE) | Streamed concept summary |
| `/graph/concepts/tracked` | GET | List tracked concepts |
| `/graph/concepts/tracked` | POST | Add tracked concept |
| `/graph/concepts/tracked/{id}` | DELETE | Remove tracked concept |

## State managed

No global store — graph data fetched per page load. Uses local component state.

## Components

| Component | Purpose |
|---|---|
| `KnowledgeGraph.svelte` | Force-directed graph renderer with zoom/pan |

## Special patterns

- **SSE concept summary**: `streamConceptSummary()` streams LLM explanation of a concept node
- **Generation jobs**: `startGraphGeneration()` returns `GenerationJob` with progress tracking
- **Checkpoints**: Graph versions saved as checkpoints — can favourite, restore, compare
- **Cluster color utility**: `clusterColor.ts` maps cluster IDs to consistent colors
- **Perf utilities**: `perf.ts` for graph rendering performance hints
