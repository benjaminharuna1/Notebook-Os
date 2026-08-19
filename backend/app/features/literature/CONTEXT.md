# literature — paper-level literature mapping

One job: build a literature map connecting papers via citation + similarity edges, with editable entries and metadata enrichment.

## Inputs

| Input | Source | Notes |
|---|---|---|
| project_id | URL param | Scope to project |
| paper_id | URL param | Single paper operations |
| LiteratureEntryUpdate | Body | Edit entry fields |
| LiteratureMetadataUpdate | Body | Edit paper metadata |
| LiteratureCandidateApply | Body | Adopt metadata candidate |
| cluster_id | Body | For cluster summary SSE |

## Process

1. **Build map** — papers as nodes, citation edges (fuzzy ref matching) + similarity edges (embedding cosine)
2. **Enrich metadata** — DOI extraction → Crossref/OpenAlex lookup → LLM fallback → unverified
3. **Entries** — editable literature rows (citation, objective, methodology, findings, limitations, relevance, APA)
4. **Community detection** — greedy modularity clustering of paper nodes
5. **Export** — XLSX workbook or DOCX references list
6. **Summaries** — SSE-streamed LLM summaries for clusters and individual papers
7. **Regenerate** — re-run enrichment for selected or all papers

## Outputs

| Output | Type | Notes |
|---|---|---|
| LiteratureMapResponse | `{nodes: [PaperNode], edges: [PaperEdge], clusters}` | Paper graph |
| LiteratureEntry | `{paper_id, citation, research_objective, methodology, ...}` | Editable entry |
| Metadata | `{title, authors, year, doi, abstract, verification_status, candidates}` | Paper metadata |
| XLSX export | Binary | Literature mapping workbook |
| DOCX export | Binary | APA references list |
| Summary | SSE stream | LLM-generated paper/cluster overview |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST + SSE endpoints for literature mapping |
| `service.py` | LiteratureService: map build, enrichment, entries, export, APA |
| `llm_service.py` | LiteratureLLMService: metadata extraction, summaries |
| `metadata.py` | Crossref/OpenAlex lookup, DOI extraction, title heuristics |
| `jobs.py` | Background literature map builds via actions registry |
| `schemas.py` | All request/response models |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
