import sqlite3
from unittest.mock import MagicMock, patch

from app.features.documents.service import DocumentService

_SCHEMA = """
CREATE TABLE documents (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, filename TEXT,
    file_path TEXT, file_type TEXT, author TEXT, year INTEGER, doi TEXT,
    abstract TEXT, verification_status TEXT, apa_reference TEXT, authors TEXT);
CREATE TABLE literature_entries (
    paper_id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, citation TEXT,
    apa_reference TEXT, auto_generated INTEGER DEFAULT 0);
CREATE TABLE paper_references (
    id TEXT PRIMARY KEY, paper_id TEXT, raw_ref TEXT, matched_paper_id TEXT, confidence REAL);
CREATE TABLE chunks (
    id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT);
"""


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    return db


def _seed(db, pid, project_id, user_id="u1"):
    db.execute(
        """INSERT INTO documents (id, user_id, project_id, title, filename, file_path, file_type)
           VALUES (?, ?, ?, ?, ?, ?, 'pdf')""",
        (pid, user_id, project_id, f"Title {pid}", f"{pid}.pdf", f"/tmp/{pid}.pdf"),
    )
    db.commit()


def _fake_chroma():
    client = MagicMock()
    client.get_or_create_collection.return_value = MagicMock()
    return client


def test_batch_delete_removes_only_owned_project_papers():
    db = _db()
    _seed(db, "p1", "proj1")
    _seed(db, "p2", "proj1")
    _seed(db, "p3", "proj2")
    _seed(db, "p4", "proj1", user_id="u2")
    db.execute(
        "INSERT INTO literature_entries (paper_id, user_id, project_id, citation) VALUES ('p1', 'u1', 'proj1', 'C1')"
    )
    db.execute(
        "INSERT INTO literature_entries (paper_id, user_id, project_id, citation) VALUES ('p3', 'u1', 'proj2', 'C3')"
    )
    db.commit()

    service = DocumentService(db)
    with patch.object(service.repo, "get_chroma", return_value=_fake_chroma()), patch.object(
        DocumentService, "_rebuild_literature"
    ) as rebuild:
        result = service.delete_documents(["p1", "p2", "p3", "missing"], "u1", "proj1")

    assert result == {"success": True, "deleted": 2}
    remaining = {row["id"] for row in db.execute("SELECT id FROM documents")}
    assert remaining == {"p3", "p4"}
    remaining_entries = {row["paper_id"] for row in db.execute("SELECT paper_id FROM literature_entries")}
    assert remaining_entries == {"p3"}
    rebuild.assert_called_once_with("u1", "proj1")


def test_batch_delete_empty_or_foreign_does_nothing():
    db = _db()
    _seed(db, "p1", "proj1")

    service = DocumentService(db)
    with patch.object(service.repo, "get_chroma", return_value=_fake_chroma()), patch.object(
        DocumentService, "_rebuild_literature"
    ) as rebuild:
        empty = service.delete_documents([], "u1", "proj1")
        assert empty == {"success": True, "deleted": 0}
        rebuild.assert_not_called()

        foreign = service.delete_documents(["unknown", "not-owned"], "u1", "proj1")
        assert foreign == {"success": True, "deleted": 0}
        rebuild.assert_not_called()
        assert db.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"] == 1
