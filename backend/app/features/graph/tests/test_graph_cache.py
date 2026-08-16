import sqlite3

from app.features.graph.builder import GraphBuilder
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


def test_graph_is_persisted_and_served_without_rebuilding():
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    first = service.build_graph("u1", [], project_id="p1")
    assert any(n.label == "Quantum Computing" for n in first.nodes)

    _BUILD_CACHE.clear()

    saved_row = db.execute(
        "SELECT graph_json FROM graph_history WHERE user_id = 'u1' AND project_id = 'p1'"
    ).fetchone()
    assert saved_row is not None

    original_build = GraphBuilder.build
    GraphBuilder.build = lambda self, chunks, prefs=None, on_progress=None: (_ for _ in ()).throw(
        AssertionError("builder must not run when the saved graph is reused")
    )
    try:
        fresh = GraphService(db)
        again = fresh.build_graph("u1", [], project_id="p1")
        assert len(again.nodes) == len(first.nodes)
        assert again.model_dump_json() == saved_row["graph_json"]
    finally:
        GraphBuilder.build = original_build
        _BUILD_CACHE.clear()


def test_graph_rebuilds_when_new_paper_is_indexed():
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    first = service.build_graph("u1", [], project_id="p1")
    first_labels = {n.label for n in first.nodes}

    _seed_chunk(db, "c2", "d1", "Machine Learning and Deep Neural Networks", index=1)
    _BUILD_CACHE.clear()

    second = service.build_graph("u1", [], project_id="p1")
    second_labels = {n.label for n in second.nodes}
    assert second_labels != first_labels

    fingerprint = db.execute(
        "SELECT fingerprint FROM graph_history WHERE user_id = 'u1' AND project_id = 'p1' ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()["fingerprint"]
    assert "c2" in fingerprint
    _BUILD_CACHE.clear()


def test_force_rebuild_ignores_saved_graph():
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    service.build_graph("u1", [], project_id="p1")

    _BUILD_CACHE.clear()
    original_build = GraphBuilder.build
    GraphBuilder.build = lambda self, chunks, prefs=None, on_progress=None: (_ for _ in ()).throw(
        AssertionError("force must always rebuild")
    )
    try:
        fresh = GraphService(db)
        try:
            fresh.build_graph("u1", [], project_id="p1", force=True)
            assert False, "expected force rebuild to invoke the builder"
        except AssertionError:
            pass
    finally:
        GraphBuilder.build = original_build
        _BUILD_CACHE.clear()


def test_saved_graph_invalidated_by_preferences():
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    service = GraphService(db)
    service.build_graph("u1", [], project_id="p1")

    db.execute("INSERT INTO tracked_concepts VALUES ('t1', 'u1', 'p1', 'neural networks')")
    db.commit()
    _BUILD_CACHE.clear()

    rebuilt = GraphService(db).build_graph("u1", [], project_id="p1")
    assert any(n.label == "Neural Networks" for n in rebuilt.nodes)
    prefs_key = db.execute(
        "SELECT prefs_key FROM graph_history WHERE user_id = 'u1' AND project_id = 'p1' ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()["prefs_key"]
    assert "neural networks" in prefs_key
    _BUILD_CACHE.clear()
