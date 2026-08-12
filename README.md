# Notebook AI OS

Local-first AI research assistant. Chat with your PDFs entirely on-device.

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)
- Ollama (with `llama3.2:3b` and `nomic-embed-text`)

### Backend
```bash
cd backend
uv venv
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker-compose up
```
