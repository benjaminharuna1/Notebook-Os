import os
import sqlite3
import tempfile
import time

from app.features.graph import jobs
from app.features.graph.service import _BUILD_CACHE, GraphService


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
        CREATE TABLE documents (id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT);
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
            embedded_at TEXT);
        CREATE TABLE tracked_concepts (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, concept TEXT)"""
    )
    db.execute("INSERT INTO projects VALUES ('p1', 'u1', 'Proj')")
    db.execute("INSERT INTO documents VALUES ('d1', 'u1', 'p1', 'Alpha Paper')")
    db.commit()
    return db


def _seed_chunk(db, chunk_id, document_id, content, index=0):
    db.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content) VALUES (?, ?, ?, ?)",
        (chunk_id, document_id, index, content),
    )
    db.commit()


def test_each_build_saves_a_checkpoint_and_latest_is_served():
    _BUILD_CACHE.clear()
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    service.build_graph("u1", [], project_id="p1")
    service.build_graph("u1", [], project_id="p1", force=True)

    history = service.list_history("u1", "p1")
    assert len(history) == 2
    assert history[0]["created_at"] >= history[1]["created_at"]
    assert history[0]["nodes"] > 0

    checkpoint = service.get_checkpoint("u1", history[0]["id"])
    assert checkpoint["graph"].model_dump_json() != ""
    assert checkpoint["id"] == history[0]["id"]


def test_history_delete_and_favourite():
    _BUILD_CACHE.clear()
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    service.build_graph("u1", [], project_id="p1", force=True)
    service.build_graph("u1", [], project_id="p1", force=True)

    history = service.list_history("u1", "p1")
    newest, oldest = history[0], history[1]

    updated = service.set_favourite("u1", newest["id"], True)
    assert updated["is_favourite"] is True
    assert service.get_checkpoint("u1", newest["id"])["is_favourite"] is True

    assert service.delete_checkpoint("u1", oldest["id"]) is True
    remaining = service.list_history("u1", "p1")
    assert [c["id"] for c in remaining] == [newest["id"]]

    assert service.delete_checkpoint("u1", "missing") is False


def test_checkpoint_ownership_scoping():
    _BUILD_CACHE.clear()
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    service.build_graph("u1", [], project_id="p1")

    checkpoint_id = service.list_history("u1", "p1")[0]["id"]
    assert service.get_checkpoint("u2", checkpoint_id) is None
    assert service.delete_checkpoint("u2", checkpoint_id) is False
    assert service.set_favourite("u2", checkpoint_id, True) is None


def test_generation_job_saves_checkpoint():
    _BUILD_CACHE.clear()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.db")
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.executescript(
            """CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
            CREATE TABLE documents (id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT);
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
                embedded_at TEXT);
            CREATE TABLE tracked_concepts (
                id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, concept TEXT)"""
        )
        db.execute("INSERT INTO projects VALUES ('p1', 'u1', 'Proj')")
        db.execute("INSERT INTO documents VALUES ('d1', 'u1', 'p1', 'Alpha Paper')")
        db.execute(
            "INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c1', 'd1', 0, 'Quantum Computing and Neural Networks')"
        )
        db.commit()

        def factory():
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return GraphService(conn)

        job_id = jobs.start_generation(factory, "u1", "p1", [], 2, True)
        job = jobs.wait_for_job(job_id)

        assert job["status"] == "done"
        assert job["progress"] == 100
        assert job["checkpoint"] is not None

        check_svc = factory()
        check = check_svc.get_checkpoint("u1", job["checkpoint"]["id"])
        assert check is not None
        assert any(n.label == "Quantum Computing" for n in check["graph"].nodes)
        check_svc.db.close()
        db.close()
        _BUILD_CACHE.clear()
