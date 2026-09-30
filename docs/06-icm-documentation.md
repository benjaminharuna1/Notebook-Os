# ICM Documentation Structure

Each feature has a `CONTEXT.md` file that serves as its ICM documentation, providing a self-contained reference that any AI agent can read to understand and work on that feature without slurping the entire codebase.

## Per-Feature CONTEXT.md Structure

Every `CONTEXT.md` follows this standardised format:

```markdown
# feature-name — one-line description

One job: single sentence describing the feature's purpose.

## Inputs
| Input | Source | Notes |
|---|---|---|

## Process
1. Step-by-step description of what the feature does

## Outputs
| Output | Type | Notes |
|---|---|---|

## Key files
| File | Purpose |
|---|---|---|

## Human check
- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
```

## Backend ICM Files

| Feature | CONTEXT.md Location |
|---------|-------------------|
| Auth | `backend/app/features/auth/CONTEXT.md` |
| Projects | `backend/app/features/projects/CONTEXT.md` |
| Ingestion | `backend/app/features/ingestion/CONTEXT.md` |
| Processing | `backend/app/features/processing/CONTEXT.md` |
| Embedding | `backend/app/features/embedding/CONTEXT.md` |
| Documents | `backend/app/features/documents/CONTEXT.md` |
| Search | `backend/app/features/search/CONTEXT.md` |
| Chat | `backend/app/features/chat/CONTEXT.md` |
| Graph | `backend/app/features/graph/CONTEXT.md` |
| Literature | `backend/app/features/literature/CONTEXT.md` |
| Models | `backend/app/features/models/CONTEXT.md` |
| Skills | `backend/app/features/skills/CONTEXT.md` |
| Settings | `backend/app/features/settings/CONTEXT.md` |
| Actions | `backend/app/features/actions/CONTEXT.md` |

## Frontend ICM Files

| Feature | CONTEXT.md Location |
|---------|-------------------|
| Auth | `frontend/src/lib/features/auth/CONTEXT.md` |
| Projects | `frontend/src/lib/features/projects/CONTEXT.md` |
| Ingestion | `frontend/src/lib/features/ingestion/CONTEXT.md` |
| Documents | `frontend/src/lib/features/documents/CONTEXT.md` |
| Search | `frontend/src/lib/features/search/CONTEXT.md` |
| Chat | `frontend/src/lib/features/chat/CONTEXT.md` |
| Graph | `frontend/src/lib/features/graph/CONTEXT.md` |
| Literature | `frontend/src/lib/features/literature/CONTEXT.md` |
| Models | `frontend/src/lib/features/models/CONTEXT.md` |
| Skills | `frontend/src/lib/features/skills/CONTEXT.md` |
| Settings | `frontend/src/lib/features/settings/CONTEXT.md` |
| Actions | `frontend/src/lib/features/actions/CONTEXT.md` |

## System-Level Prompts

Located in `backend/_system/prompts/`:

| File | Purpose |
|------|---------|
| `base_system.md` | Core LLM rules for chat responses |
| `apa_citation.md` | APA 7th edition citation formatting rules |
| `reference_handling.md` | Reference fallback and verification instructions |
| `secondary_sources.md` | Secondary source handling instructions |

## Why ICM?

- **Agent-friendly**: Any AI agent can read one `CONTEXT.md` and immediately understand a feature's contract
- **No slurping**: Eliminates need to read entire codebase for small changes
- **Living documentation**: Always accurate because it lives next to the code it describes
- **Standardised**: Same format across all features means predictable navigation
