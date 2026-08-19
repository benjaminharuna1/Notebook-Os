# Models Feature Contract

LLM model listing, switching, and status display.

## What it does

Lists available LLM models, shows the currently active model, and allows switching between providers (OpenAI, Anthropic, Google, Ollama). Provides a badge and selector widget used across other features.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/models` | GET | List available + active model |
| `/models/switch` | POST | Switch active model |
| `/models/ollama/available` | GET | List locally available Ollama models |

## State managed

| Store | Type | Purpose |
|---|---|---|
| `availableModels` | `ModelConfig[]` | All available models |
| `activeModel` | `ModelConfig \| null` | Currently selected model |

## Components

| Component | Purpose |
|---|---|
| `ModelSelector.svelte` | Dropdown to switch active model |
| `ModelBadge.svelte` | Small badge showing current model name |

## Types

- `ModelConfig`: id, name, provider, model_id, is_active, is_default, config, source (`local` | `cloud`)
