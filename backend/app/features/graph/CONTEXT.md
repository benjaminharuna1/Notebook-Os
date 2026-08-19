# graph — knowledge graph from indexed papers

One job: build a concept knowledge graph from chunked papers, with checkpoints, themes, tracked concepts, and concept summaries.

## Inputs

| Input | Source | Notes |
|---|---|---|
| document_ids | Query/body | Filter to specific documents |
| depth | Query param | Graph traversal depth (default 2) |
| project_id | Query/body | Scope to project |
| force | Query param | Skip cache/checkpoints |
| concept label | Body | For concept summary SSE |

## Process

1. **Build graph** — extract concepts from chunks, build nodes+edges via GraphBuilder
2. **Layout** — force-directed positioning via layout_nodes()
3. **Checkpoint** — save to graph_history table with fingerprint (avoids rebuild when unchanged)
4. **Themes** — detect top concepts per document as candidate tracked themes
5. **Tracked concepts** — user-curated concept list that biases pruning
6. **Concept summary** — LLM streams a summary for a concept with source citations
7. **History** — browse, favourite, delete past graph checkpoints

## Outputs

| Output | Type | Notes |
|---|---|---|
| GraphResponse | `{nodes: [{id, label, x, y, ...}], edges: [{source, target, weight}]}` | Concept graph |
| Checkpoints | `[{id, created_at, is_favourite, nodes, edges}]` | History list |
| Concept summary | SSE stream | LLM-generated concept overview |
| Themes | `[{doc_id, doc_name, themes: [{concept, count}]}]` | Candidate tracked concepts |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST + SSE endpoints for graph |
| `service.py` | GraphService: build, checkpoint, themes, tracked preferences |
| `builder.py` | GraphBuilder: concept extraction, node/edge creation, layout |
| `llm_service.py` | GraphLLMService: query refinement, concept summaries |
| `tracked_service.py` | CRUD for user-tracked concepts |
| `jobs.py` | Background graph generation via actions registry |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
