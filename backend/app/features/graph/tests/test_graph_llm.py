import asyncio
import sqlite3
from unittest.mock import patch

from app.features.graph.llm_service import GraphLLMService
from app.features.graph.service import _BUILD_CACHE, GraphService
from app.features.processing.service import ProcessingService


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT);
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
            page_number INTEGER, char_start INTEGER, char_end INTEGER, token_count INTEGER,
            embedded_at TEXT);
        CREATE TABLE tracked_concepts (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, concept TEXT);
        CREATE TABLE graph_history (
            id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, graph_json TEXT,
            fingerprint TEXT, prefs_key TEXT, is_favourite INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP);"""
    )
    db.execute("INSERT INTO projects VALUES ('p1', 'u1', 'Proj')")
    db.execute("INSERT INTO projects VALUES ('p2', 'u2', 'Other')")
    db.execute("INSERT INTO documents VALUES ('d1', 'u1', 'p1', 'Alpha Paper')")
    db.execute("INSERT INTO documents VALUES ('d2', 'u1', 'p2', 'Beta Paper')")
    db.commit()
    return db


def _seed_chunk(db, chunk_id, document_id, content, page=None, index=0):
    db.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content, page_number) VALUES (?, ?, ?, ?, ?)",
        (chunk_id, document_id, index, content, page),
    )
    db.commit()


def test_processing_service_is_page_aware():
    service = ProcessingService({"chunk_size": 40, "chunk_overlap": 0})
    chunks = service.process(
        "",
        "d1",
        pages=["The first page of alpha text goes here.", "The second page of beta text."],
    )
    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["page_number"] == 1
    assert chunks[1]["chunk_index"] == 1
    assert chunks[1]["page_number"] == 2

    legacy = ProcessingService({"chunk_size": 40, "chunk_overlap": 0}).process(
        "Single blob with no page split.", "d1"
    )
    assert legacy[0]["page_number"] is None


def test_refine_query_maps_keyword_to_existing_labels():
    _BUILD_CACHE.clear()
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    GraphService(db).build_graph("u1", [], project_id="p1", force=True)

    async def fake_call(self, user_id, system, prompt):
        assert "Quantum Computing" in prompt
        return "Quantum Computing\nNeural Networks\n"

    llm = GraphLLMService(db)
    with patch.object(GraphLLMService, "_call", fake_call):
        result = asyncio.run(llm.refine_query("u1", "p1", "quantum computers"))

    assert "Quantum Computing" in result["matches"]
    assert "Neural Networks" in result["matches"]


def test_refine_query_without_checkpoint_returns_empty():
    db = _db()
    llm = GraphLLMService(db)
    result = asyncio.run(llm.refine_query("u1", "p1", "quantum computers"))
    assert result == {"matches": []}


def test_refine_query_respects_none_answer():
    _BUILD_CACHE.clear()
    db = _db()
    _seed_chunk(db, "c1", "d1", "Quantum Computing and Neural Networks")
    GraphService(db).build_graph("u1", [], project_id="p1", force=True)

    async def fake_call(self, user_id, system, prompt):
        return "NONE"

    llm = GraphLLMService(db)
    with patch.object(GraphLLMService, "_call", fake_call):
        result = asyncio.run(llm.refine_query("u1", "p1", "unrelated topic"))
    assert result["matches"] == []


def test_summary_sources_ranks_and_scopes_to_project():
    _seed_chunk(db := _db(), "c1", "d1", "Quantum computing is promising.", page=2)
    _seed_chunk(db, "c2", "d1", "More on Quantum computing and Quantum computing again.", page=4)
    _seed_chunk(db, "c3", "d1", "Neural networks for classification.", page=5)
    # other project — must never surface
    _seed_chunk(db, "c4", "d2", "Quantum computing in a different project.", page=1)

    llm = GraphLLMService(db)
    sources = llm.summary_sources("u1", "p1", "Quantum computing")

    assert [s["document_id"] for s in sources] == ["d1", "d1"]
    assert sources[0]["count"] == 2
    assert sources[0]["page"] == 4
    assert sources[1]["page"] == 2

    assert llm.summary_sources("u1", "p1", "Missing concept") == []


def test_summary_prompt_includes_label_and_pages():
    llm = GraphLLMService(_db())
    system, prompt = llm.summary_prompt(
        "Quantum computing",
        [{"title": "Alpha Paper", "page": 4, "content": "Some quantum content."}],
    )
    assert "Quantum computing" in prompt
    assert "Alpha Paper" in prompt
    assert "Page 4" in prompt
    assert "research summarizer" in system
