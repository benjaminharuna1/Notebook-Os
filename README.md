# Notebook AI OS

Local-first AI research assistant. Chat with your PDFs entirely on-device.

The app runs **fully local out of the box** — no Ollama, no cloud, no API keys.
It uses [llama-cpp-python](https://pypi.org/project/llama-cpp-python/) to run small
quantized GGUF models (chat + embeddings) in-process on CPU, so it works on low-end
devices. Users with more powerful machines can optionally enable **Ollama** or enter
**OpenAI / Anthropic / Google API keys** in Settings.

## Quick Start

### Prerequisites
- Python 3.10+ (3.12 recommended)
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)

### Backend
```bash
cd backend
uv venv
uv pip install -r requirements.txt
cp .env.example .env
uv run uvicorn app.main:app --reload
```

### Download the local models (first run only)
Place two GGUF files in `backend/models/` (the app expects them there by default):

- **LLM**: `qwen2.5-0.5b-instruct-q4_k_m.gguf` (~400 MB) — small, CPU-friendly.
- **Embedding**: `nomic-embed-text-v1.5.Q4_K_M.gguf` (768-dim).

Download them from Hugging Face, e.g.:
```bash
# from backend/
mkdir -p models
uv run python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('Qwen/Qwen2.5-0.5B-Instruct-GGUF', 'qwen2.5-0.5b-instruct-q4_k_m.gguf', local_dir='models')
hf_hub_download('nomic-ai/nomic-embed-text-v1.5-GGUF', 'nomic-embed-text-v1.5.Q4_K_M.gguf', local_dir='models')
"
```
(Model names/repos are examples — any GGUF files placed in `backend/models/` will be listed
under `GET /api/v1/models/local/available` and selectable in the UI.)

> If `llama-cpp-python` needs to compile from source (no prebuilt wheel for your platform),
> install a C++ toolchain first. On Windows: "Desktop development with C++" via Visual Studio
> Build Tools. Prebuilt wheels exist for common platforms (Windows/Linux x86_64).

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Optional: point the frontend at a different backend:
```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000/api/v1
```

### Docker (optional, local-first)
```bash
docker-compose up
```
Ollama runs only if you opt in:
```bash
docker-compose --profile gpu up
```

## Providers

| Provider | Requires | Best for |
| --- | --- | --- |
| `local` (default) | GGUF files in `backend/models/` | Fully offline, low-end devices |
| `ollama` | Local Ollama server | Users with Ollama installed / GPU |
| `openai` / `anthropic` / `google` | API key in Settings | Powerful machines / cloud |

Embeddings use a per-model Chroma collection, so switching embedding providers is safe
(existing vectors are kept per model).
