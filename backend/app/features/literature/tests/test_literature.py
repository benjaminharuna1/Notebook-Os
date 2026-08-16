import asyncio
import json
import math
import os
import sqlite3
import tempfile
from unittest.mock import patch

from app.features.literature import jobs
from app.features.literature.llm_service import LiteratureLLMService
from app.features.literature.service import LiteratureService

_SCHEMA = """
CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
CREATE TABLE documents (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, filename TEXT,
    file_path TEXT, file_type TEXT, author TEXT, year INTEGER, doi TEXT,
    abstract TEXT, verification_status TEXT, apa_reference TEXT, authors TEXT);
CREATE TABLE chunks (
    id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
    page_number INTEGER, char_start INTEGER, char_end INTEGER, token_count INTEGER,
    embedded_at TEXT);
CREATE TABLE user_settings (user_id TEXT PRIMARY KEY, settings TEXT NOT NULL DEFAULT '{}');
CREATE TABLE model_configs (
    id TEXT PRIMARY KEY, user_id TEXT, provider TEXT, model_id TEXT,
    is_active INTEGER DEFAULT 0, is_default INTEGER DEFAULT 0, config TEXT);
CREATE TABLE graph_history (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, graph_json TEXT,
    fingerprint TEXT, prefs_key TEXT, is_favourite INTEGER DEFAULT 0,
    map_type TEXT DEFAULT 'concepts', created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE paper_references (
    id TEXT PRIMARY KEY, paper_id TEXT, raw_ref TEXT, matched_paper_id TEXT, confidence REAL);
"""


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    db.commit()
    return db


def _seed_paper(db, pid, project_id, title, author="", abstract=None, year=None):
    db.execute(
        """INSERT INTO documents (id, user_id, project_id, title, author, abstract, year, filename, file_path, file_type)
           VALUES (?, 'u1', ?, ?, ?, ?, ?, ?, ?, 'pdf')""",
        (pid, project_id, title, author, abstract, year, f"{pid}.pdf", f"/tmp/{pid}.pdf"),
    )
    db.commit()


def _seed_chunk(db, cid, doc_id, content, index=0, page=None):
    db.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content, page_number) VALUES (?, ?, ?, ?, ?)",
        (cid, doc_id, index, content, page),
    )
    db.commit()


class _FakeEmbedder:
    def __init__(self, dims=16):
        self.dims = dims

    def embed(self, texts):
        out = []
        for text in texts:
            vec = [0.0] * self.dims
            for ch in text.lower():
                vec[ord(ch) % self.dims] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class _EmptyResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"items": []}}


def _weight(edges, a, b):
    for e in edges:
        if {e["source"], e["target"]} == {a, b}:
            return e["weight"]
    return 0.0


def test_enrichment_falls_back_when_crossref_unreachable():
    db = _db()
    _seed_paper(db, "p1", "proj1", "A Survey of Quantum Machine Learning Methods")
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    with patch("app.features.literature.metadata.requests.get", side_effect=Exception("offline")):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "unverified"
    assert paper["metadata_candidates"] == []
    service.save_enrichment(paper)
    saved = service.papers("u1", "proj1")[0]
    assert "A Survey of Quantum Machine Learning Methods (n.d.)." in saved["apa_reference"]


def test_enrichment_marks_verified_with_doi_authors_and_apa():
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "message": {
                    "items": [
                        {
                            "title": ["A Survey of Quantum Machine Learning Methods"],
                            "DOI": "10.1000/xyz",
                            "published-print": {"date-parts": [[2021, 3, 1]]},
                            "author": [
                                {"family": "Smith", "given": "Jane"},
                                {"family": "Doe", "given": "John"},
                            ],
                            "abstract": "<jats:p>We review methods.</jats:p>",
                        }
                    ]
                }
            }

    db = _db()
    _seed_paper(db, "p1", "proj1", "A Survey of Quantum Machine Learning Methods")
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    with patch("app.features.literature.metadata.requests.get", return_value=_Resp()):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "verified"
    assert paper["doi"] == "10.1000/xyz"
    assert paper["year"] == 2021
    assert paper["authors"] == ["Smith, Jane", "Doe, John"]
    assert paper["abstract"] == "We review methods."
    ref = service.apa_reference(paper)
    assert "Smith, Jane; Doe, John (2021)." in ref
    assert "https://doi.org/10.1000/xyz" in ref


def test_similarity_edges_rank_related_papers_first():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Quantum Machine Learning Review")
    _seed_paper(db, "p2", "proj1", "Quantum Machine Learning Survey")
    _seed_paper(db, "p3", "proj1", "Classical Cooking Recipes")
    service = LiteratureService(db)
    papers = service.papers("u1", "proj1")

    with patch("app.features.literature.service.resolve_embedding_provider", return_value=_FakeEmbedder()):
        edges = service.similarity_edges("u1", papers)

    assert all(e["edge_type"] == "similarity" for e in edges)
    assert all(e["weight"] <= 1.0 for e in edges)
    assert _weight(edges, "p1", "p2") > _weight(edges, "p1", "p3")


def test_citation_edges_match_reference_list_to_title():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Attention Is All You Need")
    _seed_paper(db, "p2", "proj1", "Deep Learning Survey 2020")
    _seed_chunk(
        db,
        "c1",
        "p1",
        "Abstract text about attention.\nReferences\n[1] Goodfellow et al., Deep Learning Survey 2020, Nature.",
        index=0,
        page=5,
    )
    service = LiteratureService(db)
    papers = service.papers("u1", "proj1")

    edges, refs, unmatched = service.citation_edges(papers)

    pairs = {frozenset((e["source"], e["target"])) for e in edges if e["edge_type"] == "citation"}
    assert frozenset(("p1", "p2")) in pairs
    assert any(r["paper_id"] == "p1" and r["matched_paper_id"] == "p2" for r in refs)
    assert refs[0]["confidence"] >= 0.8
    assert all(u["paper_id"] == "p1" for u in unmatched)
    assert all(u["raw_ref"] for u in unmatched)


def test_build_map_produces_nodes_edges_clusters_and_layout():
    db = _db()
    titles = [
        "Quantum Machine Learning Review",
        "Quantum Machine Learning Survey",
        "Neural Architecture Search Overview",
    ]
    for i, title in enumerate(titles):
        _seed_paper(db, f"p{i + 1}", "proj1", title)
        _seed_chunk(db, f"c{i + 1}", f"p{i + 1}", f"Body text for {title}.", index=0, page=1)
    service = LiteratureService(db)

    with patch("app.features.literature.service.resolve_embedding_provider", return_value=_FakeEmbedder()), patch(
        "app.features.literature.metadata.requests.get", return_value=_EmptyResp()
    ):
        response = service.build_map("u1", "proj1")

    assert len(response.nodes) == 3
    assert all(n.x != 0.0 and n.y != 0.0 for n in response.nodes)
    assert all(n.cluster for n in response.nodes)
    assert len(response.edges) > 0
    assert sum(c.size for c in response.clusters) == 3
    assert all(n.meta and n.meta["doc_id"] for n in response.nodes)
    assert all(e.edge_type in ("citation", "similarity") for e in response.edges)


def test_cluster_prompt_includes_label_and_sources():
    llm = LiteratureLLMService(_db())
    system, prompt = llm.cluster_prompt(
        "Cluster 1",
        [{"title": "Alpha Paper", "page": 2, "content": "Some content."}],
    )
    assert "Cluster 1" in prompt
    assert "Alpha Paper" in prompt
    assert "Page 2" in prompt
    assert "research summarizer" in system


def test_cluster_sources_scoped_to_cluster_papers():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Alpha Topic Paper")
    _seed_paper(db, "p2", "proj1", "Beta Topic Paper")
    _seed_chunk(db, "c1", "p1", "Alpha content.", index=0, page=1)
    _seed_chunk(db, "c2", "p2", "Beta content.", index=0, page=2)
    service = LiteratureService(db)

    with patch("app.features.literature.service.resolve_embedding_provider", return_value=_FakeEmbedder()), patch(
        "app.features.literature.metadata.requests.get", return_value=_EmptyResp()
    ):
        response = service.build_map("u1", "proj1")
    service.save_checkpoint("u1", "proj1", response, "fp")

    llm = LiteratureLLMService(db)
    inputs = llm.cluster_inputs("u1", "proj1")
    assert inputs
    sources = llm.cluster_sources("u1", "proj1", inputs[0]["id"])
    assert len(sources) >= 1
    assert sources[0]["title"].lower() in {"alpha topic paper", "beta topic paper"}


def test_build_job_end_to_end_persists_checkpoint():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        db = sqlite3.connect(tmp_path)
        db.row_factory = sqlite3.Row
        db.executescript(_SCHEMA)
        _seed_paper(db, "p1", "proj1", "Quantum Machine Learning Review")
        _seed_paper(db, "p2", "proj1", "Quantum Machine Learning Survey")
        _seed_chunk(db, "c1", "p1", "Body of p1.", index=0, page=1)
        _seed_chunk(db, "c2", "p2", "Body of p2.", index=0, page=1)
        db.commit()
        db.close()

        def factory():
            conn = sqlite3.connect(tmp_path)
            conn.row_factory = sqlite3.Row
            return LiteratureService(conn)

        async def fake_label(self, user_id, project_id, clusters):
            return [{"id": c["id"], "label": f"L{c['id']}", "summary": "summary"} for c in clusters]

        with patch("app.features.literature.service.resolve_embedding_provider", return_value=_FakeEmbedder()), patch(
            "app.features.literature.metadata.requests.get", return_value=_EmptyResp()
        ), patch.object(LiteratureLLMService, "label_clusters", new=fake_label):
            job_id = jobs.start_build(factory, "u1", "proj1")
            job = jobs.wait_for_job(job_id, timeout=20.0)

        assert job is not None and job["status"] == "done", job

        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        response = LiteratureService(conn).get_map("u1", "proj1")
        assert len(response.nodes) == 2
        assert len(response.clusters) == 1
        assert response.clusters[0].label == "Lc1"
        assert response.generated_at is not None
        conn.close()
    finally:
        os.unlink(tmp_path)


# --- AI-judged graph edges ---------------------------------------------------


def test_related_pairs_returns_llm_similarity_edges():
    db = _db()
    papers = [
        {"id": "p1", "title": "Quantum Machine Learning Review", "year": 2021, "abstract": "Overview of quantum methods."},
        {"id": "p2", "title": "Quantum Machine Learning Survey", "year": 2022, "abstract": "Survey of quantum approaches."},
        {"id": "p3", "title": "Rural Farm Budgets", "year": 2014, "abstract": "Household budgets in the Eastern Cape."},
    ]
    llm = LiteratureLLMService(db)

    async def fake_call(self, user_id, system, user):
        return json.dumps([{"a": 1, "b": 2, "similarity": 0.9}])

    with patch.object(LiteratureLLMService, "_call", new=fake_call):
        edges = llm.related_pairs("u1", papers)

    assert len(edges) == 1
    assert {edges[0]["source"], edges[0]["target"]} == {"p1", "p2"}
    assert edges[0]["weight"] == 0.9
    assert edges[0]["edge_type"] == "similarity"


def test_related_pairs_returns_empty_when_no_model():
    db = _db()
    llm = LiteratureLLMService(db)
    papers = [{"id": "p1", "title": "A"}, {"id": "p2", "title": "B"}]
    with patch.object(LiteratureLLMService, "active_model", return_value=None):
        assert llm.related_pairs("u1", papers) == []


def test_match_reference_lines_matches_garbled_citations():
    db = _db()
    papers = [
        {"id": "p1", "title": "Attention Is All You Need", "authors": ["Vaswani, A."], "year": 2017},
        {"id": "p2", "title": "Deep Learning Survey", "authors": ["Goodfellow, I."], "year": 2020},
    ]
    refs = [{"paper_id": "p1", "raw_ref": "Goodfellow et al., Deep Learn Surv 2020."}]
    llm = LiteratureLLMService(db)

    async def fake_call(self, user_id, system, user):
        return json.dumps([{"ref_index": 1, "paper_index": 2, "confidence": 0.9}])

    with patch.object(LiteratureLLMService, "_call", new=fake_call):
        matched = llm.match_reference_lines("u1", refs, papers)

    assert len(matched) == 1
    assert matched[0]["paper_id"] == "p1"
    assert matched[0]["matched_paper_id"] == "p2"
    assert matched[0]["confidence"] == 0.9


def test_ai_edge_pass_merges_similarity_and_citation_edges():
    db = _db()
    service = LiteratureService(db)
    papers = [{"id": "p1", "title": "A"}, {"id": "p2", "title": "B"}]
    unmatched = [{"paper_id": "p1", "raw_ref": "B, garbled 2020."}]

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService,
        "related_pairs",
        return_value=[{"source": "p1", "target": "p2", "weight": 0.8, "edge_type": "similarity"}],
    ), patch.object(
        LiteratureLLMService,
        "match_reference_lines",
        return_value=[
            {"paper_id": "p1", "raw_ref": "B, garbled 2020.", "matched_paper_id": "p2", "confidence": 0.85}
        ],
    ):
        edges, refs = service._ai_edge_pass("u1", papers, unmatched, [])

    assert len(edges) == 2
    assert len(refs) == 1
    assert any(e["edge_type"] == "similarity" for e in edges)
    assert any(e["edge_type"] == "citation" for e in edges)


def test_ai_edge_pass_skips_pairs_already_connected():
    db = _db()
    service = LiteratureService(db)
    papers = [{"id": "p1", "title": "A"}, {"id": "p2", "title": "B"}]
    existing = [{"source": "p1", "target": "p2", "weight": 0.9, "edge_type": "similarity"}]

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService,
        "related_pairs",
        return_value=[{"source": "p1", "target": "p2", "weight": 0.8, "edge_type": "similarity"}],
    ), patch.object(LiteratureLLMService, "match_reference_lines", return_value=[]):
        edges, refs = service._ai_edge_pass("u1", papers, [], existing)

    assert edges == []
    assert refs == []


# --- LLM entry parsing robustness -------------------------------------------


def test_parse_json_extracts_object_from_code_fence_and_prose():
    raw = (
        'Sure, here you go:\n```json\n'
        '{"research_objective": "A", "key_findings": "B"}\n'
        '```\nHope that helps!'
    )
    parsed = LiteratureLLMService._parse_json(raw)
    assert parsed.get("research_objective") == "A"
    assert parsed.get("key_findings") == "B"


def test_parse_json_handles_json_arrays():
    raw = json.dumps([{"a": 1, "b": 2}])
    assert LiteratureLLMService._parse_json(raw) == [{"a": 1, "b": 2}]


def test_parse_json_returns_empty_for_prose():
    assert LiteratureLLMService._parse_json("This paper is great, no JSON here.") == {}


def test_generate_entry_retries_when_first_reply_is_not_json():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Widgets", abstract="This study examines widgets.")
    service = LiteratureService(db)
    llm = LiteratureLLMService(db)
    paper = {
        "id": "p1",
        "title": "Widgets",
        "authors": ["Wright, W."],
        "year": 2021,
        "abstract": "This study examines widgets.",
    }
    calls = {"n": 0}

    async def fake_call(self, user_id, system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return "The objective is clear and the findings matter."
        return json.dumps(
            {
                "research_objective": "To examine widgets.",
                "methodology": "A survey of widget makers.",
                "key_findings": "Widgets correlate with output.",
                "limitations": "Small sample.",
                "relevance": "Informs widget research.",
            }
        )

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        asyncio.run(llm._generate_entry(service, "u1", "proj1", paper, overwrite=False))

    entry = service.get_entry("p1", "u1")
    assert calls["n"] == 2
    assert entry is not None
    assert entry["research_objective"] == "To examine widgets."
    assert entry["methodology"] == "A survey of widget makers."
    assert entry["key_findings"] == "Widgets correlate with output."
    assert entry["auto_generated"] is True


def test_generate_entry_falls_back_when_llm_returns_no_fields():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Widgets", abstract="This study examines widgets.")
    service = LiteratureService(db)
    llm = LiteratureLLMService(db)
    paper = {
        "id": "p1",
        "title": "Widgets",
        "authors": [],
        "year": None,
        "abstract": "This study examines widgets.",
    }

    async def fake_call(self, user_id, system, user):
        return "No structured output here."

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        asyncio.run(llm._generate_entry(service, "u1", "proj1", paper, overwrite=False))

    entry = service.get_entry("p1", "u1")
    assert entry is not None
    assert "derived from abstract" in (entry["limitations"] or "")
    assert "This study examines widgets." in (entry["research_objective"] or "")


def test_entry_fields_returns_empty_for_array_reply():
    raw = json.dumps([{"research_objective": "A"}])
    assert LiteratureLLMService._entry_fields(raw) == {}


def test_generate_entry_falls_back_when_llm_returns_array():
    db = _db()
    _seed_paper(db, "p1", "proj1", "Widgets", abstract="This study examines widgets.")
    service = LiteratureService(db)
    llm = LiteratureLLMService(db)
    paper = {
        "id": "p1",
        "title": "Widgets",
        "authors": [],
        "year": None,
        "abstract": "This study examines widgets.",
    }

    async def fake_call(self, user_id, system, user):
        return json.dumps([{"research_objective": "ignored", "key_findings": "ignored"}])

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        asyncio.run(llm._generate_entry(service, "u1", "proj1", paper, overwrite=False))

    entry = service.get_entry("p1", "u1")
    assert entry is not None
    assert "derived from abstract" in (entry["limitations"] or "")
    assert "This study examines widgets." in (entry["research_objective"] or "")


def test_extract_paper_metadata_returns_empty_dict_for_array_reply():
    db = _db()
    llm = LiteratureLLMService(db)

    async def fake_call(self, user_id, system, user):
        return json.dumps([{"title": "ignored"}])

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        fields = llm.extract_paper_metadata("u1", "The first page of text", "widgets.pdf")

    assert fields == {}


def test_extract_paper_metadata_parses_object_reply():
    db = _db()
    llm = LiteratureLLMService(db)

    async def fake_call(self, user_id, system, user):
        return json.dumps({"title": "Widgets", "authors": ["Wright, W."], "year": 2021})

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        fields = llm.extract_paper_metadata("u1", "The first page of text", "widgets.pdf")

    assert fields["title"] == "Widgets"
    assert fields["year"] == 2021


def test_extract_paper_metadata_title_is_title_cased():
    db = _db()
    llm = LiteratureLLMService(db)

    async def fake_call(self, user_id, system, user):
        return json.dumps(
            {
                "title": "deep learning for crop yield prediction",
                "authors": ["Wright, W."],
                "year": 2021,
            }
        )

    with patch.object(LiteratureLLMService, "active_model", return_value={"id": "m"}), patch.object(
        LiteratureLLMService, "_call", new=fake_call
    ):
        fields = llm.extract_paper_metadata("u1", "The first page of text", "farming.pdf")

    assert fields["title"] == "Deep Learning For Crop Yield Prediction"


def test_paper_chunks_evenly_samples_full_document():
    db = _db()
    llm = LiteratureLLMService(db)
    for i in range(20):
        _seed_chunk(db, f"c{i}", "p1", f"chunk number {i}", index=i, page=(i // 3) + 1)

    chunks = llm._paper_chunks("p1", limit=5)

    assert len(chunks) == 5
    texts = [text for _, text in chunks]
    assert texts[0] == "chunk number 0"
    assert texts[-1] == "chunk number 19"


def test_paper_chunks_returns_all_when_fewer_than_limit():
    db = _db()
    llm = LiteratureLLMService(db)
    for i in range(3):
        _seed_chunk(db, f"c{i}", "p1", f"chunk number {i}", index=i, page=i + 1)

    chunks = llm._paper_chunks("p1", limit=5)

    assert [text for _, text in chunks] == ["chunk number 0", "chunk number 1", "chunk number 2"]
    assert [page for page, _ in chunks] == [1, 2, 3]


def test_paper_prompt_covers_sections_and_labels_pages():
    db = _db()
    llm = LiteratureLLMService(db)

    system, user = llm._paper_prompt(
        {"title": "Widgets", "authors": ["Wright, W."], "year": 2021, "abstract": "Brief abstract."},
        [(1, "Introduction text"), (4, "Methods text"), (7, "Discussion text")],
    )

    assert "Excerpt 1" in user and "Excerpt 3" in user
    assert "page 1" in user and "page 7" in user
    assert "Introduction text" in user and "Discussion text" in user
    assert "sections" in system and "abstract" in system
