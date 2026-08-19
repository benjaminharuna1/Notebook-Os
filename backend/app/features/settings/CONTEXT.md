# settings — user preferences

One job: store and retrieve per-user settings including model config, chunking params, API keys, and device tier.

## Inputs

| Input | Source | Notes |
|---|---|---|
| SettingsUpdate | Body | Partial settings dict |
| user_id | Dependency | Scoped to current user |

## Process

1. **Get** — read JSON blob from user_settings, decrypt API keys before returning
2. **Update** — merge partial updates into existing settings
3. **Device tier change** — apply tier defaults (chunk_size, overlap, max_tokens, default_llm, embedding)
4. **Encrypt** — encrypt `*_api_key` fields before storing
5. **Model sync** — when provider/default_llm changes, call ModelService.switch_model to keep active model in sync

## Outputs

| Output | Type | Notes |
|---|---|---|
| SettingsResponse | `{settings: {...}}` | Full settings dict with decrypted keys |

## Settings keys (partial)

| Key | Purpose |
|---|---|
| `device_tier` | low/medium/high — drives default params |
| `default_llm` | Active chat model name |
| `provider` | ollama/local/openai/anthropic/google |
| `chunk_size` / `chunk_overlap` | Text chunking params |
| `embedding_provider` / `embedding_model` | Embedding config |
| `*_api_key` | Cloud provider API keys (encrypted at rest) |
| `cloud_enabled` | Allow cloud model providers |
| `max_concurrent_actions` | Background job concurrency limit |
| `temperature` / `max_tokens` | LLM generation params |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints: GET /settings, PUT /settings |
| `service.py` | SettingsService: get/update with encryption + tier defaults |
| `schemas.py` | SettingsUpdate, SettingsResponse |
| `defaults.py` | Device tier defaults (low/medium/high) |
| `core/crypto.py` | encrypt_secret / decrypt_secret (used by service) |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
