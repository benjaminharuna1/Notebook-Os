# FEATURE_NAME feature

## Purpose
Brief description of what this feature does.

## Inputs
| Input | Source | Notes |
|---|---|---|
| `user_id` | JWT token | Required for all endpoints |
| `project_id` | Query/path param | Scopes data to project |

## Process
1. Router validates request
2. Service orchestrates business logic
3. Repository queries SQLite
4. Response returned

## Outputs
| Output | Type | Notes |
|---|---|---|
| JSON response | `ExampleResponse` | Standard response model |

## Key files
| File | Purpose |
|---|---|
| `router.py` | FastAPI endpoints |
| `service.py` | Business logic |
| `repository.py` | SQLite queries |
| `schemas.py` | Pydantic models |

## Human check
- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports: feature does not import from other features
