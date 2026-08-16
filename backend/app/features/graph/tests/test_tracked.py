import sqlite3

import pytest

from app.features.graph.tracked_service import TrackedConceptsService


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
        CREATE TABLE tracked_concepts (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, concept TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, project_id, concept))"""
    )
    db.execute("INSERT INTO projects VALUES ('p1', 'u1', 'Proj'), ('p2', 'u2', 'Other')")
    db.commit()
    return db


def test_add_list_and_remove():
    db = _db()
    svc = TrackedConceptsService(db)

    added = svc.add("u1", "p1", "  Agriculture  ")
    assert added["concept"] == "Agriculture"

    added2 = svc.add("u1", "p1", "Economics")
    concepts = svc.list("u1", "p1")
    assert [c["concept"] for c in concepts] == ["Agriculture", "Economics"]

    assert svc.remove("u1", added2["id"]) is True
    assert [c["concept"] for c in svc.list("u1", "p1")] == ["Agriculture"]


def test_add_is_idempotent_for_duplicate_concept():
    db = _db()
    svc = TrackedConceptsService(db)
    a = svc.add("u1", "p1", "Agriculture")
    b = svc.add("u1", "p1", "agriculture  ")
    assert a["id"] == b["id"]
    assert len(svc.list("u1", "p1")) == 1


def test_concepts_scoped_per_project_and_user():
    db = _db()
    svc = TrackedConceptsService(db)
    svc.add("u1", "p1", "Agriculture")
    svc.add("u2", "p2", "Mining")

    assert [c["concept"] for c in svc.list("u1", "p1")] == ["Agriculture"]
    assert [c["concept"] for c in svc.list("u2", "p2")] == ["Mining"]


def test_rejects_empty_or_blank_concept():
    db = _db()
    svc = TrackedConceptsService(db)
    with pytest.raises(ValueError):
        svc.add("u1", "p1", "   ")


def test_rejects_concept_for_unknown_project():
    db = _db()
    svc = TrackedConceptsService(db)
    with pytest.raises(ValueError):
        svc.add("u1", "nope", "Agriculture")
    with pytest.raises(ValueError):
        svc.list("u1", "nope")


def test_remove_scoped_to_user():
    db = _db()
    svc = TrackedConceptsService(db)
    added = svc.add("u1", "p1", "Agriculture")
    assert svc.remove("u2", added["id"]) is False
    assert len(svc.list("u1", "p1")) == 1
