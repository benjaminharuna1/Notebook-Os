# Notebook AI OS — Architecture Index

> This file is an index. Detailed architecture documentation is split into focused files under `docs/` to reduce context for coding agents.

## Quick Navigation

| Document | Lines | What it covers |
|----------|-------|----------------|
| [01-architecture-overview.md](docs/01-architecture-overview.md) | ~100 | System diagram, data flow |
| [02a-backend-structure.md](docs/02a-backend-structure.md) | ~220 | Backend directory tree (15 features) |
| [02b-frontend-structure.md](docs/02b-frontend-structure.md) | ~120 | Frontend directory tree (12 features) |
| [03-database-schema.md](docs/03-database-schema.md) | ~190 | All 13 SQLite tables, indexes, ChromaDB |
| [04a-api-auth-projects.md](docs/04a-api-auth-projects.md) | ~65 | Auth, Projects, Ingestion, Documents endpoints |
| [04b-api-search-chat-graph.md](docs/04b-api-search-chat-graph.md) | ~65 | Search, Chat, Graph endpoints |
| [04c-api-literature-models.md](docs/04c-api-literature-models.md) | ~80 | Literature, Models, Skills, Settings, Actions endpoints |
| [05-current-state.md](docs/05-current-state.md) | ~75 | Implemented features, tech choices, verification |
| [06-icm-documentation.md](docs/06-icm-documentation.md) | ~67 | ICM file locations, format, rationale |

## Summary

**Notebook AI OS** is a local-first AI research assistant. 15 backend features, 12 frontend features. FastAPI + SvelteKit + SQLite + ChromaDB. 175 tests.

```
Backend pipeline:
01_auth → 02_projects → 03_ingestion → 04_processing → 05_embedding →
06_documents → 07_search → 08_chat → 09_graph → 10_literature →
11_models → 12_skills → 13_settings → 14_actions
```

## Agent Entry Points

| Task | Start here |
|------|------------|
| System overview | `docs/01-architecture-overview.md` |
| Find a file | `docs/02a-backend-structure.md` or `docs/02b-frontend-structure.md` |
| Database schema | `docs/03-database-schema.md` |
| API endpoint | `docs/04a-api-auth-projects.md` etc. |
| Feature status | `docs/05-current-state.md` |
| ICM docs | `docs/06-icm-documentation.md` |
| Backend feature | `backend/app/features/{name}/CONTEXT.md` |
| Frontend feature | `frontend/src/lib/features/{name}/CONTEXT.md` |
| Run tests | `cd backend && .venv\Scripts\python.exe -m pytest -q` |
| Build frontend | `cd frontend && npm run build` |
