# backend/app — FastAPI API

One job: serve the Notebook AI OS REST API for research paper management and AI chat.

## Pipeline (feature execution order)

```
01_auth → 02_projects → 03_ingestion → 04_processing → 05_embedding →
06_documents → 07_search → 08_chat → 09_graph → 10_literature →
11_models → 12_skills → 13_settings → 14_actions
```

## Key files

| File | Purpose |
|---|---|
| `main.py` | App factory, router registration |
| `core/database.py` | SQLite schema + migrations (run on startup) |
| `core/config.py` | All settings: token budgets, search defaults, JWT, etc. |
| `core/dependencies.py` | Auth (`get_current_user`), DB injection |
| `core/events.py` | App startup/shutdown lifecycle |
| `core/exceptions.py` | `AppException` + global handler |
| `shared/logger.py` | Structured logging |
| `shared/id_utils.py` | UUID generation |

## Cross-feature rules

- Features NEVER import from each other
- Cross-feature data flows through SQLite or `core/events.py`
- Each feature owns: `router.py`, `service.py`, `schemas.py`, `repository.py`, `tests/`
- New feature = copy `features/auth/` as skeleton, rename, implement

## Data flow

```
User request
  → router.py (validates, extracts user_id)
  → service.py (orchestrates business logic)
  → repository.py (SQLite queries)
  → response (JSON or SSE stream)
```

## Human check

- All 168 tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports: `grep -r "from app.features" features/ | grep -v __pycache__`
- Token budgets in `config.py` are sane for your model's context window
