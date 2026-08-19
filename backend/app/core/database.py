import sqlite3
import threading
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

_chroma_lock = threading.Lock()
_chroma_client = None


def get_sqlite_connection() -> sqlite3.Connection:
    db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_sqlite_db():
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id   TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            settings  TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id  TEXT REFERENCES projects(id) ON DELETE CASCADE,
            title       TEXT NOT NULL,
            filename    TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            file_size   INTEGER,
            page_count  INTEGER,
            source_url  TEXT,
            author      TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            indexed_at  DATETIME,
            status      TEXT DEFAULT 'pending',
            error       TEXT,
            metadata_user_edited INTEGER DEFAULT 0,
            extracted_doi TEXT,
            metadata_candidates TEXT
        );

        CREATE TABLE IF NOT EXISTS chunks (
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

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id  TEXT REFERENCES projects(id) ON DELETE CASCADE,
            title       TEXT,
            model_used  TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content     TEXT NOT NULL,
            sources     TEXT,
            model_used  TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS model_configs (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            provider    TEXT NOT NULL,
            model_id    TEXT NOT NULL,
            is_active   BOOLEAN DEFAULT FALSE,
            is_default  BOOLEAN DEFAULT FALSE,
            config      TEXT
        );

        CREATE TABLE IF NOT EXISTS user_skills (
            user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            skill_id     TEXT NOT NULL,
            manifest     TEXT NOT NULL,
            enabled      INTEGER DEFAULT 1,
            installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, skill_id)
        );

        CREATE TABLE IF NOT EXISTS tracked_concepts (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            concept     TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, project_id, concept)
        );

        CREATE TABLE IF NOT EXISTS graph_history (
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

        CREATE TABLE IF NOT EXISTS paper_references (
            id               TEXT PRIMARY KEY,
            paper_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            raw_ref          TEXT NOT NULL,
            matched_paper_id TEXT,
            confidence       REAL
        );

        CREATE TABLE IF NOT EXISTS literature_entries (
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

        CREATE TABLE IF NOT EXISTS project_memory (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            source      TEXT DEFAULT 'chat',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, key)
        );
    """)

    # Lightweight migrations for databases created before these columns existed.
    migrations = [
        ("ALTER TABLE documents ADD COLUMN error TEXT", None),
        ("ALTER TABLE documents ADD COLUMN project_id TEXT", None),
        ("ALTER TABLE chat_sessions ADD COLUMN project_id TEXT", None),
        ("ALTER TABLE documents ADD COLUMN year INTEGER", None),
        ("ALTER TABLE documents ADD COLUMN doi TEXT", None),
        ("ALTER TABLE documents ADD COLUMN abstract TEXT", None),
        ("ALTER TABLE documents ADD COLUMN verification_status TEXT", None),
        ("ALTER TABLE documents ADD COLUMN apa_reference TEXT", None),
        ("ALTER TABLE documents ADD COLUMN authors TEXT", None),
        ("ALTER TABLE documents ADD COLUMN metadata_user_edited INTEGER DEFAULT 0", None),
        ("ALTER TABLE documents ADD COLUMN extracted_doi TEXT", None),
        ("ALTER TABLE documents ADD COLUMN metadata_candidates TEXT", None),
        ("ALTER TABLE graph_history ADD COLUMN map_type TEXT DEFAULT 'concepts'", None),
        ("ALTER TABLE graph_history ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0", None),
        ("ALTER TABLE literature_entries ADD COLUMN user_edited TEXT", None),
        ("ALTER TABLE documents ADD COLUMN paper_type TEXT", None),
        ("ALTER TABLE documents ADD COLUMN edition TEXT", None),
        ("ALTER TABLE documents ADD COLUMN issn TEXT", None),
        ("ALTER TABLE documents ADD COLUMN isbn TEXT", None),
    ]
    for statement, _ in migrations:
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError:
            pass

    # Indexes referencing migrated columns must be created after the ALTERs.
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_project ON chat_sessions(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_graph_history_lookup ON graph_history(user_id, project_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_graph_history_map ON graph_history(user_id, project_id, map_type, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_paper_references_paper ON paper_references(paper_id)",
        "CREATE INDEX IF NOT EXISTS idx_paper_references_matched ON paper_references(matched_paper_id)",
        "CREATE INDEX IF NOT EXISTS idx_literature_entries_project ON literature_entries(user_id, project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_memory_project ON project_memory(project_id, updated_at DESC)",
    ):
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def get_chroma_client() -> chromadb.ClientAPI:
    # Cache a single long-lived client. Creating a fresh PersistentClient per
    # call lets the old one get garbage-collected, which drops Chroma's
    # refcount to zero and tears down the shared system while worker threads
    # are still using it (KeyError: '<chroma_db path>').
    global _chroma_client
    if _chroma_client is None:
        with _chroma_lock:
            if _chroma_client is None:
                chroma_path = Path(settings.CHROMA_DB_PATH)
                chroma_path.mkdir(parents=True, exist_ok=True)
                _chroma_client = chromadb.PersistentClient(
                    path=str(chroma_path),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
    return _chroma_client
