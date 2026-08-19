# skills — AI skill system

One job: manage installable skill definitions that inject specialized instructions into chat prompts.

## Inputs

| Input | Source | Notes |
|---|---|---|
| skill_id | URL param / body | For install/enable/uninstall |
| SkillEnableRequest | Body | `{enabled: bool}` |
| SkillManifest | Body | For custom skill import |
| user message | From chat | For keyword-based skill detection |

## Process

1. **Catalog** — scan `backend/skills/` for JSON manifests and SKILL.md folders (5min cache)
2. **Auto-install** — ensure all catalog skills are in user_skills table on first access
3. **Install/Uninstall** — add/remove from user_skills table
4. **Enable/Disable** — toggle enabled flag per user
5. **Import** — add custom skill manifest (rejects if id conflicts with catalog)
6. **Active instructions** — return all enabled skill instructions for prompt injection
7. **Detect relevant** — keyword matching picks skills relevant to the user's message

## Outputs

| Output | Type | Notes |
|---|---|---|
| Installed skills | `[{skill: manifest, enabled, installed_at}]` | User's skills |
| Catalog | `[{skill: manifest, installed}]` | Available skills |
| Instructions text | String | Concatenated enabled skill instructions |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints: list, catalog, install, enable, uninstall, import |
| `service.py` | SkillsService: catalog loading, CRUD, keyword detection |
| `schemas.py` | SkillManifest, SkillInstallRequest, SkillEnableRequest |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
