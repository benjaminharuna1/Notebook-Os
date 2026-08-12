# Notebook AI OS — Full System Architecture & Implementation Plan

## Overview

**Notebook AI OS** is a local-first AI research assistant that ingests, processes, understands, and reasons over research materials entirely on-device. Cloud models are optionally used as reasoning accelerators — they only ever receive structured, processed context, never raw documents.

The system follows a strict layered architecture with clean separation between ingestion, storage, retrieval, AI routing, and UI.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SvelteKit)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐  │
│  │ Notebook │ │   Chat   │ │  Upload  │ │ Graph  │ │ Model  │  │
│  │   View   │ │Interface │ │   UI     │ │  Viz   │ │Switch  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ └───┬────┘  │
└───────┼────────────┼────────────┼────────────┼──────────┼───────┘
        │            │            │            │          │
        └────────────┴────────────┴────────────┴──────────┘
                                  │ HTTP/REST
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  INGESTION   │───▶│  PROCESSING  │───▶│   EMBEDDING      │   │
│  │    LAYER     │    │    LAYER     │    │     ENGINE       │   │
│  │ PDF/Web/DOCX │    │ Chunk/Clean  │    │ nomic-embed-text │   │
│  └──────────────┘    └──────────────┘    └────────┬─────────┘   │
│                                                   │             │
│  ┌──────────────┐    ┌──────────────┐    ┌────────▼─────────┐   │
│  │  AI ROUTER   │◀───│   RETRIEVAL  │◀───│   VECTOR STORE   │   │
│  │ local/cloud  │    │    (RAG)     │    │    (ChromaDB)    │   │
│  └──────┬───────┘    └──────────────┘    └──────────────────┘   │
│         │                                                        │
│  ┌──────▼───────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  CHAT ENGINE │    │ GRAPH BUILDER│    │   INSIGHT ENGINE │   │
│  │(context-aware│    │  (NetworkX)  │    │   (Phase 3+)     │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌──────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ LOCAL MODELS │   │  LOCAL STORAGE  │   │   OPTIONAL CLOUD     │
│  (Ollama)    │   │ ChromaDB + Files│   │  OpenAI/Claude/Gemini│
│ llama3/mistral│  │  SQLite metadata│   │  (structured ctx only)│
└──────────────┘   └─────────────────┘   └──────────────────────┘
```

---

## Data Flow

```
User uploads PDF
      │
      ▼
[Ingestion Layer]
  - Save raw file to /data/uploads/
  - Extract text (PyMuPDF / pdfplumber)
  - Extract metadata (title, author, date)
      │
      ▼
[Processing Layer]
  - Clean text (remove noise, headers, footers)
  - Chunk text (semantic chunking, 512 tokens, 64 overlap)
  - Generate chunk metadata (page, source, position)
      │
      ▼
[Embedding Engine]
  - Embed each chunk via nomic-embed-text (Ollama)
  - Store embeddings → ChromaDB
  - Store metadata → SQLite
      │
      ▼
[Vector Store - ChromaDB]
  - Persistent local vector database
  - Collections per notebook/project
      │
      ▼
[Retrieval Layer - RAG]
  - Query = user question embedded
  - Cosine similarity search → top-k chunks
  - Assemble context window
      │
      ▼
[AI Router]
  - Route to Ollama (local) OR cloud model
  - Never send raw documents to cloud
  - Only send structured chunks + question
      │
      ▼
[Chat Engine]
  - System prompt + context + history
  - Stream response to frontend
  - Store chat history in SQLite
```

---

## Folder Structure

> **Design principle**: Feature-based organisation. Every feature owns its entire vertical slice — router, service, schemas, models, and tests — co-located in one folder. Adding a new feature means adding a new folder, never modifying existing ones.

### Organisation Rules
- `features/` — one sub-folder per domain capability (self-contained, independently deployable)
- `core/` — shared infrastructure used by ALL features (DB, config, auth, logging)
- `shared/` — reusable utilities that are feature-agnostic
- A feature folder may NEVER import from another feature folder (use `core/` or events for cross-feature communication)

```
notebook-ai-os/
│
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI app factory + feature router registration
│   │   │
│   │   ├── core/                          # Shared infrastructure (not feature-specific)
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # Pydantic BaseSettings (.env loading)
│   │   │   ├── database.py                # SQLite + ChromaDB init & session management
│   │   │   ├── dependencies.py            # FastAPI shared Depends() (db session, etc.)
│   │   │   ├── security.py                # Auth helpers (Phase 4)
│   │   │   ├── events.py                  # App startup/shutdown lifecycle hooks
│   │   │   └── exceptions.py              # Global exception handlers
│   │   │
│   │   ├── shared/                        # Reusable utilities, no business logic
│   │   │   ├── __init__.py
│   │   │   ├── logger.py                  # Structured logging setup
│   │   │   ├── file_utils.py              # Path helpers, MIME detection
│   │   │   ├── text_utils.py              # Text cleaning, normalisation
│   │   │   └── id_utils.py                # UUID generation helpers
│   │   │
│   │   └── features/                      # ← FEATURE-BASED MODULES
│   │       │
│   │       ├── ingestion/                 # Feature: ingest files & URLs
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /ingest/file, GET /ingest/status/{id}
│   │       │   ├── service.py             # Orchestrates extract → chunk → embed pipeline
│   │       │   ├── schemas.py             # Pydantic request/response models
│   │       │   ├── models.py              # SQLAlchemy/raw SQL models if needed
│   │       │   ├── extractors/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── base.py            # BaseExtractor ABC
│   │       │   │   ├── pdf.py             # PyMuPDF extraction
│   │       │   │   ├── web.py             # URL → clean text (Phase 2)
│   │       │   │   ├── docx.py            # Word documents (Phase 2)
│   │       │   │   ├── excel.py           # Spreadsheets (Phase 2)
│   │       │   │   └── image.py           # OCR via Tesseract (Phase 2)
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_service.py
│   │       │
│   │       ├── processing/                # Feature: chunk & clean extracted text
│   │       │   ├── __init__.py
│   │       │   ├── service.py             # Chunking orchestration
│   │       │   ├── schemas.py
│   │       │   ├── chunker.py             # Recursive character / semantic chunker
│   │       │   ├── cleaner.py             # Noise removal, deduplication
│   │       │   └── tests/
│   │       │       └── test_chunker.py
│   │       │
│   │       ├── embedding/                 # Feature: embed chunks → vector store
│   │       │   ├── __init__.py
│   │       │   ├── service.py             # Embedding orchestration
│   │       │   ├── schemas.py
│   │       │   ├── providers/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── base.py            # BaseEmbeddingProvider ABC
│   │       │   │   ├── ollama.py          # nomic-embed-text via Ollama
│   │       │   │   └── sentence_transformers.py  # Local Python alternative
│   │       │   └── tests/
│   │       │       └── test_embedding.py
│   │       │
│   │       ├── documents/                 # Feature: document library management
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /documents, DELETE /documents/{id}
│   │       │   ├── service.py             # CRUD operations on document metadata
│   │       │   ├── schemas.py
│   │       │   ├── repository.py          # SQLite queries (data access layer)
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_repository.py
│   │       │
│   │       ├── search/                    # Feature: semantic search over vector store
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /search
│   │       │   ├── service.py             # RAG retrieval, context assembly
│   │       │   ├── schemas.py
│   │       │   ├── vector_store.py        # ChromaDB read/write abstraction
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_vector_store.py
│   │       │
│   │       ├── chat/                      # Feature: context-aware AI chat
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /chat, GET /chat/sessions
│   │       │   ├── service.py             # Chat orchestration (history + RAG + LLM)
│   │       │   ├── schemas.py
│   │       │   ├── repository.py          # SQLite: sessions + messages CRUD
│   │       │   ├── prompt_builder.py      # System prompt + context window assembly
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_service.py
│   │       │
│   │       ├── models/                    # Feature: AI model management & routing
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /models, POST /models/switch
│   │       │   ├── service.py             # Model registry + active model tracking
│   │       │   ├── schemas.py
│   │       │   ├── repository.py          # SQLite model_configs CRUD
│   │       │   ├── ai_router.py           # local vs cloud routing decision logic
│   │       │   ├── providers/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── base.py            # BaseLLMProvider ABC
│   │       │   │   ├── ollama.py          # Ollama streaming client
│   │       │   │   ├── openai.py          # OpenAI client (Phase 2)
│   │       │   │   ├── anthropic.py       # Claude client (Phase 2)
│   │       │   │   └── google.py          # Gemini client (Phase 2)
│   │       │   └── tests/
│   │       │       └── test_router.py
│   │       │
│   │       └── graph/                     # Feature: knowledge graph (Phase 3)
│   │           ├── __init__.py
│   │           ├── router.py              # GET /graph
│   │           ├── service.py             # Graph build + traversal
│   │           ├── schemas.py
│   │           ├── builder.py             # NetworkX graph construction
│   │           ├── concept_extractor.py   # NLP entity/concept extraction
│   │           └── tests/
│   │               └── test_builder.py
│   │
│   ├── data/                              # Runtime data (gitignored)
│   │   ├── uploads/                       # Raw uploaded files
│   │   ├── processed/                     # Extracted text artifacts
│   │   ├── chroma_db/                     # ChromaDB persistence
│   │   └── notebook.db                    # SQLite database
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app.css                        # Global design tokens & resets
│   │   ├── app.html                        # SvelteKit HTML shell
│   │   │
│   │   ├── lib/
│   │   │   ├── core/                      # Shared non-feature code
│   │   │   │   ├── api/
│   │   │   │   │   └── client.ts          # Base fetch wrapper (auth, errors, SSE)
│   │   │   │   ├── components/
│   │   │   │   │   ├── ui/                # Headless/generic UI primitives
│   │   │   │   │   │   ├── Button.svelte
│   │   │   │   │   │   ├── Badge.svelte
│   │   │   │   │   │   ├── Spinner.svelte
│   │   │   │   │   │   ├── Modal.svelte
│   │   │   │   │   │   └── Toast.svelte
│   │   │   │   │   └── layout/
│   │   │   │   │       ├── AppShell.svelte
│   │   │   │   │       ├── Sidebar.svelte
│   │   │   │   │       └── Header.svelte
│   │   │   │   └── stores/
│   │   │   │       └── toasts.ts          # Global notification store
│   │   │   │
│   │   │   └── features/                  # ← FEATURE-BASED MODULES
│   │   │       │
│   │   │       ├── ingestion/             # Feature: file upload & processing status
│   │   │       │   ├── api.ts             # API calls for /ingest/*
│   │   │       │   ├── store.ts           # Upload queue & progress state
│   │   │       │   ├── types.ts           # TS types for this feature
│   │   │       │   └── components/
│   │   │       │       ├── FileDropzone.svelte
│   │   │       │       ├── UploadQueue.svelte
│   │   │       │       └── UploadProgress.svelte
│   │   │       │
│   │   │       ├── documents/             # Feature: document library
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── DocumentList.svelte
│   │   │       │       ├── DocumentCard.svelte
│   │   │       │       └── DocumentDetail.svelte
│   │   │       │
│   │   │       ├── chat/                  # Feature: AI chat interface
│   │   │       │   ├── api.ts             # SSE streaming client
│   │   │       │   ├── store.ts           # Sessions + messages state
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── ChatWindow.svelte
│   │   │       │       ├── ChatMessage.svelte
│   │   │       │       ├── ChatInput.svelte
│   │   │       │       ├── ChatSidebar.svelte
│   │   │       │       └── SourceCitation.svelte
│   │   │       │
│   │   │       ├── search/                # Feature: semantic search
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── SearchBar.svelte
│   │   │       │       └── SearchResults.svelte
│   │   │       │
│   │   │       ├── models/               # Feature: model selector & switching
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── ModelSelector.svelte
│   │   │       │       └── ModelBadge.svelte
│   │   │       │
│   │   │       └── graph/                # Feature: knowledge graph (Phase 3)
│   │   │           ├── api.ts
│   │   │           ├── store.ts
│   │   │           ├── types.ts
│   │   │           └── components/
│   │   │               ├── KnowledgeGraph.svelte
│   │   │               └── GraphControls.svelte
│   │   │
│   │   └── routes/                        # SvelteKit file-based routing
│   │       ├── +layout.svelte             # Root layout (AppShell)
│   │       ├── +page.svelte               # / → redirects to /chat
│   │       ├── chat/
│   │       │   ├── +page.svelte           # /chat — main chat view
│   │       │   └── [sessionId]/
│   │       │       └── +page.svelte       # /chat/:id — specific session
│   │       ├── library/
│   │       │   ├── +page.svelte           # /library — document browser
│   │       │   └── [docId]/
│   │       │       └── +page.svelte       # /library/:id — document detail
│   │       ├── search/
│   │       │   └── +page.svelte           # /search — semantic search
│   │       └── graph/
│   │           └── +page.svelte           # /graph — knowledge graph (Phase 3)
│   │
│   ├── static/
│   ├── package.json
│   ├── svelte.config.js
│   └── vite.config.ts
│
├── docker-compose.yml                     # Full stack orchestration
├── ARCHITECTURE.md                        # This file
└── README.md
```

### Why Feature-Based?

| Concern | Layer-Based (old) | Feature-Based (new) |
|---------|------------------|--------------------|
| Add a new feature | Touch `api/`, `services/`, `models/` | Add one folder under `features/` |
| Find all code for Chat | Hunt across 5+ folders | One folder: `features/chat/` |
| Delete a feature | Risk breaking shared modules | Delete one folder |
| Onboard a new dev | Must understand entire codebase | Read one feature folder |
| Test isolation | Tests scattered across `tests/` | Tests co-located in `feature/tests/` |
| Scale to microservices | Major refactor required | Each feature folder → its own service |

---

## Database Schema

### SQLite — `notebook.db`

```sql
-- Documents table (metadata for all ingested files)
CREATE TABLE documents (
    id          TEXT PRIMARY KEY,         -- UUID
    title       TEXT NOT NULL,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_type   TEXT NOT NULL,            -- pdf | web | docx | image
    file_size   INTEGER,
    page_count  INTEGER,
    source_url  TEXT,                     -- for web ingestion
    author      TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    indexed_at  DATETIME,
    status      TEXT DEFAULT 'pending'    -- pending | processing | indexed | failed
);

-- Chunks table (processed text units)
CREATE TABLE chunks (
    id          TEXT PRIMARY KEY,         -- UUID
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    page_number INTEGER,
    char_start  INTEGER,
    char_end    INTEGER,
    token_count INTEGER,
    embedded_at DATETIME,
    UNIQUE(document_id, chunk_index)
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    model_used  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Chat messages
CREATE TABLE chat_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    sources     TEXT,                     -- JSON array of chunk IDs used
    model_used  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Model configurations
CREATE TABLE model_configs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    provider    TEXT NOT NULL,            -- ollama | openai | anthropic | google
    model_id    TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT FALSE,
    is_default  BOOLEAN DEFAULT FALSE,
    config      TEXT                      -- JSON: temperature, max_tokens, etc.
);
```

### ChromaDB — Vector Collections

```
Collection: "documents"
  - id:        chunk UUID
  - embedding: float[] (768-dim for nomic-embed-text)
  - metadata: {
      document_id: str,
      chunk_index:  int,
      page_number:  int,
      source_title: str,
      file_type:    str
    }
  - document:  chunk text content
```

---

## API Contract

### Ingestion

```
POST /api/v1/ingest/file
  Content-Type: multipart/form-data
  Body: { file: File, notebook_id?: string }
  Response: {
    document_id: string,
    status: "processing",
    estimated_time: number
  }

GET /api/v1/ingest/status/{document_id}
  Response: {
    document_id: string,
    status: "pending" | "processing" | "indexed" | "failed",
    progress: number,        // 0-100
    chunks_created: number,
    error?: string
  }

POST /api/v1/ingest/url          # Phase 2
  Body: { url: string }
```

### Documents

```
GET /api/v1/documents
  Query: ?page=1&limit=20&search=string&type=pdf
  Response: {
    documents: Document[],
    total: number,
    page: number
  }

GET /api/v1/documents/{id}
  Response: Document (full metadata + chunks summary)

DELETE /api/v1/documents/{id}
  Response: { success: boolean }
```

### Search

```
POST /api/v1/search
  Body: {
    query: string,
    top_k: number,          // default: 5
    document_ids?: string[] // filter to specific docs
  }
  Response: {
    results: [
      {
        chunk_id: string,
        content: string,
        score: float,
        document_id: string,
        document_title: string,
        page_number: int
      }
    ]
  }
```

### Chat

```
POST /api/v1/chat
  Body: {
    session_id?: string,    // omit to create new session
    message: string,
    model?: string,         // override active model
    document_ids?: string[] // scope to specific docs
  }
  Response: Server-Sent Events (SSE) stream
    data: { type: "chunk", content: "..." }
    data: { type: "sources", sources: [{ chunk_id, title, page }] }
    data: { type: "done", session_id: "..." }

GET /api/v1/chat/sessions
  Response: { sessions: ChatSession[] }

GET /api/v1/chat/sessions/{id}
  Response: { session: ChatSession, messages: ChatMessage[] }

DELETE /api/v1/chat/sessions/{id}
```

### Models

```
GET /api/v1/models
  Response: {
    available: ModelConfig[],
    active: ModelConfig
  }

POST /api/v1/models/switch
  Body: { model_id: string }

GET /api/v1/models/ollama/available
  Response: { models: string[] }  // from Ollama local API
```

### Graph (Phase 3)

```
GET /api/v1/graph
  Query: ?document_ids=id1,id2&depth=2
  Response: {
    nodes: [{ id, label, type, weight }],
    edges: [{ source, target, label, weight }]
  }
```

---

## MVP Definition

> **Scope**: Everything needed for a working "chat with your PDFs" system.

### ✅ Phase 1 — MVP (Weeks 1–2)
**Goal**: Upload PDF → Chat with it using local LLM

| Module | Technology | Status |
|--------|-----------|--------|
| FastAPI backend skeleton | FastAPI + Uvicorn | Phase 1 |
| PDF text extraction | PyMuPDF (fitz) | Phase 1 |
| Text cleaning | regex + custom | Phase 1 |
| Chunking engine | LangChain TextSplitter or custom | Phase 1 |
| Embedding | Ollama `nomic-embed-text` | Phase 1 |
| Vector storage | ChromaDB (persistent) | Phase 1 |
| Metadata storage | SQLite (aiosqlite) | Phase 1 |
| RAG retrieval | ChromaDB cosine search | Phase 1 |
| Chat engine | Ollama `llama3` | Phase 1 |
| Streaming responses | SSE (FastAPI StreamingResponse) | Phase 1 |
| File upload UI | SvelteKit + drag-drop | Phase 1 |
| Chat interface | SvelteKit | Phase 1 |
| Document library | SvelteKit | Phase 1 |
| Source citation viewer | SvelteKit | Phase 1 |

### 🔄 Phase 2 — Extended Ingestion + Cloud (Weeks 3–4)
- Web URL ingestion (BeautifulSoup4 + trafilatura)
- DOCX ingestion (python-docx)
- Excel ingestion (openpyxl)
- Image OCR (Tesseract + Pillow)
- Cloud model router (OpenAI GPT-4o, Claude, Gemini)
- API key management UI
- Model switching UI with cost warnings

### 🔮 Phase 3 — Intelligence Layer (Weeks 5–6)
- Knowledge graph builder (NetworkX)
- Graph visualization (D3.js or Cytoscape in SvelteKit)
- Literature gap detection
- Methodology suggestion engine
- Concept clustering (UMAP/HDBSCAN)

### 🚀 Phase 4 — Polish & Production (Week 7+)
- Notebook/project management (multi-notebook)
- Export (PDF reports, citations)
- Tauri desktop wrapper
- Background job queue (Celery or ARQ)
- Prometheus metrics + logging

---

## Implementation Phases — Execution Order

### Phase 1 Execution Steps

```
Step 1:  Backend project setup + dependencies
Step 2:  Config, logging, database init (SQLite + ChromaDB)
Step 3:  PDF extractor service
Step 4:  Text cleaner + chunker
Step 5:  Embedder (Ollama nomic-embed-text)
Step 6:  ChromaDB storage layer
Step 7:  Ingestion API endpoint (POST /ingest/file)
Step 8:  RAG retrieval service
Step 9:  Ollama chat client (streaming)
Step 10: Chat API endpoint (SSE streaming)
Step 11: Document listing API
Step 12: SvelteKit frontend scaffold
Step 13: FileDropzone upload component
Step 14: Document library page
Step 15: Chat interface + SSE streaming client
Step 16: Source citation display
Step 17: Integration test (upload PDF → chat)
Step 18: docker-compose for full stack
```

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vector DB | ChromaDB | Zero-config, local-first, Python-native, production-ready |
| Embedding model | `nomic-embed-text` via Ollama | Runs locally, 768-dim, excellent quality |
| LLM | Ollama (`llama3.2` or `mistral`) | Privacy-first, no cloud dependency for MVP |
| Chunking | Recursive character splitter (512 tokens, 64 overlap) | Balance between context and precision |
| Chat protocol | SSE streaming | Better UX than polling, simpler than WebSockets for one-way |
| Metadata store | SQLite | Lightweight, zero-config, perfect for local-first |
| File handling | Async background tasks | Non-blocking ingestion via FastAPI BackgroundTasks |
| Cloud isolation | Structured chunks only | Raw documents NEVER leave the local machine |
| Frontend framework | SvelteKit | Lightweight, fast, excellent DX, built-in routing |

---

## Decisions

| Question | Decision |
|----------|----------|
| Primary LLM | `llama3.2:3b` (speed-focused) |
| Embedding model | `nomic-embed-text` via Ollama |
| Chunking | 1024 tokens, 128 overlap |
| Python env | `uv` |
| Cloud models | Scaffold stubs (inactive) |
| Auth | Basic auth |

---

## Verification Plan

### Phase 1 Acceptance Criteria
- [ ] `POST /api/v1/ingest/file` accepts a PDF and returns a document ID
- [ ] `GET /api/v1/ingest/status/{id}` shows progress to "indexed"
- [ ] `POST /api/v1/search` returns semantically relevant chunks
- [ ] `POST /api/v1/chat` streams a coherent response citing the uploaded PDF
- [ ] Frontend upload UI accepts drag-and-drop PDF
- [ ] Chat UI displays streamed response with source citations
- [ ] All services start cleanly with `docker-compose up`
