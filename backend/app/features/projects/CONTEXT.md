# projects — workspace management

One job: CRUD operations for projects that group documents together.

## Inputs

| Input | Source | Notes |
|---|---|---|
| ProjectCreate | Body | `{name, description}` |
| ProjectUpdate | Body | `{name?, description?}` |
| project_id | URL param | For single project operations |

## Process

1. **Create** — validate name, insert into projects table, return created project
2. **List** — return all projects for current user
3. **Get** — fetch single project by id + user_id
4. **Update** — partial update of name/description
5. **Delete** — remove vectors (all collections), delete disk files, cascade delete documents

## Outputs

| Output | Type | Notes |
|---|---|---|
| Project | `{id, name, description, created_at, updated_at}` | Single project |
| Project list | `{projects: [...]}` | All user projects |
| Delete result | `{success: true}` | After cleanup |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints: create, list, get, update, delete |
| `service.py` | ProjectService: CRUD + cascade deletion |
| `repository.py` | SQLite queries for projects |
| `schemas.py` | Project, ProjectCreate, ProjectUpdate |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
