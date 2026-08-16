import sqlite3

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
    db.execute("INSERT INTO documents VALUES ('d2', 'u2', 'p1', 'Other User Doc')")
    db.commit()
    return db


def test_detect_themes_groups_concepts_per_document():
    db = _db()
    db.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c1', 'd1', 0, 'Quantum Computing and Neural Networks'), "
        "('c2', 'd1', 1, 'Quantum Computing grows fast')"
    )
    db.commit()
    service = GraphService(db)

    themes = service.detect_themes("u1", "p1")
    assert len(themes) == 1
    assert themes[0]["doc_id"] == "d1"
    assert themes[0]["doc_name"] == "Alpha Paper"
    counts = {t["concept"]: t["count"] for t in themes[0]["themes"]}
    assert counts.get("Quantum Computing") == 2
    assert counts.get("Neural Networks") == 1


def test_detect_themes_excludes_other_users_documents():
    db = _db()
    db.execute("INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c3', 'd2', 0, 'Secret Project details')")
    db.commit()
    service = GraphService(db)

    assert service.detect_themes("u1", "p1") == []
    assert len(service.detect_themes("u2", "p1")) == 1


def test_detect_themes_respects_limit():
    db = _db()
    db.execute("INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c1', 'd1', 0, 'Alpha Beta; Gamma Delta; Epsilon Zeta')")
    db.commit()
    service = GraphService(db)

    themes = service.detect_themes("u1", "p1", limit=3)
    assert len(themes[0]["themes"]) == 3


def test_detect_themes_empty_project():
    db = _db()
    service = GraphService(db)
    assert service.detect_themes("u1", "p1") == []


def test_build_graph_uses_tracked_preferences():
    db = _db()
    db.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c1', 'd1', 0, 'Quantum Computing and Neural Networks')"
    )
    db.execute(
        "INSERT INTO tracked_concepts VALUES ('t1', 'u1', 'p1', 'quantum computing')"
    )
    db.commit()
    service = GraphService(db)

    resp = service.build_graph("u1", [], project_id="p1")
    assert any(n.label == "Quantum Computing" for n in resp.nodes)


def test_build_graph_is_cached_and_invalidated_by_preferences():
    db = _db()
    db.execute("INSERT INTO chunks (id, document_id, chunk_index, content) VALUES ('c1', 'd1', 0, 'Quantum Computing and Neural Networks')")
    db.commit()
    service = GraphService(db)

    before = _BUILD_CACHE.copy()
    first = service.build_graph("u1", [], project_id="p1")
    second = service.build_graph("u1", [], project_id="p1")
    assert first is second

    db.execute("INSERT INTO tracked_concepts VALUES ('t1', 'u1', 'p1', 'neural networks')")
    db.commit()
    third = service.build_graph("u1", [], project_id="p1")
    assert third is not first
    assert any(n.label == "Neural Networks" for n in third.nodes)

    _BUILD_CACHE.clear()
    for key in before:
        _BUILD_CACHE[key] = before[key]
