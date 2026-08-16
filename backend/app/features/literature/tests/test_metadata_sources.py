import json
import sqlite3
from unittest.mock import MagicMock, patch

from app.features.literature import metadata as metadata_sources
from app.features.literature.metadata import extract_doi, extract_issn, extract_year, heuristic_title
from app.features.literature.service import LiteratureService

_SCHEMA = """
CREATE TABLE documents (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, filename TEXT,
    file_path TEXT, file_type TEXT, author TEXT, year INTEGER, doi TEXT,
    abstract TEXT, verification_status TEXT, apa_reference TEXT, authors TEXT,
    metadata_user_edited INTEGER DEFAULT 0, extracted_doi TEXT, metadata_candidates TEXT);
CREATE TABLE chunks (
    id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
    page_number INTEGER, char_start INTEGER, char_end INTEGER, token_count INTEGER,
    embedded_at TEXT);
CREATE TABLE literature_entries (
    paper_id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, citation TEXT,
    research_objective TEXT, methodology TEXT, key_findings TEXT, limitations TEXT,
    relevance TEXT, apa_reference TEXT, auto_generated INTEGER DEFAULT 0,
    user_edited TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE paper_references (
    id TEXT PRIMARY KEY, paper_id TEXT, raw_ref TEXT, matched_paper_id TEXT, confidence REAL);
"""


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    db.commit()
    return db


def _seed_paper(db, pid, project_id, title, author="", year=None, authors=None, file_path=None, file_type="pdf"):
    db.execute(
        """INSERT INTO documents (id, user_id, project_id, title, author, year, authors,
                                 filename, file_path, file_type)
           VALUES (?, 'u1', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, project_id, title, author, year, json.dumps(authors or []),
         f"{pid}.pdf", file_path or f"/tmp/{pid}.pdf", file_type),
    )
    db.commit()


def _make_pdf(path, first_page_text):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), first_page_text, fontsize=12)
    doc.save(str(path))
    doc.close()


# --- heuristic extraction ---------------------------------------------------


def test_extract_doi_finds_doi_in_text():
    text = "Some header\nhttps://doi.org/10.1000/abc123 and more text here."
    assert extract_doi(text) == "10.1000/abc123"


def test_extract_doi_handles_line_wrapped_url():
    text = "International Journal of Things\nhttps://doi.org/10.1000/xyz\n1234 and following text"
    assert extract_doi(text) == "10.1000/xyz1234"


def test_extract_doi_finds_bare_doi_token():
    assert extract_doi("DOI: 10.1000/abc123") == "10.1000/abc123"


def test_extract_doi_returns_none_without_doi():
    assert extract_doi("No digital object identifiers here.") is None
    assert extract_doi(None) is None


def test_extract_issn_finds_issn():
    text = "ISSN 1234-5678 (print), e-ISSN 9876-543X"
    assert extract_issn(text) == "1234-5678"


def test_heuristic_title_picks_the_most_wordy_early_line():
    text = "Journal of Things\n\nA Comprehensive Survey of Deep Learning Techniques\nAbstract..."
    title = heuristic_title(text)
    assert title == "A Comprehensive Survey of Deep Learning Techniques"


def test_heuristic_title_ignores_journal_authors_issn_and_doi():
    first_page = """International Journal of Advanced Research in Computer Science
Vol. 12, No. 3, 2024
ISSN 2277-128X
https://doi.org/10.1000/xyz1234
Jane Doe, John Smith
An Intelligent Approach to Detecting Fake News on Social Media
Abstract: In this paper, we present a novel framework for detecting fake news
on social media platforms using a hybrid of machine learning and graph analysis."""
    assert heuristic_title(first_page) == "An Intelligent Approach to Detecting Fake News on Social Media"


def test_heuristic_title_returns_none_for_boilerplate_only():
    text = "Journal of Things\nISSN 1234-5678\nVol. 1, No. 1\nhttps://doi.org/10.1000/x"
    assert heuristic_title(text) is None


def test_extract_year_finds_publication_year():
    assert extract_year("Copyright 1998, published 2021") == 1998
    assert extract_year("No years at all") is None


# --- source parsing ---------------------------------------------------------


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_crossref_by_title_parses_record_with_year_fallback():
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Deep Learning Survey"],
                    "DOI": "10.1000/survey",
                    "published-print": {"date-parts": [[2021, 5, 1]]},
                    "author": [
                        {"family": "Smith", "given": "Jane"},
                        {"family": "Doe", "given": "John"},
                    ],
                    "abstract": "<jats:p>We survey the field.</jats:p>",
                }
            ]
        }
    }
    with patch("app.features.literature.metadata.requests.get", return_value=_FakeResp(payload)):
        records = metadata_sources.crossref_by_title("Deep Learning Survey")

    assert len(records) == 1
    record = records[0]
    assert record["source"] == "crossref"
    assert record["doi"] == "10.1000/survey"
    assert record["year"] == 2021
    assert record["authors"] == ["Smith, Jane", "Doe, John"]
    assert record["abstract"] == "We survey the field."


def test_crossref_by_doi_sets_confidence_one():
    payload = {
        "message": {
            "title": ["Exact Paper"],
            "DOI": "10.1000/exact",
            "issued": {"date-parts": [[2019]]},
            "author": [{"family": "Kim", "given": "Soo"}],
        }
    }
    with patch("app.features.literature.metadata.requests.get", return_value=_FakeResp(payload)):
        record = metadata_sources.crossref_by_doi("10.1000/exact")

    assert record is not None
    assert record["confidence"] == 1.0
    assert record["authors"] == ["Kim, Soo"]
    assert record["year"] == 2019


def test_openalex_by_title_parses_authors_and_abstract():
    payload = {
        "results": [
            {
                "title": "Graph Neural Networks",
                "doi": "https://doi.org/10.2000/gnn",
                "publication_year": 2022,
                "authorships": [
                    {"author": {"display_name": "Ada Lovelace"}},
                    {"author": {"display_name": "Turing, Alan"}},
                ],
                "abstract_inverted_index": {"networks": [0], "graph": [1]},
                "primary_location": {"source": {"display_name": "Neural Journal"}},
            }
        ]
    }
    with patch("app.features.literature.metadata.requests.get", return_value=_FakeResp(payload)):
        records = metadata_sources.openalex_by_title("Graph Neural Networks")

    assert len(records) == 1
    record = records[0]
    assert record["source"] == "openalex"
    assert record["doi"] == "10.2000/gnn"
    assert record["authors"] == ["Lovelace, Ada", "Turing, Alan"]
    assert record["abstract"] == "networks graph"
    assert record["container_title"] == "Neural Journal"


# --- enrichment flow --------------------------------------------------------


def test_enrich_verifies_via_doi_extracted_from_pdf(tmp_path):
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, "Some journal header\nhttps://doi.org/10.1000/abc123\nDeep Learning Survey\nAbstract…")
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(pdf))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    record = {
        "source": "crossref",
        "doi": "10.1000/abc123",
        "title": "Deep Learning Survey",
        "authors": ["Lee, Sam"],
        "year": 2021,
        "abstract": "An abstract.",
    }
    mock_title = MagicMock()
    with patch("app.features.literature.metadata.crossref_by_doi", return_value=record), patch(
        "app.features.literature.metadata.crossref_by_title", mock_title
    ):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "verified"
    assert paper["extracted_doi"] == "10.1000/abc123"
    assert paper["doi"] == "10.1000/abc123"
    assert paper["year"] == 2021
    assert paper["authors"] == ["Lee, Sam"]
    assert paper["title"] == "Deep Learning Survey"
    assert paper["abstract"] == "An abstract."
    mock_title.assert_not_called()


def test_enrich_cross_checks_title_match_across_sources(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Deep Learning Survey", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    crossref_record = {
        "source": "crossref",
        "doi": "10.1000/survey",
        "title": "Deep Learning Survey",
        "authors": ["Smith, Jane"],
        "year": 2021,
    }
    with patch("app.features.literature.metadata.crossref_by_title", return_value=[crossref_record]), patch(
        "app.features.literature.metadata.openalex_by_title", return_value=[]
    ):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "verified"
    assert paper["doi"] == "10.1000/survey"


def test_enrich_rejects_author_mismatch(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Deep Learning Survey", author="Jones, Bob",
                file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    crossref_record = {
        "source": "crossref",
        "doi": "10.1000/survey",
        "title": "Deep Learning Survey",
        "authors": ["Smith, Jane"],
        "year": 2021,
    }
    with patch("app.features.literature.metadata.crossref_by_title", return_value=[crossref_record]), patch(
        "app.features.literature.metadata.openalex_by_title", return_value=[]
    ):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "unverified"
    assert len(paper["metadata_candidates"]) == 1


def test_enrich_rejects_year_mismatch_from_pdf(tmp_path):
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, "A Deep Learning Survey\nPublished 1999\nAbstract…")
    db = _db()
    _seed_paper(db, "p1", "proj1", "Deep Learning Survey", file_path=str(pdf))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    crossref_record = {
        "source": "crossref",
        "doi": "10.1000/survey",
        "title": "A Deep Learning Survey",
        "authors": ["Smith, Jane"],
        "year": 2023,
    }
    with patch("app.features.literature.metadata.crossref_by_title", return_value=[crossref_record]), patch(
        "app.features.literature.metadata.openalex_by_title", return_value=[]
    ):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "unverified"


# --- LLM second layer -------------------------------------------------------


def test_enrich_verifies_via_llm_provided_doi(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    ai_fields = {
        "title": "The Correct Paper Title",
        "authors": ["Kim, Soo"],
        "year": 2021,
        "doi": "10.1000/right",
        "journal": "Journal of Things",
    }
    record = {
        "source": "crossref",
        "doi": "10.1000/right",
        "title": "The Correct Paper Title",
        "authors": ["Kim, Soo"],
        "year": 2021,
        "abstract": "An abstract.",
    }
    with patch.object(LiteratureService, "_ai_extract", return_value=ai_fields), patch(
        "app.features.literature.metadata.crossref_by_doi", return_value=record
    ), patch("app.features.literature.metadata.crossref_by_title", return_value=[]), patch(
        "app.features.literature.metadata.openalex_by_title", return_value=[]
    ):
        paper = service.enrich(paper, user_id="u1")

    assert paper["verification_status"] == "verified"
    assert paper["title"] == "The Correct Paper Title"
    assert paper["doi"] == "10.1000/right"
    assert paper["authors"] == ["Kim, Soo"]


def test_enrich_applies_ai_metadata_when_no_external_match(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    ai_fields = {
        "title": "An Intelligent Approach to Detecting Fake News",
        "authors": ["Doe, Jane", "Smith, John"],
        "year": 2024,
        "doi": None,
        "journal": "International Journal of Things",
    }
    with patch.object(LiteratureService, "_ai_extract", return_value=ai_fields), patch(
        "app.features.literature.metadata.crossref_by_title", return_value=[]
    ), patch("app.features.literature.metadata.openalex_by_title", return_value=[]):
        paper = service.enrich(paper, user_id="u1")

    assert paper["verification_status"] == "ai"
    assert paper["title"] == "An Intelligent Approach to Detecting Fake News"
    assert paper["authors"] == ["Doe, Jane", "Smith, John"]
    assert paper["year"] == 2024
    assert any(c["source"] == "ai" for c in paper["metadata_candidates"])

    service.save_enrichment(paper)
    saved = service.papers("u1", "proj1")[0]
    assert saved["title"] == "An Intelligent Approach to Detecting Fake News"
    assert "Doe, Jane; Smith, John (2024)." in saved["apa_reference"]


def test_enrich_uses_llm_title_to_query_external_sources(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    ai_fields = {
        "title": "An Intelligent Approach to Detecting Fake News on Social Media",
        "authors": ["Doe, Jane"],
        "year": 2024,
    }
    crossref_record = {
        "source": "crossref",
        "doi": "10.1000/fakenews",
        "title": "An Intelligent Approach to Detecting Fake News on Social Media",
        "authors": ["Doe, Jane", "Roe, Sam"],
        "year": 2024,
    }
    with patch.object(LiteratureService, "_ai_extract", return_value=ai_fields), patch(
        "app.features.literature.metadata.crossref_by_title", return_value=[crossref_record]
    ) as crossref, patch("app.features.literature.metadata.openalex_by_title", return_value=[]):
        paper = service.enrich(paper, user_id="u1")

    crossref.assert_called_once_with(
        "An Intelligent Approach to Detecting Fake News on Social Media"
    )
    assert paper["verification_status"] == "verified"
    assert paper["doi"] == "10.1000/fakenews"
    assert paper["title"] == "An Intelligent Approach to Detecting Fake News on Social Media"


def test_enrich_without_llm_skips_ai_layer(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Deep Learning Survey", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    paper = service.papers("u1", "proj1")[0]

    with patch("app.features.literature.metadata.crossref_by_title", return_value=[]), patch(
        "app.features.literature.metadata.openalex_by_title", return_value=[]
    ):
        paper = service.enrich(paper)

    assert paper["verification_status"] == "unverified"
    assert not any(c.get("source") == "ai" for c in paper["metadata_candidates"])


# --- candidate picker -------------------------------------------------------


def test_apply_candidate_persists_verified_metadata(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(tmp_path / "none.pdf"))
    candidates = [
        {
            "source": "crossref",
            "doi": "10.1000/wrong",
            "title": "A Similar Title",
            "authors": ["Jones, Bob"],
            "year": 2001,
        },
        {
            "source": "openalex",
            "doi": "10.1000/right",
            "title": "The Correct Paper",
            "authors": ["Kim, Soo", "Lee, Sam"],
            "year": 2018,
            "abstract": "The right abstract.",
        },
    ]
    db.execute("UPDATE documents SET metadata_candidates = ? WHERE id = 'p1'", (json.dumps(candidates),))
    db.commit()
    service = LiteratureService(db)
    service.ensure_entries("u1", "proj1")

    meta = service.apply_candidate("p1", "u1", "proj1", 1)

    assert meta is not None
    assert meta["verification_status"] == "verified"
    assert meta["title"] == "The Correct Paper"
    assert meta["authors"] == ["Kim, Soo", "Lee, Sam"]
    assert meta["year"] == 2018
    assert meta["candidates"] == []
    assert meta["metadata_user_edited"] is True

    row = db.execute("SELECT * FROM documents WHERE id = 'p1'").fetchone()
    assert row["verification_status"] == "verified"
    assert json.loads(row["metadata_candidates"]) == []

    entry = service.get_entry("p1", "u1")
    assert entry["citation"] == "Kim, 2018"
    assert "The Correct Paper" in entry["apa_reference"]


def test_apply_candidate_rejects_out_of_range(tmp_path):
    db = _db()
    _seed_paper(db, "p1", "proj1", "Uploaded File Name", file_path=str(tmp_path / "none.pdf"))
    service = LiteratureService(db)
    assert service.apply_candidate("p1", "u1", "proj1", 0) is None
