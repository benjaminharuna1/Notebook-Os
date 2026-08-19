# Notebook AI OS — Full System Architecture

## Overview

**Notebook AI OS** is a local-first AI research assistant that ingests, processes, understands, and reasons over research materials entirely on-device. Cloud models are optionally used as reasoning accelerators — they only ever receive structured, processed context, never raw documents.

The system follows a strict layered architecture with clean separation between ingestion, storage, retrieval, AI routing, and UI.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SvelteKit)                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐    │
│  │Auth  │ │Chat  │ │Upload│ │Graph │ │Model │ │Literature│    │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘    │
└─────┼────────┼────────┼────────┼────────┼──────────┼───────────┘
      │        │        │        │        │          │
      └────────┴────────┴────────┴────────┴──────────┘
                                │ HTTP/REST + SSE
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │   AUTH   │  │ PROJECTS │  │SETTINGS  │  │   MODELS     │    │
│  │JWT+CORS  │  │ CRUD     │  │per-user  │  │Ollama/Local/ │    │
│  └──────────┘  └──────────┘  └──────────┘  │Cloud routing │    │
│                                             └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │  INGESTION   │─▶│  PROCESSING  │─▶│   EMBEDDING      │      │
│  │ PDF upload   │  │ chunk/clean  │  │ fastembed/Ollama │      │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘      │
│                                               │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────▼─────────┐      │
│  │ AI ROUTER    │◀─│   RETRIEVAL  │◀─│   VECTOR STORE   │      │
│  │ local/cloud  │  │ semantic +   │  │    (ChromaDB)    │      │
│  └──────┬───────┘  │ keyword      │  └──────────────────┘      │
│         │          └──────────────┘                              │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │  CHAT ENGINE │  │ GRAPH BUILDER│  │  LITERATURE MAP  │      │
│  │  context +   │  │ (NetworkX +  │  │  citation graph  │      │
│  │  RAG + SSE   │  │  LLM)        │  │  + metadata      │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │   SKILLS     │  │   ACTIONS    │  │  DOCUMENTS       │      │
│  │ 8 AI skills  │  │ bg job       │  │  CRUD + file     │      │
│  │ (JSON defs)  │  │ tracking     │  │  serving         │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌──────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ LOCAL MODELS │   │  LOCAL STORAGE  │   │   OPTIONAL CLOUD     │
│  llama-cpp   │   │ ChromaDB + Files│   │  OpenAI/Claude/Gemini│
│  (GGUF)      │   │  SQLite metadata│   │  (structured ctx only)│
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
  - Extract metadata (title, author, year, DOI)
      │
      ▼
[Processing Layer]
  - Clean text (remove noise, headers, footers)
  - Chunk text (configurable: default 1024 tokens, 128 overlap)
  - Generate chunk metadata (page, source, position)
      │
      ▼
[Embedding Engine]
  - Embed each chunk via fastembed (local) or Ollama
  - Store embeddings → ChromaDB
  - Store metadata → SQLite
      │
      ▼
[Vector Store - ChromaDB]
  - Persistent local vector database
  - Collections per project
      │
      ▼
[Retrieval Layer]
  - Semantic: cosine similarity search → top-k chunks
  - Keyword: SQLite LIKE across chunks, ranked by token overlap
  - Merge: semantic first, keyword fills gaps, deduplicated
      │
      ▼
[AI Router]
  - Route to Ollama, local GGUF, or cloud model
  - Never send raw documents to cloud
  - Only send structured chunks + question
      │
      ▼
[Chat Engine]
  - System prompt + context + history + skills
  - Stream response to frontend via SSE
  - Store chat history in SQLite
  - Auto-learn: extract topics, preferences, references
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
│   │   │   ├── database.py                # SQLite schema + ChromaDB init & session management
│   │   │   ├── dependencies.py            # FastAPI shared Depends() (get_current_user, get_db)
│   │   │   ├── security.py                # Auth helpers (JWT, password hashing)
│   │   │   ├── events.py                  # App startup/shutdown lifecycle hooks
│   │   │   ├── exceptions.py              # Global exception handlers (AppException)
│   │   │   └── ratelimit.py               # Per-IP rate limiting
│   │   │
│   │   ├── shared/                        # Reusable utilities, no business logic
│   │   │   ├── __init__.py
│   │   │   ├── logger.py                  # Structured logging setup
│   │   │   ├── file_utils.py              # Path helpers, MIME detection
│   │   │   ├── text_utils.py              # Text cleaning, normalisation
│   │   │   └── id_utils.py               # UUID generation helpers
│   │   │
│   │   └── features/                      # ← FEATURE-BASED MODULES (15 features)
│   │       │
│   │       ├── auth/                      # Feature: user authentication (JWT + cookies)
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /auth/register, /auth/login, /auth/logout, GET /auth/me
│   │       │   ├── service.py             # Register, login, password verification
│   │       │   ├── schemas.py             # RegisterRequest, LoginRequest, AuthResponse
│   │       │   └── tests/
│   │       │       └── test_service.py
│   │       │
│   │       ├── projects/                  # Feature: workspace management (CRUD)
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # CRUD /projects endpoints
│   │       │   ├── service.py             # ProjectService: CRUD + cascade deletion
│   │       │   ├── repository.py          # SQLite queries for projects
│   │       │   ├── schemas.py             # Project, ProjectCreate, ProjectUpdate
│   │       │   └── tests/
│   │       │       └── test_service.py
│   │       │
│   │       ├── ingestion/                 # Feature: PDF upload and processing pipeline
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /ingest/file, GET /ingest/status/{id}, pause, resume, reprocess
│   │       │   ├── service.py             # IngestionService: full pipeline orchestration
│   │       │   ├── schemas.py             # IngestionResponse, IngestionStatus, BatchReprocess
│   │       │   ├── extractors/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── base.py            # BaseExtractor ABC
│   │       │   │   └── pdf.py             # PyMuPDF extraction
│   │       │   ├── jobs.py                # Background job_manager for pipeline
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_service.py
│   │       │
│   │       ├── processing/                # Feature: chunk & clean extracted text
│   │       │   ├── __init__.py
│   │       │   ├── service.py             # ProcessingService: chunking orchestration
│   │       │   ├── schemas.py
│   │       │   ├── chunker.py             # Recursive character chunker (configurable size/overlap)
│   │       │   ├── cleaner.py             # Noise removal, deduplication
│   │       │   └── tests/
│   │       │       └── test_chunker.py
│   │       │
│   │       ├── embedding/                 # Feature: embed chunks → vector store
│   │       │   ├── __init__.py
│   │       │   ├── service.py             # EmbeddingService: batch embedding orchestration
│   │       │   ├── schemas.py
│   │       │   ├── providers/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── base.py            # BaseEmbeddingProvider ABC
│   │       │   │   ├── fastembed.py       # fastembed (local, default)
│   │       │   │   └── ollama.py          # nomic-embed-text via Ollama
│   │       │   └── tests/
│   │       │       └── test_embedding.py
│   │       │
│   │       ├── documents/                 # Feature: document CRUD and file management
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /documents, DELETE, batch delete, file serve, orphans
│   │       │   ├── service.py             # DocumentService: CRUD, file serving, orphan management
│   │       │   ├── repository.py          # SQLite queries for documents
│   │       │   ├── schemas.py
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       ├── test_repository.py
│   │       │       ├── test_batch_delete.py
│   │       │       └── test_file_serving.py
│   │       │
│   │       ├── search/                    # Feature: semantic + keyword retrieval
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /search
│   │       │   ├── service.py             # SearchService: semantic + keyword merge
│   │       │   ├── schemas.py             # SearchRequest, SearchResponse
│   │       │   ├── vector_store.py        # ChromaDB read/write abstraction
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_vector_store.py
│   │       │
│   │       ├── chat/                      # Feature: context-aware AI conversation
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # POST /chat, GET/PATCH/DELETE /chat/sessions
│   │       │   ├── service.py             # ChatService: search + context + stream + auto-learn
│   │       │   ├── schemas.py             # ChatRequest
│   │       │   ├── repository.py          # SQLite: sessions + messages + project_memory
│   │       │   ├── prompt_builder.py      # System prompt assembly with APA rules
│   │       │   ├── web_search.py          # DuckDuckGo HTML scraper for reference fallback
│   │       │   └── tests/
│   │       │       ├── test_router.py
│   │       │       └── test_service.py
│   │       │
│   │       ├── graph/                     # Feature: knowledge graph from indexed papers
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /graph, history, themes, tracked concepts, concept summary
│   │       │   ├── service.py             # GraphService: build, checkpoint, themes
│   │       │   ├── schemas.py             # GraphResponse, GraphCheckpoint, TrackedConcept, etc.
│   │       │   ├── builder.py             # GraphBuilder: concept extraction, node/edge creation, layout
│   │       │   ├── llm_service.py         # GraphLLMService: query refinement, concept summaries
│   │       │   ├── tracked_service.py     # CRUD for user-tracked concepts
│   │       │   ├── jobs.py                # Background graph generation via actions registry
│   │       │   └── tests/
│   │       │       ├── test_builder.py
│   │       │       ├── test_graph_history.py
│   │       │       ├── test_graph_cache.py
│   │       │       ├── test_themes.py
│   │       │       ├── test_graph_llm.py
│   │       │       └── test_tracked.py
│   │       │
│   │       ├── literature/                # Feature: paper-level literature mapping
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # Literature map, entries, metadata, export, summaries
│   │       │   ├── service.py             # LiteratureService: map build, enrichment, entries, APA
│   │       │   ├── llm_service.py         # LiteratureLLMService: metadata extraction, summaries
│   │       │   ├── metadata.py            # Crossref/OpenAlex lookup, DOI extraction
│   │       │   ├── jobs.py                # Background literature map builds
│   │       │   ├── schemas.py             # LiteratureEntry, LiteratureMapResponse, etc.
│   │       │   └── tests/
│   │       │       ├── test_literature.py
│   │       │       ├── test_literature_entries.py
│   │       │       └── test_metadata_sources.py
│   │       │
│   │       ├── models/                    # Feature: LLM provider management
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /models, POST /models/switch, catalog, downloads
│   │       │   ├── service.py             # ModelService: listing, switching, provider factory
│   │       │   ├── schemas.py             # SwitchModelRequest, DownloadModelRequest
│   │       │   ├── repository.py          # SQLite CRUD for model_configs
│   │       │   ├── catalog.py             # Device tier recommendations, cloud presets
│   │       │   ├── downloads.py           # HuggingFace GGUF download manager
│   │       │   ├── providers/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── ollama.py          # Ollama API provider
│   │       │   │   ├── local.py           # Local GGUF provider (llama-cpp-python)
│   │       │   │   ├── openai.py          # OpenAI API provider
│   │       │   │   ├── anthropic.py       # Anthropic API provider
│   │       │   │   └── google.py          # Google Gemini API provider
│   │       │   └── tests/
│   │       │       └── test_router.py
│   │       │
│   │       ├── skills/                    # Feature: AI skill system
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /skills, /skills/catalog, install, enable, uninstall, import
│   │       │   ├── service.py             # SkillsService: catalog, CRUD, keyword detection
│   │       │   ├── schemas.py             # SkillManifest, SkillInstallRequest, SkillEnableRequest
│   │       │   └── tests/
│   │       │       └── test_service.py
│   │       │
│   │       ├── settings/                  # Feature: user preferences
│   │       │   ├── __init__.py
│   │       │   ├── router.py              # GET /settings, PUT /settings
│   │       │   ├── service.py             # SettingsService: get/update with encryption + tier defaults
│   │       │   ├── schemas.py             # SettingsUpdate, SettingsResponse
│   │       │   ├── defaults.py            # Device tier defaults (low/medium/high)
│   │       │   └── tests/
│   │       │       └── test_service.py
│   │       │
│   │       └── actions/                   # Feature: background job registry
│   │           ├── __init__.py
│   │           ├── router.py              # GET /actions, POST pause/resume
│   │           ├── registry.py            # In-memory action registry, slot management, pause events
│   │           └── tests/
│   │               └── test_registry.py
│   │
│   ├── skills/                            # 8 AI skill definitions (JSON manifests)
│   │   ├── citation-formatter.json
│   │   ├── critical-thinking.json
│   │   ├── hypothesis-brainstorm.json
│   │   ├── literature-mapping.json
│   │   ├── literature-review.json
│   │   ├── research-workflow.json
│   │   ├── source-evaluation.json
│   │   └── summarize.json
│   │
│   ├── _system/                           # System-level prompts and schemas
│   │   └── prompts/
│   │       ├── base_system.md             # Core LLM rules for chat
│   │       ├── apa_citation.md            # APA 7th edition citation rules
│   │       ├── reference_handling.md      # Reference fallback instructions
│   │       └── secondary_sources.md       # Secondary source handling
│   │
│   ├── data/                              # Runtime data (gitignored)
│   │   ├── uploads/                       # Raw uploaded files
│   │   ├── processed/                     # Extracted text artifacts
│   │   ├── chroma_db/                     # ChromaDB persistence
│   │   └── notebook.db                    # SQLite database
│   │
│   ├── tests/                             # Backend tests
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app.css                        # Global design tokens & resets
│   │   ├── app.html                       # SvelteKit HTML shell
│   │   │
│   │   ├── lib/
│   │   │   ├── core/                      # Shared non-feature code
│   │   │   │   ├── api/
│   │   │   │   │   └── client.ts          # Base fetch wrapper (auth, errors, SSE)
│   │   │   │   ├── components/
│   │   │   │   │   ├── ui/                # Headless/generic UI primitives
│   │   │   │   │   └── layout/            # AppShell, Sidebar, Header
│   │   │   │   └── stores/
│   │   │   │       └── toasts.ts          # Global notification store
│   │   │   │
│   │   │   └── features/                  # ← FEATURE-BASED MODULES (12 features)
│   │   │       │
│   │   │       ├── auth/                  # Login/register UI
│   │   │       │   ├── api.ts
│   │   │       │   └── components/
│   │   │       │
│   │   │       ├── projects/              # Project selector/CRUD UI
│   │   │       │   ├── api.ts
│   │   │       │   └── components/
│   │   │       │
│   │   │       ├── ingestion/             # File upload & processing status
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── FileDropzone.svelte
│   │   │       │       ├── UploadQueue.svelte
│   │   │       │       └── UploadProgress.svelte
│   │   │       │
│   │   │       ├── documents/             # Document library
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── DocumentList.svelte
│   │   │       │       ├── DocumentCard.svelte
│   │   │       │       └── DocumentDetail.svelte
│   │   │       │
│   │   │       ├── search/                # Semantic search
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── SearchBar.svelte
│   │   │       │       └── SearchResults.svelte
│   │   │       │
│   │   │       ├── chat/                  # AI chat interface
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
│   │   │       ├── graph/                 # Knowledge graph visualization
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── KnowledgeGraph.svelte
│   │   │       │       └── GraphControls.svelte
│   │   │       │
│   │   │       ├── literature/            # Literature mapping UI
│   │   │       │   ├── api.ts
│   │   │       │   └── components/
│   │   │       │
│   │   │       ├── models/                # Model selector & switching
│   │   │       │   ├── api.ts
│   │   │       │   ├── store.ts
│   │   │       │   ├── types.ts
│   │   │       │   └── components/
│   │   │       │       ├── ModelSelector.svelte
│   │   │       │       └── ModelBadge.svelte
│   │   │       │
│   │   │       ├── skills/                # Skill catalog & management UI
│   │   │       │   ├── api.ts
│   │   │       │   └── components/
│   │   │       │
│   │   │       ├── settings/              # User preferences UI
│   │   │       │   ├── api.ts
│   │   │       │   └── components/
│   │   │       │
│   │   │       └── actions/               # Background action status UI
│   │   │           ├── api.ts
│   │   │           └── components/
│   │   │
│   │   └── routes/                        # SvelteKit file-based routing
│   │       ├── +layout.svelte             # Root layout (AppShell)
│   │       ├── +page.svelte               # / → redirects to /chat
│   │       ├── login/                     # /login — auth page
│   │       │   └── +page.svelte
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
│   │       ├── graph/
│   │       │   └── +page.svelte           # /graph — knowledge graph
│   │       └── settings/
│   │           └── +page.svelte           # /settings — user preferences
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

| Concern | Layer-Based (old) | Feature-Based (current) |
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
-- Users table
CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- User settings (JSON blob)
CREATE TABLE user_settings (
    user_id   TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    settings  TEXT NOT NULL DEFAULT '{}'
);

-- Projects (workspaces grouping documents)
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Documents (metadata for all ingested files)
CREATE TABLE documents (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id            TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title                 TEXT NOT NULL,
    filename              TEXT NOT NULL,
    file_path             TEXT NOT NULL,
    file_type             TEXT NOT NULL,
    file_size             INTEGER,
    page_count            INTEGER,
    source_url            TEXT,
    author                TEXT,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    indexed_at            DATETIME,
    status                TEXT DEFAULT 'pending',
    error                 TEXT,
    year                  INTEGER,
    doi                   TEXT,
    abstract              TEXT,
    authors               TEXT,
    verification_status   TEXT,
    apa_reference         TEXT,
    metadata_user_edited  INTEGER DEFAULT 0,
    extracted_doi         TEXT,
    metadata_candidates   TEXT,
    paper_type            TEXT,
    edition               TEXT,
    issn                  TEXT,
    isbn                  TEXT
);

-- Chunks (processed text units)
CREATE TABLE chunks (
    id          TEXT PRIMARY KEY,
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
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id  TEXT REFERENCES projects(id) ON DELETE CASCADE,
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
    sources     TEXT,
    model_used  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Model configurations
CREATE TABLE model_configs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT FALSE,
    is_default  BOOLEAN DEFAULT FALSE,
    config      TEXT
);

-- User skills (installed AI skill definitions)
CREATE TABLE user_skills (
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id     TEXT NOT NULL,
    manifest     TEXT NOT NULL,
    enabled      INTEGER DEFAULT 1,
    installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, skill_id)
);

-- Tracked concepts (user-curated concept list for graph)
CREATE TABLE tracked_concepts (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    concept     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, project_id, concept)
);

-- Graph history (checkpoints of generated knowledge graphs)
CREATE TABLE graph_history (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    project_id  TEXT NOT NULL,
    graph_json  TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    prefs_key   TEXT NOT NULL,
    is_favourite INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 0,
    map_type    TEXT DEFAULT 'concepts',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Paper references (in-text citations found in papers)
CREATE TABLE paper_references (
    id               TEXT PRIMARY KEY,
    paper_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    raw_ref          TEXT NOT NULL,
    matched_paper_id TEXT,
    confidence       REAL
);

-- Literature entries (per-paper literature mapping)
CREATE TABLE literature_entries (
    paper_id           TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    user_id            TEXT NOT NULL,
    project_id         TEXT NOT NULL,
    citation           TEXT,
    research_objective TEXT,
    methodology        TEXT,
    key_findings       TEXT,
    limitations        TEXT,
    relevance          TEXT,
    apa_reference      TEXT,
    auto_generated     INTEGER NOT NULL DEFAULT 0,
    user_edited        TEXT,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Project memory (learned insights from chat interactions)
CREATE TABLE project_memory (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    source      TEXT DEFAULT 'chat',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, key)
);
```

**Indexes:**
```sql
idx_documents_project       ON documents(project_id)
idx_chat_sessions_project   ON chat_sessions(project_id)
idx_chat_messages_session   ON chat_messages(session_id)
idx_graph_history_lookup    ON graph_history(user_id, project_id, created_at)
idx_graph_history_map       ON graph_history(user_id, project_id, map_type, created_at)
idx_paper_references_paper  ON paper_references(paper_id)
idx_paper_references_matched ON paper_references(matched_paper_id)
idx_literature_entries_project ON literature_entries(user_id, project_id)
idx_project_memory_project  ON project_memory(project_id, updated_at DESC)
```

### ChromaDB — Vector Collections

```
Collection: "documents"
  - id:        chunk UUID
  - embedding: float[] (384-dim for fastembed / 768-dim for nomic-embed-text)
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

All endpoints are prefixed with `/api/v1`. All endpoints (except auth) require JWT authentication via cookie or header.

### Auth

```
POST /api/v1/auth/register
  Body: { email: string, username: string, password: string }
  Response: { token: string, user: { id, email, username } }

POST /api/v1/auth/login
  Body: { identifier: string, password: string }
  Response: { token: string, user: { id, email, username } }
  Sets: HttpOnly access_token cookie

POST /api/v1/auth/logout
  Clears access_token cookie
  Response: { success: true }

GET /api/v1/auth/me
  Response: { id, email, username }
```

### Projects

```
POST /api/v1/projects
  Body: { name: string, description?: string }
  Response: Project { id, name, description, created_at, updated_at }

GET /api/v1/projects
  Response: { projects: Project[] }

GET /api/v1/projects/{project_id}
  Response: Project

PATCH /api/v1/projects/{project_id}
  Body: { name?: string, description?: string }
  Response: Project

DELETE /api/v1/projects/{project_id}
  Response: { success: true }
```

### Ingestion

```
POST /api/v1/ingest/file
  Content-Type: multipart/form-data
  Body: { file: File, project_id?: string }
  Response: { document_id: string, status: "processing", estimated_time: number }

GET /api/v1/ingest/status/{document_id}
  Response: { document_id: string, status: "pending"|"processing"|"indexed"|"failed"|"paused", progress: number, error?: string }

POST /api/v1/ingest/{document_id}/pause
POST /api/v1/ingest/{document_id}/resume
POST /api/v1/ingest/{document_id}/reprocess

POST /api/v1/ingest/reprocess
  Body: { document_ids: string[] }
  Response: { success: true, processed: number, errors: [] }
```

### Documents

```
GET /api/v1/documents
  Query: ?page=1&limit=20&search=string&file_type=string&project_id=string
  Response: { documents: Document[], total: number, page: number, pages: number }

GET /api/v1/documents/{document_id}
  Response: Document (full metadata + chunk_count)

DELETE /api/v1/documents/{document_id}
  Response: { success: true }

POST /api/v1/projects/{project_id}/documents/batch/delete
  Body: { document_ids: string[] }

GET /api/v1/projects/{project_id}/documents/{document_id}/file
  Response: FileResponse (PDF/DOCX/etc)

GET /api/v1/projects/{project_id}/documents/orphans
POST /api/v1/projects/{project_id}/documents/clean-orphans
```

### Search

```
POST /api/v1/search
  Body: {
    query: string,
    top_k?: number,           // default: 15
    project_id?: string,
    document_ids?: string[]
  }
  Response: {
    results: [{
      chunk_id: string,
      content: string,
      score: float,
      document_id: string,
      document_title: string,
      page_number: int
    }]
  }
```

### Chat

```
POST /api/v1/chat
  Body: {
    session_id?: string,
    message: string,
    project_id?: string,
    model?: string,
    slash_command?: string,
    regenerate?: boolean
  }
  Response: Server-Sent Events (SSE) stream
    data: { type: "chunk", content: "..." }
    data: { type: "sources", sources: [{ title, page, doc_id, snippet }] }
    data: { type: "done", session_id: "..." }
    data: { type: "error", detail: "..." }

GET /api/v1/chat/sessions?project_id=string
  Response: { sessions: ChatSession[] }

GET /api/v1/chat/sessions/{session_id}
  Response: { session: ChatSession, messages: ChatMessage[] }

PATCH /api/v1/chat/sessions/{session_id}
  Body: { title: string }

DELETE /api/v1/chat/sessions/{session_id}
```

### Graph

```
GET /api/v1/graph
  Query: ?document_ids=id1,id2&depth=2&project_id=string&force=false
  Response: { nodes: [{ id, label, x, y, ... }], edges: [{ source, target, weight }] }

POST /api/v1/graph/generate
  Body: { project_id, document_ids?, depth?, force? }
  Response: { id, kind, status, ... }

GET /api/v1/graph/history?project_id=string
  Response: { checkpoints: [{ id, created_at, is_favourite, ... }] }

GET /api/v1/graph/history/{checkpoint_id}
PATCH /api/v1/graph/history/{checkpoint_id}
DELETE /api/v1/graph/history/{checkpoint_id}

POST /api/v1/graph/search
  Body: { project_id, query }
  Response: { refined_query, ... }

POST /api/v1/graph/concepts/summary
  Body: { project_id, label }
  Response: SSE stream (concept summary with sources)

GET /api/v1/graph/themes?project_id=string&limit=5
  Response: { documents: [{ doc_id, doc_name, themes: [{ concept, count }] }] }

GET /api/v1/graph/concepts/tracked?project_id=string
POST /api/v1/graph/concepts/tracked  (Body: { project_id, concept })
DELETE /api/v1/graph/concepts/tracked/{concept_id}
```

### Literature

```
GET /api/v1/projects/{project_id}/literature/status
POST /api/v1/projects/{project_id}/literature/build
GET /api/v1/projects/{project_id}/literature/jobs/{job_id}

GET /api/v1/projects/{project_id}/literature/map
  Response: { nodes: [PaperNode], edges: [PaperEdge], clusters }

GET /api/v1/projects/{project_id}/literature/entries
GET /api/v1/projects/{project_id}/literature/entries/{paper_id}
PATCH /api/v1/projects/{project_id}/literature/entries/{paper_id}
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/regenerate
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/summarize

GET /api/v1/projects/{project_id}/literature/entries/{paper_id}/metadata
PATCH /api/v1/projects/{project_id}/literature/entries/{paper_id}/metadata
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/candidates/apply

POST /api/v1/projects/{project_id}/literature/regenerate
POST /api/v1/projects/{project_id}/literature/clusters/summary

GET /api/v1/projects/{project_id}/literature/export
  Response: XLSX binary download

GET /api/v1/projects/{project_id}/literature/references/export.docx
  Response: DOCX binary download (APA references list)
```

### Models

```
GET /api/v1/models
  Response: { available: ModelConfig[], active: ModelConfig }

POST /api/v1/models/switch
  Body: { model_id: string }  // format: "provider:model_name"

GET /api/v1/models/ollama/available
  Response: { models: string[] }

GET /api/v1/models/catalog
  Response: { recommendations, presets, downloads }

POST /api/v1/models/hf/download
  Body: { key: string }
  Response: download status

GET /api/v1/models/hf/downloads
  Response: { downloads: [...] }

GET /api/v1/local/status
  Response: { ollama_running, recommended_models, ... }
```

### Skills

```
GET /api/v1/skills
  Response: { skills: [{ skill: manifest, enabled, installed_at }] }

GET /api/v1/skills/catalog
  Response: { catalog: [{ skill: manifest, installed }] }

POST /api/v1/skills/install
  Body: { skill_id: string }

POST /api/v1/skills/{skill_id}/enable
  Body: { enabled: boolean }

DELETE /api/v1/skills/{skill_id}

POST /api/v1/skills/import
  Body: SkillManifest (custom skill definition)
```

### Settings

```
GET /api/v1/settings
  Response: { settings: { device_tier, default_llm, provider, chunk_size, ... } }

PUT /api/v1/settings
  Body: { ...partial settings update }
  Response: { settings: { ... } }
```

### Actions

```
GET /api/v1/actions
  Response: { actions: [{ id, kind, title, status, progress, stage, ... }] }

POST /api/v1/actions/{action_id}/pause
POST /api/v1/actions/{action_id}/resume
```

---

## Current State

> All core features are implemented and tested. The system is a working local-first research assistant.

### Implemented Features (15 backend / 12 frontend)

| # | Feature | Backend | Frontend | Description |
|---|---------|---------|----------|-------------|
| 1 | **Auth** | `features/auth/` | `features/auth/` | JWT registration, login, cookie auth |
| 2 | **Projects** | `features/projects/` | `features/projects/` | Workspace CRUD with cascade deletion |
| 3 | **Ingestion** | `features/ingestion/` | `features/ingestion/` | PDF upload, extract, pause/resume, reprocess |
| 4 | **Processing** | `features/processing/` | — | Text cleaning, recursive character chunking |
| 5 | **Embedding** | `features/embedding/` | — | fastembed (local) or Ollama embedding |
| 6 | **Documents** | `features/documents/` | `features/documents/` | CRUD, file serving, batch delete, orphan detection |
| 7 | **Search** | `features/search/` | `features/search/` | Semantic + keyword merge search |
| 8 | **Chat** | `features/chat/` | `features/chat/` | RAG chat with SSE streaming, auto-learn, project memory |
| 9 | **Graph** | `features/graph/` | `features/graph/` | Knowledge graph with checkpoints, themes, tracked concepts |
| 10 | **Literature** | `features/literature/` | `features/literature/` | Literature mapping, metadata enrichment, XLSX/DOCX export |
| 11 | **Models** | `features/models/` | `features/models/` | Ollama, local GGUF, OpenAI, Anthropic, Google providers |
| 12 | **Skills** | `features/skills/` | `features/skills/` | 8 installable AI skill definitions, keyword detection |
| 13 | **Settings** | `features/settings/` | `features/settings/` | Per-user preferences, device tier, encrypted API keys |
| 14 | **Actions** | `features/actions/` | `features/actions/` | Background job registry with pause/resume |
| 15 | — | — | `features/documents/` | *(Processing & embedding are backend-only pipeline stages)* |

### Key Technology Choices

| Component | Choice | Notes |
|-----------|--------|-------|
| Vector DB | ChromaDB (persistent) | Zero-config, local-first, Python-native |
| Embedding | fastembed (default) / Ollama nomic-embed-text | Local inference, configurable provider |
| LLM | llama-cpp-python (local GGUF) / Ollama / Cloud APIs | qwen2.5-0.5b default for local |
| Chunking | Recursive character splitter (1024 tokens, 128 overlap) | Configurable via settings |
| Chat protocol | SSE streaming | One-way stream, simpler than WebSockets |
| Metadata store | SQLite (raw aiosqlite) | Zero-config, WAL mode, foreign keys |
| Auth | JWT tokens + HttpOnly cookies | Rate-limited, per-user scoping |
| Search | Semantic (ChromaDB cosine) + keyword (SQLite LIKE) | Merged, deduplicated results |
| Frontend | SvelteKit + TypeScript + Tailwind | File-based routing, lightweight |
| Background jobs | In-memory registry (actions) | Pause/resume via threading.Event |
| Cloud isolation | Structured chunks only | Raw documents NEVER leave the local machine |

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vector DB | ChromaDB | Zero-config, local-first, Python-native, production-ready |
| Embedding | fastembed (default) | Local inference without Ollama dependency |
| LLM | llama-cpp-python with GGUF models | No Ollama required; qwen2.5-0.5b is tiny and fast |
| Cloud models | OpenAI / Anthropic / Google (opt-in) | Users enable per-account; raw docs never sent |
| Chunking | 1024 tokens, 128 overlap | Balance between context window and retrieval precision |
| Chat protocol | SSE streaming | Better UX than polling, simpler than WebSockets |
| Metadata store | SQLite with WAL mode | Lightweight, concurrent reads, zero-config |
| File handling | Background job_manager with pause/resume | Non-blocking ingestion with cooperative checkpoints |
| Auth | JWT + HttpOnly cookies | Secure, cookie-based for browser clients |
| Search | Semantic + keyword merge | Catches exact terms that semantic search misses |
| Prompt assembly | Token-budgeted sections | Prevents context overflow; configurable per section |
| Skill system | JSON manifests + keyword detection | Extensible without code changes |

---

## Verification Plan

### Test Suite

- **175 tests** across all features
- Run: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- Tests are co-located in each feature's `tests/` directory
- Coverage: auth, projects, ingestion, processing, embedding, documents, search, chat, graph (6 test files), literature (3 test files), models, skills, settings, actions

### Acceptance Criteria

- [x] `POST /api/v1/auth/register` creates user, returns JWT
- [x] `POST /api/v1/ingest/file` accepts a PDF and returns a document ID
- [x] `GET /api/v1/ingest/status/{id}` shows progress through queued → processing → indexed
- [x] `POST /api/v1/search` returns semantically relevant chunks (semantic + keyword merge)
- [x] `POST /api/v1/chat` streams a coherent response with APA citations via SSE
- [x] Chat auto-learned insights persist in project_memory table
- [x] Graph builds with checkpoints, themes, and tracked concepts
- [x] Literature mapping produces entries with metadata enrichment (Crossref/OpenAlex/LLM)
- [x] XLSX and DOCX exports work for literature mapping
- [x] Skills install, enable, and inject instructions into chat prompts
- [x] All services start cleanly with `docker-compose up`

### Feature Integrity Checks

```bash
# Run full test suite
cd backend && .venv\Scripts\python.exe -m pytest -q

# Verify no cross-feature imports
grep -r "from app.features" backend/app/features/ | grep -v __pycache__ | grep -v "from app.features.\w\+ import"

# Build frontend
cd frontend && npm run build
```

---

## ICM (Interpretable Context Methodology) Documentation Structure

Each feature has a `CONTEXT.md` file that serves as its ICM documentation, providing a self-contained reference that any AI agent can read to understand and work on that feature without slurping the entire codebase.

### Per-Feature CONTEXT.md Structure

Every `CONTEXT.md` follows this standardised format:

```markdown
# feature-name — one-line description

One job: single sentence describing the feature's purpose.

## Inputs
| Input | Source | Notes |
|---|---|---|

## Process
1. Step-by-step description of what the feature does

## Outputs
| Output | Type | Notes |
|---|---|---|

## Key files
| File | Purpose |
|---|---|

## Human check
- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
```

### Current ICM Files

| Feature | CONTEXT.md Location |
|---------|-------------------|
| Auth | `backend/app/features/auth/CONTEXT.md` |
| Projects | `backend/app/features/projects/CONTEXT.md` |
| Ingestion | `backend/app/features/ingestion/CONTEXT.md` |
| Processing | `backend/app/features/processing/CONTEXT.md` |
| Embedding | `backend/app/features/embedding/CONTEXT.md` |
| Documents | `backend/app/features/documents/CONTEXT.md` |
| Search | `backend/app/features/search/CONTEXT.md` |
| Chat | `backend/app/features/chat/CONTEXT.md` |
| Graph | `backend/app/features/graph/CONTEXT.md` |
| Literature | `backend/app/features/literature/CONTEXT.md` |
| Models | `backend/app/features/models/CONTEXT.md` |
| Skills | `backend/app/features/skills/CONTEXT.md` |
| Settings | `backend/app/features/settings/CONTEXT.md` |
| Actions | `backend/app/features/actions/CONTEXT.md` |

### System-Level Prompts

Located in `backend/_system/prompts/`:

| File | Purpose |
|------|---------|
| `base_system.md` | Core LLM rules for chat responses |
| `apa_citation.md` | APA 7th edition citation formatting rules |
| `reference_handling.md` | Reference fallback and verification instructions |
| `secondary_sources.md` | Secondary source handling instructions |

### Why ICM?

- **Agent-friendly**: Any AI agent can read one `CONTEXT.md` and immediately understand a feature's contract
- **No slurping**: Eliminates need to read entire codebase for small changes
- **Living documentation**: Always accurate because it lives next to the code it describes
- **Standardised**: Same format across all features means predictable navigation
