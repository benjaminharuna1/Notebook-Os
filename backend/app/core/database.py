import sqlite3
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings


def get_sqlite_connection() -> sqlite3.Connection:
    db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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

        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
            status      TEXT DEFAULT 'pending'
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
    """)

    conn.commit()
    conn.close()


def get_chroma_client() -> chromadb.ClientAPI:
    chroma_path = Path(settings.CHROMA_DB_PATH)
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
