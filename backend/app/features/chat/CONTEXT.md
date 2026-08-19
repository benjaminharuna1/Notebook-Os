# chat — context-aware AI conversation

One job: take a user message, search indexed papers, build context, stream LLM response with APA citations.

## Inputs

| Source | Path | When |
|---|---|---|
| User message | `req.message` | Every request |
| Session ID | `req.session_id` | Continuing a session |
| Project ID | `req.project_id` | New session scoping |
| Slash command | `req.slash_command` | `/summarize`, `/evaluate`, `/mapping`, `/review` |

## Process

1. **Session management** — create or load session, handle regenerate
2. **Slash command** — detect `/summarize` etc., inject special instruction
3. **Semantic search** — `search/service.py` with `top_k=15`, score filter `>=0.2`
4. **Query expansion** — second search with extracted key terms (stop words removed)
5. **Reference fallback** — 3-pass SQL: surname1+surname2+year, surname1+year, surname1+surname2
6. **Web fallback** — DuckDuckGo search if reference not in indexed papers
7. **Past context** — fetch recent chats from other sessions in same project
8. **Project memory** — fetch accumulated learning (interests, preferences, references)
9. **Skill detection** — `skills/service.py` matches keywords to relevant skills
10. **Prompt assembly** — `prompt_builder.py` builds system prompt with all context
11. **Stream response** — LLM streams tokens via SSE, persisted to DB
12. **Auto-learn** — extract topics, preferences, references from interaction

## Outputs

| Output | Destination | Format |
|---|---|---|
| SSE stream | Frontend | `data: {"type":"chunk","content":"..."}` |
| Sources | Frontend | `data: {"type":"sources","sources":[...]}` |
| Done signal | Frontend | `data: {"type":"done","session_id":"..."}` |
| chat_messages | SQLite | role, content, sources JSON, model_used |
| project_memory | SQLite | key-value pairs for learned insights |

## Key files

| File | Purpose | Size |
|---|---|---|
| `service.py` | Main orchestrator — search, context, stream | ~650 lines |
| `prompt_builder.py` | System prompt assembly with APA rules | ~220 lines |
| `repository.py` | SQLite CRUD for sessions, messages, memory | ~170 lines |
| `web_search.py` | DuckDuckGo HTML scraper for reference fallback | ~70 lines |
| `router.py` | FastAPI endpoints for chat | ~80 lines |
| `schemas.py` | Pydantic request/response models | ~40 lines |

## Token budgets (configurable in `core/config.py`)

| Section | Budget | Notes |
|---|---|---|
| Source chunks | 10,000 | Search results (most important) |
| Literature entries | 4,000 | Per-paper metadata |
| Past chats | 2,000 | Previous conversations |
| Project memory | 1,500 | Learned insights |

## Human check

- Prompt quality: review `prompt_builder.py` system prompt sections
- Search quality: check `service.py` thresholds (score `>=0.2`, top_k `15`)
- APA compliance: verify citation format in `prompt_builder.py` rules
- Learned insights: query `SELECT * FROM project_memory WHERE project_id = ?`
- Past context: verify `get_recent_project_chats()` returns relevant history
