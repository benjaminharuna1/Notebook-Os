# actions — background job registry

One job: track long-running background actions (graph builds, literature builds, etc.) with progress, pause, and resume.

## Inputs

| Input | Source | Notes |
|---|---|---|
| action_id | URL param | For pause/resume |
| user_id | `get_current_user` | Scoped to current user |

## Process

1. **Register** — `registry.py` creates in-memory action with id, kind, status=queued
2. **Slot wait** — worker blocks until under max_concurrent_actions limit
3. **Progress** — workers call `update()` to report stage/progress
4. **Pause/Resume** — cooperative via `threading.Event`; checkpoint() blocks worker between stages
5. **Rebuild pending** — flag to re-run action after current run finishes
6. **Prune** — old terminal actions (done/error) capped at 50 per user

## Outputs

| Output | Type | Notes |
|---|---|---|
| Action list | `[{id, kind, title, status, progress, stage, ...}]` | Newest first |
| Action state | `{id, status, progress, stage, ...}` | After pause/resume |

## Key files

| File | Purpose |
|---|---|
| `router.py` | GET /actions, POST pause/resume |
| `registry.py` | In-memory action registry, slot management, pause events |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
