# Settings Feature Contract

User settings, provider configuration, and local model management.

## What it does

Manages user preferences (chunk size, temperature, max tokens), API provider keys (OpenAI, Anthropic, Google), embedding configuration, local model status (Ollama), and HuggingFace model downloads.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/settings` | GET | Load user settings |
| `/settings` | PUT | Update user settings |
| `/local/status` | GET | Ollama status + device tier |
| `/models/catalog` | GET | Browse available local models |
| `/models/hf/download` | POST | Start HuggingFace model download |
| `/models/hf/downloads` | GET | List download progress |

## State managed

No global store — settings fetched/saved on page interaction.

## Components

No feature-specific components — settings UI is in `routes/settings/`.

## Types

- `UserSettings`: chunk_size, chunk_overlap, default_llm, embedding_backend, provider, device_tier, cloud_enabled, api keys, model selections, max_tokens, temperature, max_concurrent_actions
- `LocalStatus`: ollama_running, ollama_models[], device_tier, recommended_local_model, recommended_embedding
- `ModelCatalog`: device_tier, llm[], embeddings[], cloud_presets, downloads[]
- `ModelDownload`: key, name, kind, tier, size_label, status, progress, downloaded_bytes, total_bytes
