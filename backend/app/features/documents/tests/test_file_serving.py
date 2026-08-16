import sqlite3
from unittest.mock import patch

import pytest

from app.core.exceptions import AppException
from app.features.documents.service import DocumentService

_SCHEMA = """
CREATE TABLE documents (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, filename TEXT,
    file_path TEXT, file_type TEXT, file_size INTEGER, page_count INTEGER,
    source_url TEXT, author TEXT, created_at TEXT, indexed_at TEXT, status TEXT,
    error TEXT, year INTEGER, doi TEXT, abstract TEXT, verification_status TEXT,
    apa_reference TEXT, authors TEXT, metadata_user_edited INTEGER DEFAULT 0);
"""


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    return db


def _seed(db, upload_dir, doc_id="d1", filename="paper.pdf"):
    path = upload_dir / filename
    path.write_bytes(b"%PDF-1.4 fake pdf content")
    db.execute(
        """INSERT INTO documents (id, user_id, project_id, title, filename, file_path, file_type)
           VALUES (?, ?, 'proj1', ?, ?, ?, ?)""",
        (doc_id, "u1", filename, filename, str(path), "pdf"),
    )
    db.commit()


def _service_with_upload_dir(db, upload_dir):
    with patch("app.features.documents.service.settings") as mock_settings:
        mock_settings.UPLOAD_DIR = str(upload_dir)
        yield DocumentService(db)


def test_get_document_file_returns_path_and_media_type(tmp_path):
    db = _db()
    _seed(db, tmp_path)
    for service in _service_with_upload_dir(db, tmp_path):
        path, media_type = service.get_document_file("d1", "u1", "proj1")
    assert path.name == "paper.pdf"
    assert media_type == "application/pdf"


def test_get_document_file_scopes_to_project_and_user(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4")
    db = _db()
    db.execute(
        """INSERT INTO documents (id, user_id, project_id, title, filename, file_path, file_type)
           VALUES ('d1', 'u2', 'proj1', 'x', 'paper.pdf', ?, 'pdf')""",
        (str(path),),
    )
    db.commit()
    for service in _service_with_upload_dir(db, tmp_path):
        with pytest.raises(AppException) as exc:
            service.get_document_file("d1", "u1", "proj1")  # wrong owner
    assert exc.value.status_code == 404


def test_get_document_file_rejects_path_outside_upload_dir(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    db = _db()
    _seed(db, upload_dir)
    evil_dir = tmp_path / "outside"
    evil_dir.mkdir()
    evil = evil_dir / "evil.pdf"
    evil.write_bytes(b"x")
    db.execute("UPDATE documents SET file_path = ? WHERE id = 'd1'", (str(evil),))
    db.commit()
    for service in _service_with_upload_dir(db, upload_dir):
        with pytest.raises(AppException) as exc:
            service.get_document_file("d1", "u1", "proj1")
    assert exc.value.status_code == 403


def test_get_document_file_missing_on_disk(tmp_path):
    db = _db()
    _seed(db, tmp_path)
    (tmp_path / "paper.pdf").unlink()
    for service in _service_with_upload_dir(db, tmp_path):
        with pytest.raises(AppException) as exc:
            service.get_document_file("d1", "u1", "proj1")
    assert exc.value.status_code == 404
