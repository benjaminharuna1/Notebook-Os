import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.features.ingestion.jobs import JobManager
from app.features.ingestion.service import IngestionService


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT,
            filename TEXT, file_path TEXT, file_type TEXT, file_size INTEGER, page_count INTEGER,
            status TEXT, error TEXT, indexed_at TEXT)"""
    )
    conn.commit()
    return conn


def _insert(conn: sqlite3.Connection, doc_id: str, status: str) -> None:
    conn.execute(
        "INSERT INTO documents (id, user_id, title, status) VALUES (?, 'u1', 'Doc', ?)",
        (doc_id, status),
    )
    conn.commit()


# --- JobManager -----------------------------------------------------------


def test_job_manager_pause_blocks_and_resume_releases():
    manager = JobManager()
    progress = []
    gate = threading.Event()

    def work():
        manager.checkpoint("d1")
        gate.wait()  # hold the worker until pause has been applied
        manager.checkpoint("d1")  # blocks here while paused
        progress.append("finished")

    manager.submit("d1", work)
    assert manager.pause("d1") is True
    gate.set()  # release the worker into the (now cleared) checkpoint
    time.sleep(0.1)
    assert manager.is_paused("d1")
    assert progress == []

    assert manager.resume("d1") is True
    deadline = time.time() + 5
    while not progress and time.time() < deadline:
        time.sleep(0.02)
    assert progress == ["finished"]


def test_job_manager_finishes_without_pause():
    manager = JobManager()
    done = []

    def work():
        manager.checkpoint("d2")
        done.append(True)

    manager.submit("d2", work)
    deadline = time.time() + 5
    while not done and time.time() < deadline:
        time.sleep(0.02)
    assert done == [True]
    # completed jobs are unregistered
    assert manager.is_active("d2") is False


# --- IngestionService control ---------------------------------------------


def test_pause_then_resume_updates_status():
    conn = _db()
    _insert(conn, "d3", "processing")
    service = IngestionService(conn)

    hold = threading.Event()
    job_manager_holder = _job_manager_for(service)
    job_manager_holder.submit("d3", hold.wait)

    assert service.pause("d3", "u1") == {"success": True, "status": "paused"}
    assert _status(conn, "d3") == "paused"

    assert service.resume("d3", "u1") == {"success": True, "status": "processing"}
    assert _status(conn, "d3") == "processing"

    hold.set()  # let the job thread finish


def test_pause_rejected_for_finished_document():
    conn = _db()
    _insert(conn, "d4", "indexed")
    service = IngestionService(conn)

    with pytest.raises(AppException) as excinfo:
        service.pause("d4", "u1")
    assert excinfo.value.status_code == 409


def test_resume_rejected_when_not_paused():
    conn = _db()
    _insert(conn, "d5", "indexed")
    service = IngestionService(conn)

    with pytest.raises(AppException) as excinfo:
        service.resume("d5", "u1")
    assert excinfo.value.status_code == 409


def test_reprocess_finished_document():
    conn = _db()
    _insert(conn, "d6", "failed")
    service = IngestionService(conn)

    result = service.reprocess("d6", "u1")
    assert result["status"] == "queued"
    assert _status(conn, "d6") == "queued"


@pytest.mark.asyncio
async def test_status_not_found():
    conn = _db()
    service = IngestionService(conn)
    with pytest.raises(AppException) as excinfo:
        await service.get_status("missing", "u1")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_status_indexed_progress_is_100():
    conn = _db()
    _insert(conn, "d7", "indexed")
    service = IngestionService(conn)
    status = await service.get_status("d7", "u1")
    assert status.status == "indexed"
    assert status.progress == 100


# --- end-to-end background pipeline ----------------------------------------


class _FakeCollection:
    def get(self, where=None, include=None):
        return {"ids": []}

    def delete(self, ids):
        pass


class _FakeChroma:
    def get_or_create_collection(self, name=None):
        return _FakeCollection()


class _FakeEmbeddingService:
    def __init__(self, settings_dict=None):
        pass

    def embed_chunks(self, chunks, document_id, user_id, project_id=None):
        pass


class _FakeFile:
    def __init__(self, name: str, data: bytes):
        self.filename = name
        self._data = data

    async def read(self):
        return self._data


@pytest.mark.asyncio
async def test_ingest_queues_then_pipeline_indexes(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"

    def _open():
        c = sqlite3.connect(str(db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT,
                filename TEXT, file_path TEXT, file_type TEXT, file_size INTEGER, page_count INTEGER,
                status TEXT, error TEXT, indexed_at TEXT)"""
        )
        c.commit()
        return c

    monkeypatch.setattr("app.features.ingestion.service.get_sqlite_connection", _open)
    monkeypatch.setattr("app.features.ingestion.service.get_chroma_client", lambda: _FakeChroma())
    monkeypatch.setattr("app.features.ingestion.service.EmbeddingService", _FakeEmbeddingService)
    monkeypatch.setattr(
        "app.features.ingestion.service.settings",
        SimpleNamespace(UPLOAD_DIR=tmp_path, MAX_UPLOAD_SIZE_MB=25, EMBED_BATCH_SIZE=4),
    )

    conn = _open()
    service = IngestionService(conn)

    class _FakeExtractor:
        def extract(self, path):
            return SimpleNamespace(title="Report", page_count=3, text="hello world")

    service.extractors = {"pdf": _FakeExtractor()}

    resp = await service.ingest(_FakeFile("a.pdf", b"%PDF-1.4 tiny"), "u1")
    assert resp.status == "queued"
    assert resp.document_id

    deadline = time.time() + 10
    status = ""
    while time.time() < deadline:
        row = conn.execute("SELECT status FROM documents WHERE id = ?", (resp.document_id,)).fetchone()
        status = row["status"] if row else ""
        if status == "indexed":
            break
        time.sleep(0.1)

    assert status == "indexed"
    row = conn.execute("SELECT title, page_count FROM documents WHERE id = ?", (resp.document_id,)).fetchone()
    assert row["title"] == "Report"
    assert row["page_count"] == 3


# --- project scoping --------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_rejects_unknown_project():
    conn = _db()
    service = IngestionService(conn)
    with pytest.raises(AppException) as excinfo:
        await service.ingest(_FakeFile("c.pdf", b"data"), "u1", project_id="nope")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_ingest_scopes_file_to_project_folder(monkeypatch, tmp_path):
    conn = _db()
    conn.execute("INSERT INTO projects VALUES ('p1', 'u1', 'Proj')")
    conn.commit()

    monkeypatch.setattr(
        "app.features.ingestion.service.settings",
        SimpleNamespace(UPLOAD_DIR=str(tmp_path), MAX_UPLOAD_SIZE_MB=25),
    )
    monkeypatch.setattr("app.features.ingestion.service.job_manager.submit", lambda *a, **k: None)

    service = IngestionService(conn)
    resp = await service.ingest(_FakeFile("b.pdf", b"%PDF tiny"), "u1", project_id="p1")

    row = conn.execute(
        "SELECT file_path, project_id FROM documents WHERE id = ?", (resp.document_id,)
    ).fetchone()
    expected = str(tmp_path / "projects" / "p1" / f"{resp.document_id}.pdf")
    assert row["file_path"] == expected
    assert row["project_id"] == "p1"
    assert Path(expected).exists()


# --- helpers --------------------------------------------------------------


def _job_manager_for(service: IngestionService):
    from app.features.ingestion.jobs import job_manager

    return job_manager


def _status(conn: sqlite3.Connection, doc_id: str) -> str:
    return conn.execute("SELECT status FROM documents WHERE id = ?", (doc_id,)).fetchone()["status"]
