# Current State & Design Decisions

## Implemented Features (15 backend / 12 frontend)

| # | Feature | Backend | Frontend | Description |
|---|---------|---------|----------|-------------|
| 1 | **Auth** | `features/auth/` | `features/auth/` | JWT registration, login, cookie auth |
| 2 | **Projects** | `features/projects/` | `features/projects/` | Workspace CRUD with cascade deletion |
| 3 | **Ingestion** | `features/ingestion/` | `features/ingestion/` | PDF upload, extract, pause/resume, reprocess |
| 4 | **Processing** | `features/processing/` | — | Text cleaning, recursive character chunking |
| 5 | **Embedding** | `features/embedding/` | — | fastembed (local) or Ollama embedding |
| 6 | **Documents** | `features/documents/` | `features/documents/` | CRUD, file serving, batch delete, orphan detection |
| 7 | **Search** | `features/search/` | `features/search/` | Semantic + keyword merge search |
| 8 | **Chat** | `features/chat/` | `features/chat/` | RAG chat with SSE streaming, auto-learn, project memory |
| 9 | **Graph** | `features/graph/` | `features/graph/` | Knowledge graph with checkpoints, themes, tracked concepts |
| 10 | **Literature** | `features/literature/` | `features/literature/` | Literature mapping, metadata enrichment, XLSX/DOCX export |
| 11 | **Models** | `features/models/` | `features/models/` | Ollama, local GGUF, OpenAI, Anthropic, Google providers |
| 12 | **Skills** | `features/skills/` | `features/skills/` | 8 installable AI skill definitions, keyword detection |
| 13 | **Settings** | `features/settings/` | `features/settings/` | Per-user preferences, device tier, encrypted API keys |
| 14 | **Actions** | `features/actions/` | `features/actions/` | Background job registry with pause/resume |
| 15 | — | — | `features/documents/` | *(Processing & embedding are backend-only pipeline stages)* |

## Key Technology Choices

| Component | Choice | Notes |
|-----------|--------|-------|
| Vector DB | ChromaDB (persistent) | Zero-config, local-first, Python-native |
| Embedding | fastembed (default) / Ollama nomic-embed-text | Local inference, configurable provider |
| LLM | llama-cpp-python (local GGUF) / Ollama / Cloud APIs | qwen2.5-0.5b default for local |
| Chunking | Recursive character splitter (1024 tokens, 128 overlap) | Configurable via settings |
| Chat protocol | SSE streaming | One-way stream, simpler than WebSockets |
| Metadata store | SQLite (raw aiosqlite) | Zero-config, WAL mode, foreign keys |
| Auth | JWT tokens + HttpOnly cookies | Rate-limited, per-user scoping |
| Search | Semantic (ChromaDB cosine) + keyword (SQLite LIKE) | Merged, deduplicated results |
| Frontend | SvelteKit + TypeScript + Tailwind | File-based routing, lightweight |
| Background jobs | In-memory registry (actions) | Pause/resume via threading.Event |
| Cloud isolation | Structured chunks only | Raw documents NEVER leave the local machine |

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vector DB | ChromaDB | Zero-config, local-first, Python-native, production-ready |
| Embedding | fastembed (default) | Local inference without Ollama dependency |
| LLM | llama-cpp-python with GGUF models | No Ollama required; qwen2.5-0.5b is tiny and fast |
| Cloud models | OpenAI / Anthropic / Google (opt-in) | Users enable per-account; raw docs never sent |
| Chunking | 1024 tokens, 128 overlap | Balance between context window and retrieval precision |
| Chat protocol | SSE streaming | Better UX than polling, simpler than WebSockets |
| Metadata store | SQLite with WAL mode | Lightweight, concurrent reads, zero-config |
| File handling | Background job_manager with pause/resume | Non-blocking ingestion with cooperative checkpoints |
| Auth | JWT + HttpOnly cookies | Secure, cookie-based for browser clients |
| Search | Semantic + keyword merge | Catches exact terms that semantic search misses |
| Prompt assembly | Token-budgeted sections | Prevents context overflow; configurable per section |
| Skill system | JSON manifests + keyword detection | Extensible without code changes |

## Verification Plan

### Test Suite

- **175 tests** across all features
- Run: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- Tests are co-located in each feature's `tests/` directory
- Coverage: auth, projects, ingestion, processing, embedding, documents, search, chat, graph (6 test files), literature (3 test files), models, skills, settings, actions

### Acceptance Criteria

- [x] `POST /api/v1/auth/register` creates user, returns JWT
- [x] `POST /api/v1/ingest/file` accepts a PDF and returns a document ID
- [x] `GET /api/v1/ingest/status/{id}` shows progress through queued → processing → indexed
- [x] `POST /api/v1/search` returns semantically relevant chunks (semantic + keyword merge)
- [x] `POST /api/v1/chat` streams a coherent response with APA citations via SSE
- [x] Chat auto-learned insights persist in project_memory table
- [x] Graph builds with checkpoints, themes, and tracked concepts
- [x] Literature mapping produces entries with metadata enrichment (Crossref/OpenAlex/LLM)
- [x] XLSX and DOCX exports work for literature mapping
- [x] Skills install, enable, and inject instructions into chat prompts
- [x] All services start cleanly with `docker-compose up`

### Feature Integrity Checks

```bash
# Run full test suite
cd backend && .venv\Scripts\python.exe -m pytest -q

# Verify no cross-feature imports
grep -r "from app.features" backend/app/features/ | grep -v __pycache__ | grep -v "from app.features.\w\+ import"

# Build frontend
cd frontend && npm run build
```
