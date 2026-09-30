# Database Schema

## SQLite — `notebook.db`

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

## Indexes

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

## ChromaDB — Vector Collections

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
