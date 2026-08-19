# Backend Structure

```
backend/
├── app/
│   ├── main.py                        # FastAPI app factory + feature router registration
│   │
│   ├── core/                          # Shared infrastructure (not feature-specific)
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic BaseSettings (.env loading)
│   │   ├── database.py                # SQLite schema + ChromaDB init & session management
│   │   ├── dependencies.py            # FastAPI shared Depends() (get_current_user, get_db)
│   │   ├── security.py                # Auth helpers (JWT, password hashing)
│   │   ├── events.py                  # App startup/shutdown lifecycle hooks
│   │   ├── exceptions.py              # Global exception handlers (AppException)
│   │   └── ratelimit.py               # Per-IP rate limiting
│   │
│   ├── shared/                        # Reusable utilities, no business logic
│   │   ├── __init__.py
│   │   ├── logger.py                  # Structured logging setup
│   │   ├── file_utils.py              # Path helpers, MIME detection
│   │   ├── text_utils.py              # Text cleaning, normalisation
│   │   └── id_utils.py               # UUID generation helpers
│   │
│   └── features/                      # ← FEATURE-BASED MODULES (15 features)
│       │
│       ├── auth/                      # Feature: user authentication (JWT + cookies)
│       │   ├── __init__.py
│       │   ├── router.py              # POST /auth/register, /auth/login, /auth/logout, GET /auth/me
│       │   ├── service.py             # Register, login, password verification
│       │   ├── schemas.py             # RegisterRequest, LoginRequest, AuthResponse
│       │   └── tests/
│       │       └── test_service.py
│       │
│       ├── projects/                  # Feature: workspace management (CRUD)
│       │   ├── __init__.py
│       │   ├── router.py              # CRUD /projects endpoints
│       │   ├── service.py             # ProjectService: CRUD + cascade deletion
│       │   ├── repository.py          # SQLite queries for projects
│       │   ├── schemas.py             # Project, ProjectCreate, ProjectUpdate
│       │   └── tests/
│       │       └── test_service.py
│       │
│       ├── ingestion/                 # Feature: PDF upload and processing pipeline
│       │   ├── __init__.py
│       │   ├── router.py              # POST /ingest/file, GET /ingest/status/{id}, pause, resume, reprocess
│       │   ├── service.py             # IngestionService: full pipeline orchestration
│       │   ├── schemas.py             # IngestionResponse, IngestionStatus, BatchReprocess
│       │   ├── extractors/
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # BaseExtractor ABC
│       │   │   └── pdf.py             # PyMuPDF extraction
│       │   ├── jobs.py                # Background job_manager for pipeline
│       │   └── tests/
│       │       ├── test_router.py
│       │       └── test_service.py
│       │
│       ├── processing/                # Feature: chunk & clean extracted text
│       │   ├── __init__.py
│       │   ├── service.py             # ProcessingService: chunking orchestration
│       │   ├── schemas.py
│       │   ├── chunker.py             # Recursive character chunker (configurable size/overlap)
│       │   ├── cleaner.py             # Noise removal, deduplication
│       │   └── tests/
│       │       └── test_chunker.py
│       │
│       ├── embedding/                 # Feature: embed chunks → vector store
│       │   ├── __init__.py
│       │   ├── service.py             # EmbeddingService: batch embedding orchestration
│       │   ├── schemas.py
│       │   ├── providers/
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # BaseEmbeddingProvider ABC
│       │   │   ├── fastembed.py       # fastembed (local, default)
│       │   │   └── ollama.py          # nomic-embed-text via Ollama
│       │   └── tests/
│       │       └── test_embedding.py
│       │
│       ├── documents/                 # Feature: document CRUD and file management
│       │   ├── __init__.py
│       │   ├── router.py              # GET /documents, DELETE, batch delete, file serve, orphans
│       │   ├── service.py             # DocumentService: CRUD, file serving, orphan management
│       │   ├── repository.py          # SQLite queries for documents
│       │   ├── schemas.py
│       │   └── tests/
│       │       ├── test_router.py
│       │       ├── test_repository.py
│       │       ├── test_batch_delete.py
│       │       └── test_file_serving.py
│       │
│       ├── search/                    # Feature: semantic + keyword retrieval
│       │   ├── __init__.py
│       │   ├── router.py              # POST /search
│       │   ├── service.py             # SearchService: semantic + keyword merge
│       │   ├── schemas.py             # SearchRequest, SearchResponse
│       │   ├── vector_store.py        # ChromaDB read/write abstraction
│       │   └── tests/
│       │       ├── test_router.py
│       │       └── test_vector_store.py
│       │
│       ├── chat/                      # Feature: context-aware AI conversation
│       │   ├── __init__.py
│       │   ├── router.py              # POST /chat, GET/PATCH/DELETE /chat/sessions
│       │   ├── service.py             # ChatService: search + context + stream + auto-learn
│       │   ├── schemas.py             # ChatRequest
│       │   ├── repository.py          # SQLite: sessions + messages + project_memory
│       │   ├── prompt_builder.py      # System prompt assembly with APA rules
│       │   ├── web_search.py          # DuckDuckGo HTML scraper for reference fallback
│       │   └── tests/
│       │       ├── test_router.py
│       │       └── test_service.py
│       │
│       ├── graph/                     # Feature: knowledge graph from indexed papers
│       │   ├── __init__.py
│       │   ├── router.py              # GET /graph, history, themes, tracked concepts, concept summary
│       │   ├── service.py             # GraphService: build, checkpoint, themes
│       │   ├── schemas.py             # GraphResponse, GraphCheckpoint, TrackedConcept, etc.
│       │   ├── builder.py             # GraphBuilder: concept extraction, node/edge creation, layout
│       │   ├── llm_service.py         # GraphLLMService: query refinement, concept summaries
│       │   ├── tracked_service.py     # CRUD for user-tracked concepts
│       │   ├── jobs.py                # Background graph generation via actions registry
│       │   └── tests/
│       │       ├── test_builder.py
│       │       ├── test_graph_history.py
│       │       ├── test_graph_cache.py
│       │       ├── test_themes.py
│       │       ├── test_graph_llm.py
│       │       └── test_tracked.py
│       │
│       ├── literature/                # Feature: paper-level literature mapping
│       │   ├── __init__.py
│       │   ├── router.py              # Literature map, entries, metadata, export, summaries
│       │   ├── service.py             # LiteratureService: map build, enrichment, entries, APA
│       │   ├── llm_service.py         # LiteratureLLMService: metadata extraction, summaries
│       │   ├── metadata.py            # Crossref/OpenAlex lookup, DOI extraction
│       │   ├── jobs.py                # Background literature map builds
│       │   ├── schemas.py             # LiteratureEntry, LiteratureMapResponse, etc.
│       │   └── tests/
│       │       ├── test_literature.py
│       │       ├── test_literature_entries.py
│       │       └── test_metadata_sources.py
│       │
│       ├── models/                    # Feature: LLM provider management
│       │   ├── __init__.py
│       │   ├── router.py              # GET /models, POST /models/switch, catalog, downloads
│       │   ├── service.py             # ModelService: listing, switching, provider factory
│       │   ├── schemas.py             # SwitchModelRequest, DownloadModelRequest
│       │   ├── repository.py          # SQLite CRUD for model_configs
│       │   ├── catalog.py             # Device tier recommendations, cloud presets
│       │   ├── downloads.py           # HuggingFace GGUF download manager
│       │   ├── providers/
│       │   │   ├── __init__.py
│       │   │   ├── ollama.py          # Ollama API provider
│       │   │   ├── local.py           # Local GGUF provider (llama-cpp-python)
│       │   │   ├── openai.py          # OpenAI API provider
│       │   │   ├── anthropic.py       # Anthropic API provider
│       │   │   └── google.py          # Google Gemini API provider
│       │   └── tests/
│       │       └── test_router.py
│       │
│       ├── skills/                    # Feature: AI skill system
│       │   ├── __init__.py
│       │   ├── router.py              # GET /skills, /skills/catalog, install, enable, uninstall, import
│       │   ├── service.py             # SkillsService: catalog, CRUD, keyword detection
│       │   ├── schemas.py             # SkillManifest, SkillInstallRequest, SkillEnableRequest
│       │   └── tests/
│       │       └── test_service.py
│       │
│       ├── settings/                  # Feature: user preferences
│       │   ├── __init__.py
│       │   ├── router.py              # GET /settings, PUT /settings
│       │   ├── service.py             # SettingsService: get/update with encryption + tier defaults
│       │   ├── schemas.py             # SettingsUpdate, SettingsResponse
│       │   ├── defaults.py            # Device tier defaults (low/medium/high)
│       │   └── tests/
│       │       └── test_service.py
│       │
│       └── actions/                   # Feature: background job registry
│           ├── __init__.py
│           ├── router.py              # GET /actions, POST pause/resume
│           ├── registry.py            # In-memory action registry, slot management, pause events
│           └── tests/
│               └── test_registry.py
│
├── skills/                            # 8 AI skill definitions (JSON manifests)
│   ├── citation-formatter.json
│   ├── critical-thinking.json
│   ├── hypothesis-brainstorm.json
│   ├── literature-mapping.json
│   ├── literature-review.json
│   ├── research-workflow.json
│   ├── source-evaluation.json
│   └── summarize.json
│
├── _system/                           # System-level prompts and schemas
│   └── prompts/
│       ├── base_system.md             # Core LLM rules for chat
│       ├── apa_citation.md            # APA 7th edition citation rules
│       ├── reference_handling.md      # Reference fallback instructions
│       └── secondary_sources.md       # Secondary source handling
│
├── _templates/feature/                # Feature skeleton for new features
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   ├── schemas.py
│   ├── CONTEXT.md
│   ├── README.md
│   └── tests/
│
├── data/                              # Runtime data (gitignored)
│   ├── uploads/                       # Raw uploaded files
│   ├── processed/                     # Extracted text artifacts
│   ├── chroma_db/                     # ChromaDB persistence
│   ├── project_memory/                # Inspectable memory files per project
│   └── notebook.db                    # SQLite database
│
├── tests/                             # Backend tests
├── requirements.txt
├── .env.example
└── Dockerfile
```
