# models — LLM provider management

One job: list available models (Ollama, local GGUF, cloud), switch active model, and provide provider instances for chat/summaries.

## Inputs

| Input | Source | Notes |
|---|---|---|
| model_id | Body | Format: `provider:model_name` |
| DownloadModelRequest | Body | HuggingFace model download |
| user_id | Dependency | Scoped to current user |

## Process

1. **List** — scan Ollama API, local GGUF files, cloud providers (based on user API keys)
2. **Switch** — set is_active in model_configs table, or insert new row
3. **Get provider** — instantiate OllamaProvider/LocalLLMProvider/OpenAIProvider/AnthropicProvider/GoogleProvider
4. **Catalog** — return device-tier recommendations + cloud presets + download status
5. **HuggingFace download** — download GGUF files to LOCAL_MODELS_DIR in background
6. **Local status** — Ollama running check, recommended models by device tier

## Outputs

| Output | Type | Notes |
|---|---|---|
| Available models | `[{id, name, provider, source}]` | Combined list |
| Active model | `{id, provider, model_id, source}` | Currently selected |
| Provider instance | LLMProvider | Used by chat/graph/literature for streaming |
| Catalog | Recommendations + presets + downloads | For settings UI |

## Key files

| File | Purpose |
|---|---|
| `router.py` | REST endpoints: list, switch, catalog, downloads |
| `service.py` | ModelService: model listing, switching, provider factory |
| `repository.py` | SQLite CRUD for model_configs |
| `catalog.py` | Device tier recommendations, cloud model presets |
| `downloads.py` | HuggingFace GGUF download manager |
| `providers/ollama.py` | Ollama API provider |
| `providers/local.py` | Local GGUF provider (llama-cpp-python) |
| `providers/openai.py` | OpenAI API provider |
| `providers/anthropic.py` | Anthropic API provider |
| `providers/google.py` | Google Gemini API provider |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
