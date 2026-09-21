import json
import sqlite3
from io import BytesIO

from docx import Document
from openpyxl import load_workbook

from app.features.export import dossier, snapshot as snapshot_mod, workbook

_SCHEMA = """
CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
CREATE TABLE documents (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, filename TEXT,
    file_path TEXT, file_type TEXT, author TEXT, year INTEGER, doi TEXT,
    abstract TEXT, verification_status TEXT, apa_reference TEXT, authors TEXT,
    metadata_user_edited INTEGER DEFAULT 0, journal TEXT, volume TEXT, issue TEXT,
    pages TEXT, publisher TEXT, url TEXT, paper_type TEXT, edition TEXT,
    issn TEXT, isbn TEXT);
CREATE TABLE literature_entries (
    paper_id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, citation TEXT,
    research_objective TEXT, methodology TEXT, key_findings TEXT, limitations TEXT,
    relevance TEXT, apa_reference TEXT, auto_generated INTEGER DEFAULT 0,
    user_edited TEXT, updated_at DATETIME);
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY, user_id TEXT, project_id TEXT, title TEXT, model_used TEXT,
    created_at DATETIME);
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, sources TEXT,
    model_used TEXT, created_at DATETIME);
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.execute("INSERT INTO projects (id, user_id, name) VALUES ('proj1', 'u1', 'My Thesis')")
    conn.commit()
    return conn


def _seed_paper(db, pid, title, *, authors=None, author=None, year=None, doi=None, **extra):
    columns = {
        "id": pid,
        "user_id": "u1",
        "project_id": "proj1",
        "title": title,
        "filename": f"{pid}.pdf",
        "file_path": f"/tmp/{pid}.pdf",
        "file_type": "pdf",
        "author": author,
        "year": year,
        "doi": doi,
        "authors": json.dumps(authors) if authors is not None else None,
        **extra,
    }
    keys = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    db.execute(f"INSERT INTO documents ({keys}) VALUES ({marks})", list(columns.values()))


def _seed_entry(db, paper_id, **fields):
    columns = {"paper_id": paper_id, "user_id": "u1", "project_id": "proj1", **fields}
    keys = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    db.execute(f"INSERT INTO literature_entries ({keys}) VALUES ({marks})", list(columns.values()))


# --- snapshot ---------------------------------------------------------------


def test_missing_author_is_marked_not_fabricated():
    db = _db()
    _seed_paper(db, "p1", "Deep Learning Survey", authors=None, year=None)
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")

    (paper,) = snap.papers
    assert paper.citation == snapshot_mod.AUTHOR_UNKNOWN
    assert "authors" in paper.missing_fields
    assert "year" in paper.missing_fields
    # An APA string still exists, but the paper is reported as incomplete.
    assert paper.apa_reference
    assert any("no author recorded" in item for item in snap.unresolved)


def test_provenance_reflects_verification_and_user_edits():
    db = _db()
    _seed_paper(db, "p1", "Verified", authors=["Smith, J."], year=2020,
                verification_status="verified")
    _seed_paper(db, "p2", "Guessed", authors=["Doe, J."], year=2021,
                verification_status="ai")
    _seed_paper(db, "p3", "Hand-edited", authors=["Roe, J."], year=2022,
                metadata_user_edited=1)
    _seed_paper(db, "p4", "Untouched", authors=["Poe, J."], year=2023)
    db.commit()

    by_title = {p.title: p for p in snapshot_mod.build(db, "u1", "proj1").papers}

    assert by_title["Verified"].provenance == "verified"
    assert by_title["Guessed"].provenance == "ai-suggested"
    assert by_title["Hand-edited"].provenance == "edited by you"
    assert by_title["Untouched"].provenance == snapshot_mod.UNENRICHED


def test_three_blank_states_are_distinguished():
    db = _db()
    _seed_paper(db, "p1", "No entry row", authors=["A, A."], year=2020)
    _seed_paper(db, "p2", "Auto generated", authors=["B, B."], year=2021)
    _seed_paper(db, "p3", "User cleared", authors=["C, C."], year=2022)
    _seed_paper(db, "p4", "Plain empty", authors=["D, D."], year=2023)
    db.commit()

    _seed_entry(db, "p2", auto_generated=1, key_findings="")
    _seed_entry(db, "p3", user_edited=json.dumps(["key_findings"]), key_findings="")
    _seed_entry(db, "p4", auto_generated=0, key_findings="")
    db.commit()

    by_title = {p.title: p for p in snapshot_mod.build(db, "u1", "proj1").papers}

    assert by_title["No entry row"].entry is None
    assert by_title["Auto generated"].entry.values["key_findings"] == snapshot_mod.NOT_GENERATED
    assert by_title["User cleared"].entry.values["key_findings"] == snapshot_mod.CLEARED_BY_YOU
    assert by_title["Plain empty"].entry.values["key_findings"] == snapshot_mod.EMPTY


def test_citation_to_deleted_document_is_marked_not_dropped():
    db = _db()
    _seed_paper(db, "p1", "Still Here", authors=["Smith, J."], year=2020)
    sources = [
        {
            "chunk_id": "c1",
            "title": "Still Here",
            "page": 2,
            "document_id": "p1",
            "apa_reference": "Smith, J. (2020). Still Here.",
            "citation": "Smith, 2020",
        },
        {
            "chunk_id": "c2",
            "title": "Removed Paper",
            "page": 7,
            "document_id": "p-gone",
            "apa_reference": "Doe, J. (2019). Removed Paper.",
            "citation": "Doe, 2019",
        },
    ]
    db.execute(
        "INSERT INTO chat_sessions (id, user_id, project_id, title, model_used, created_at)"
        " VALUES ('s1', 'u1', 'proj1', 'First pass', 'local:x', '2024-01-01')"
    )
    db.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, sources, created_at)"
        " VALUES ('m1', 's1', 'assistant', 'An answer.', ?, '2024-01-01')",
        (json.dumps(sources),),
    )
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")

    message = snap.sessions[0].messages[0]
    live, gone = message.sources
    assert live.deleted is False
    assert live.label == "Smith, 2020"
    assert gone.deleted is True
    assert gone.label == f"Doe, 2019 {snapshot_mod.NOT_IN_PROJECT}"
    assert any("no longer in this project" in item for item in snap.unresolved)


def test_snapshot_is_scoped_and_ordered_by_title():
    db = _db()
    _seed_paper(db, "p1", "Zeta", authors=["Z, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha", authors=["A, A."], year=2021)
    _seed_paper(db, "p3", "Other Project", authors=["O, O."], year=2022,
                project_id="proj2")
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")

    assert [p.title for p in snap.papers] == ["Alpha", "Zeta"]


# --- workbook ---------------------------------------------------------------


def test_workbook_carries_provenance_and_missing_columns():
    db = _db()
    _seed_paper(db, "p1", "Sourced Paper", authors=["Smith, J."], year=2020,
                doi="10.1000/abc", journal="Journal of Things",
                verification_status="verified")
    _seed_paper(db, "p2", "Unsourced Paper", authors=None, year=None)
    db.commit()

    data = workbook.render(snapshot_mod.build(db, "u1", "proj1"))
    sheet = load_workbook(BytesIO(data)).active

    headers = [cell.value for cell in sheet[1]]
    assert "Source" in headers
    assert "Missing metadata" in headers
    assert headers.index("DOI") >= 0

    rows = {row[0]: row for row in sheet.iter_rows(min_row=2, values_only=True)}
    sourced = rows["Sourced Paper"]
    assert sourced[headers.index("Source")] == "verified"
    assert sourced[headers.index("DOI")] == "10.1000/abc"
    assert sourced[headers.index("Missing metadata")] in (None, "")

    unsourced = rows["Unsourced Paper"]
    assert unsourced[headers.index("Citation (Author, Year)")] == snapshot_mod.AUTHOR_UNKNOWN
    missing = unsourced[headers.index("Missing metadata")]
    assert "authors" in missing and "year" in missing
    assert unsourced[headers.index("Year")] is None


def test_workbook_keeps_the_historical_column_order():
    db = _db()
    _seed_paper(db, "p1", "Sourced Paper", authors=["Smith, J."], year=2020)
    db.commit()

    data = workbook.render(snapshot_mod.build(db, "u1", "proj1"))
    headers = [cell.value for cell in load_workbook(BytesIO(data)).active[1]]

    assert headers[:8] == [
        "Paper Title",
        "Citation (Author, Year)",
        "Research Objective / Questions",
        "Methodology & Sample",
        "Key Findings",
        "Limitations & Gaps",
        "Relevance / Contribution",
        "APA Reference",
    ]


# --- dossier ----------------------------------------------------------------


def _paragraphs(data: bytes) -> list[str]:
    return [p.text for p in Document(BytesIO(data)).paragraphs]


def _section(data: bytes, heading: str) -> list[str]:
    """Paragraphs between `heading` and the next heading of the same level."""
    texts = [p.text for p in Document(BytesIO(data)).paragraphs]
    styles = [p.style.name for p in Document(BytesIO(data)).paragraphs]
    try:
        start = texts.index(heading)
    except ValueError:
        return []
    out = []
    for text, style in zip(texts[start + 1 :], styles[start + 1 :]):
        if style.startswith("Heading"):
            break
        out.append(text)
    return out



def test_dossier_cover_page_states_what_is_missing():
    db = _db()
    _seed_paper(db, "p1", "Complete Paper", authors=["Smith, J."], year=2020,
                verification_status="verified")
    _seed_paper(db, "p2", "Incomplete Paper", authors=None, year=None)
    db.commit()

    text = "\n".join(_paragraphs(dossier.render(snapshot_mod.build(db, "u1", "proj1"))))

    assert "My Thesis" in text
    assert "Before you rely on this" in text
    assert "no author recorded" in text
    assert "References with incomplete metadata" in text
    # The incomplete paper is flagged rather than presented as a clean reference.
    assert "Incomplete: authors" in text


def test_dossier_says_nothing_missing_when_project_is_clean():
    db = _db()
    _seed_paper(db, "p1", "Complete Paper", authors=["Smith, J."], year=2020,
                doi="10.1000/abc", journal="Journal of Things",
                verification_status="verified")
    _seed_entry(db, "p1", research_objective="To test.", methodology="Survey.",
                key_findings="It works.", limitations="Small n.", relevance="High.")
    db.commit()

    text = "\n".join(_paragraphs(dossier.render(snapshot_mod.build(db, "u1", "proj1"))))

    assert "Nothing was missing when this export ran." in text
    assert "To test." in text


def test_dossier_includes_answers_only_when_requested():
    db = _db()
    _seed_paper(db, "p1", "A Paper", authors=["Smith, J."], year=2020)
    db.execute(
        "INSERT INTO chat_sessions (id, user_id, project_id, title, created_at)"
        " VALUES ('s1', 'u1', 'proj1', 'First pass', '2024-01-01')"
    )
    db.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, sources, created_at)"
        " VALUES ('m1', 's1', 'assistant', 'The key finding was X.', '[]', '2024-01-01')"
    )
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")

    without = "\n".join(_paragraphs(dossier.render(snap, include_answers=False)))
    with_answers = "\n".join(_paragraphs(dossier.render(snap, include_answers=True)))

    assert "The key finding was X." not in without
    assert "Saved answers" not in without
    assert "The key finding was X." in with_answers
    assert "First pass" in with_answers


def test_dossier_references_are_sorted_deduplicated_and_hanging_indented():
    db = _db()
    _seed_paper(db, "p1", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p3", "Alpha Study", authors=["Alpha, A."], year=2021)
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")
    data = dossier.render(snap)

    assert _section(data, "References") == [
        "Alpha, A. (2021). Alpha Study.",
        "Zeta, Z. (2020). Zeta Study.",
    ]

    document = Document(BytesIO(data))
    numbered = [p for p in document.paragraphs if p.text.startswith("Alpha, A.")]
    assert numbered[0].paragraph_format.first_line_indent.pt == -36
