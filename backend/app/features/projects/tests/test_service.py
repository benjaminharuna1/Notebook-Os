import sqlite3

import pytest

from app.core.exceptions import AppException
from app.features.projects.service import ProjectService


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """CREATE TABLE projects (
            id TEXT PRIMARY KEY, user_id TEXT, name TEXT, description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT, filename TEXT, file_path TEXT, file_type TEXT, file_size INTEGER, page_count INTEGER,
            status TEXT, error TEXT, indexed_at TEXT);
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT, model_used TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);"""
    )
    conn.commit()
    return conn


def test_create_and_list_project():
    conn = _db()
    service = ProjectService(conn)

    project = service.create_project("u1", "Thesis", "My thesis research")
    assert project["name"] == "Thesis"
    assert project["doc_count"] == 0

    projects = service.list_projects("u1")["projects"]
    assert len(projects) == 1
    assert projects[0]["id"] == project["id"]

    # Other users don't see it.
    assert service.list_projects("u2")["projects"] == []


def test_create_project_requires_name():
    conn = _db()
    with pytest.raises(AppException) as excinfo:
        ProjectService(conn).create_project("u1", "   ")
    assert excinfo.value.status_code == 422


def test_get_project_ownership():
    conn = _db()
    service = ProjectService(conn)
    project = service.create_project("u1", "Alpha")

    assert service.get_project(project["id"], "u1")["id"] == project["id"]
    with pytest.raises(AppException) as excinfo:
        service.get_project(project["id"], "u2")
    assert excinfo.value.status_code == 404


def test_update_project():
    conn = _db()
    service = ProjectService(conn)
    project = service.create_project("u1", "Alpha")

    updated = service.update_project(project["id"], "u1", name="Beta", description="New desc")
    assert updated["name"] == "Beta"
    assert updated["description"] == "New desc"


def test_delete_project_cascades_documents_and_sessions():
    conn = _db()
    service = ProjectService(conn)
    project = service.create_project("u1", "To Delete")

    pid = project["id"]
    conn.execute(
        "INSERT INTO documents (id, user_id, project_id, title, filename, file_path, file_type, status) "
        "VALUES ('doc1', 'u1', ?, 'T', 't.pdf', '/tmp/x.pdf', 'pdf', 'indexed')",
        (pid,),
    )
    conn.execute(
        "INSERT INTO chat_sessions (id, user_id, project_id, title) VALUES ('s1', 'u1', ?, 'S')",
        (pid,),
    )
    conn.commit()

    assert service.delete_project(pid, "u1") == {"success": True}
    assert service.list_projects("u1")["projects"] == []
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0] == 0
