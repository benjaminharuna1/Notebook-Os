# Notebook OS — AI Research Assistant

Local-first research assistant that ingests, processes, and reasons over academic papers.

## Where am I

```
Notebook Os/
├── backend/app/              ← FastAPI API (14 feature modules)
├── frontend/src/             ← SvelteKit UI (mirrors backend features)
├── backend/skills/           ← 8 AI skill definitions (JSON)
├── backend/_system/          ← Factory reference (prompts, schemas)
├── data/                     ← Runtime: SQLite, ChromaDB, uploads (gitignored)
└── docs/ARCHITECTURE.md      ← Full architecture + API contract
```

## Where do I go for task X

| Task | Start here |
|---|---|
| Chat feature (most complex) | `backend/app/features/chat/service.py` |
| Prompt engineering | `backend/app/features/chat/prompt_builder.py` |
| Search quality / retrieval | `backend/app/features/search/service.py` |
| Database schema | `backend/app/core/database.py` |
| Configuration / settings | `backend/app/core/config.py` |
| Add a new feature | Copy `backend/app/features/auth/` as skeleton |
| Ingestion pipeline | `backend/app/features/ingestion/service.py` |
| Knowledge graph | `backend/app/features/graph/service.py` |
| Literature mapping | `backend/app/features/literature/service.py` |
| AI skills system | `backend/app/features/skills/service.py` |
| Frontend components | `frontend/src/lib/features/{name}/components/` |
| Frontend API layer | `frontend/src/lib/features/{name}/api.ts` |
| Run tests | `cd backend && .venv\Scripts\python.exe -m pytest -q` |
| Build frontend | `cd frontend && cmd /c "npm run build"` |

## Pipeline order (feature execution)

```
01_auth → 02_projects → 03_ingestion → 04_processing → 05_embedding →
06_documents → 07_search → 08_chat → 09_graph → 10_literature →
11_models → 12_skills → 13_settings → 14_actions
```

Features NEVER import from each other. Cross-feature data flows through
SQLite or events (`core/events.py`).

## Key conventions

- Backend: Python 3.10+, FastAPI, SQLite (aiosqlite), ChromaDB
- Frontend: SvelteKit, TypeScript, Tailwind
- Tests: `pytest -q` in `backend/`, `npm run build` in `frontend/`
- Auth: JWT tokens, `get_current_user` dependency
- Streaming: SSE via `StreamingResponse` for chat
- Token budgets: configurable in `config.py` (PROMPT_BUDGET_*)
- Anti-hallucination: prompt_builder.py enforces indexed-paper-only answers
- Citation style: APA 7th edition throughout

## Files to read for deep context

- `docs/ARCHITECTURE.md` — full system design, API contract, data flow
- `backend/_system/prompts/base_system.md` — core LLM rules
- `backend/app/features/chat/CONTEXT.md` — chat feature contract
- `backend/app/features/search/CONTEXT.md` — search feature contract
