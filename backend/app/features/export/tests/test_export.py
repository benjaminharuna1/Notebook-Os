import asyncio
import json
import sqlite3
from io import BytesIO

from docx import Document
from fastapi import HTTPException
from openpyxl import load_workbook

from app.features.export import (
    conversation,
    dossier,
    references,
    router,
    snapshot as snapshot_mod,
)

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


def _seed_session(db, sid="s1", *, user_id="u1", project_id="proj1", title="First pass",
                  model_used=None):
    db.execute(
        "INSERT INTO chat_sessions (id, user_id, project_id, title, model_used, created_at)"
        " VALUES (?, ?, ?, ?, ?, '2024-01-01')",
        (sid, user_id, project_id, title, model_used),
    )


def _seed_message(db, mid, sid, role, content, *, sources=None, model_used=None):
    db.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, sources, model_used, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, '2024-01-01')",
        (
            mid,
            sid,
            role,
            content,
            json.dumps(sources) if sources is not None else None,
            model_used,
        ),
    )


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
    _seed_paper(db, "p3", "Hand Edited", authors=["Roe, J."], year=2022,
                metadata_user_edited=1)
    _seed_paper(db, "p4", "Untouched", authors=["Poe, J."], year=2023)
    db.commit()

    by_title = {p.title: p for p in snapshot_mod.build(db, "u1", "proj1").papers}

    assert by_title["Verified"].provenance == "verified"
    assert by_title["Guessed"].provenance == "ai-suggested"
    assert by_title["Hand Edited"].provenance == "edited by you"
    assert by_title["Untouched"].provenance == snapshot_mod.UNENRICHED


def test_three_blank_states_are_distinguished():
    db = _db()
    _seed_paper(db, "p1", "No Entry Row", authors=["A, A."], year=2020)
    _seed_paper(db, "p2", "Auto Generated", authors=["B, B."], year=2021)
    _seed_paper(db, "p3", "User Cleared", authors=["C, C."], year=2022)
    _seed_paper(db, "p4", "Plain Empty", authors=["D, D."], year=2023)
    db.commit()

    _seed_entry(db, "p2", auto_generated=1, key_findings="")
    _seed_entry(db, "p3", user_edited=json.dumps(["key_findings"]), key_findings="")
    _seed_entry(db, "p4", auto_generated=0, key_findings="")
    db.commit()

    by_title = {p.title: p for p in snapshot_mod.build(db, "u1", "proj1").papers}

    assert by_title["No Entry Row"].entry is None
    assert by_title["Auto Generated"].entry.values["key_findings"] == snapshot_mod.NOT_GENERATED
    assert by_title["User Cleared"].entry.values["key_findings"] == snapshot_mod.CLEARED_BY_YOU
    assert by_title["Plain Empty"].entry.values["key_findings"] == snapshot_mod.EMPTY


def test_snapshot_is_scoped_and_ordered_by_title():
    db = _db()
    _seed_paper(db, "p1", "Zeta", authors=["Z, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha", authors=["A, A."], year=2021)
    _seed_paper(db, "p3", "Other Project", authors=["O, O."], year=2022,
                project_id="proj2")
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")

    assert [p.title for p in snap.papers] == ["Alpha", "Zeta"]


# --- dossier: xlsx ----------------------------------------------------------


def _notes_sheet(data: bytes):
    return load_workbook(BytesIO(data))[dossier.NOTES_SHEET]


def test_dossier_xlsx_notes_sheet_carries_provenance_and_missing_columns():
    db = _db()
    _seed_paper(db, "p1", "Sourced Paper", authors=["Smith, J."], year=2020,
                doi="10.1000/abc", journal="Journal of Things",
                verification_status="verified")
    _seed_paper(db, "p2", "Unsourced Paper", authors=None, year=None)
    db.commit()

    sheet = _notes_sheet(dossier.render_xlsx(snapshot_mod.build(db, "u1", "proj1")))

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


def test_dossier_xlsx_notes_sheet_keeps_the_historical_column_order():
    db = _db()
    _seed_paper(db, "p1", "Sourced Paper", authors=["Smith, J."], year=2020)
    db.commit()

    sheet = _notes_sheet(dossier.render_xlsx(snapshot_mod.build(db, "u1", "proj1")))
    headers = [cell.value for cell in sheet[1]]

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


def test_dossier_carries_the_same_sections_in_both_formats():
    db = _db()
    _seed_paper(db, "p1", "Complete Paper", authors=["Smith, J."], year=2020,
                verification_status="verified")
    _seed_paper(db, "p2", "Incomplete Paper", authors=None, year=None)
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")
    workbook = load_workbook(BytesIO(dossier.render_xlsx(snap)))
    words = "\n".join(_paragraphs(dossier.render_docx(snap)))

    assert workbook.sheetnames == [
        dossier.SUMMARY_SHEET,
        dossier.NOTES_SHEET,
        dossier.REFERENCES_SHEET,
    ]
    # Section 1 — the same unresolved notice as the Word cover page.
    summary = [row[1] for row in workbook[dossier.SUMMARY_SHEET].iter_rows(min_row=2, values_only=True)]
    assert "My Thesis" in summary
    assert any("no author recorded" in str(item) for item in summary)
    assert "no author recorded" in words

    # Section 2 — the same bibliography, laid out by the one shared definition.
    # Blank strings round-trip through openpyxl as empty cells (None).
    ref_rows = [list(row) for row in workbook[dossier.REFERENCES_SHEET].iter_rows(min_row=2, values_only=True)]
    expected = [
        [value if value != "" else None for value in row]
        for row in references.table(references.compile(snap))
    ]
    assert ref_rows == expected

    # Section 3 — the same papers.
    note_rows = [row[0] for row in workbook[dossier.NOTES_SHEET].iter_rows(min_row=2, values_only=True)]
    assert note_rows == ["Complete Paper", "Incomplete Paper"]


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

    text = "\n".join(_paragraphs(dossier.render_docx(snapshot_mod.build(db, "u1", "proj1"))))

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

    text = "\n".join(_paragraphs(dossier.render_docx(snapshot_mod.build(db, "u1", "proj1"))))

    assert "Nothing was missing when this export ran." in text
    assert "To test." in text


def test_dossier_never_includes_conversations():
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
    text = "\n".join(_paragraphs(dossier.render_docx(snap)))
    refs_text = "\n".join(_paragraphs(references.render_docx(snap)))

    for artifact in (text, refs_text):
        assert "The key finding was X." not in artifact
        assert "Saved answers" not in artifact
        assert "First pass" not in artifact


def test_dossier_references_are_sorted_deduplicated_and_hanging_indented():
    db = _db()
    _seed_paper(db, "p1", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p3", "Alpha Study", authors=["Alpha, A."], year=2021)
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")
    data = dossier.render_docx(snap)

    assert _section(data, "References") == [
        "Alpha, A. (2021). Alpha Study.",
        "Zeta, Z. (2020). Zeta Study.",
    ]

    document = Document(BytesIO(data))
    numbered = [p for p in document.paragraphs if p.text.startswith("Alpha, A.")]
    assert numbered[0].paragraph_format.first_line_indent.pt == -36


# --- references -------------------------------------------------------------


def test_references_compile_dedupes_sorts_and_flags_incomplete():
    db = _db()
    _seed_paper(db, "p1", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p3", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p4", "Unattributed Report", authors=None, year=None)
    db.commit()

    refs = references.compile(snapshot_mod.build(db, "u1", "proj1"))

    assert [r.apa for r in refs] == [
        "Alpha, A. (2021). Alpha Study.",
        "Unattributed Report (n.d.).",
        "Zeta, Z. (2020). Zeta Study.",
    ]
    by_title = {r.title: r for r in refs}
    assert by_title["Alpha Study"].complete is True
    assert by_title["Unattributed Report"].complete is False
    assert by_title["Unattributed Report"].authors == snapshot_mod.AUTHOR_UNKNOWN
    assert "authors" in by_title["Unattributed Report"].missing_fields


def test_references_repair_an_all_caps_title():
    db = _db()
    _seed_paper(db, "p1", "DEEP LEARNING FOR CROP YIELD PREDICTION",
                authors=["Smith, J."], year=2020, verification_status="verified")
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")
    (paper,) = snap.papers
    (ref,) = references.compile(snap)

    # The title is normalised once, so the notes, the Title column and the
    # reference all read the same.
    assert paper.title == "Deep Learning for Crop Yield Prediction"
    assert ref.title == "Deep Learning for Crop Yield Prediction"
    assert ref.apa == "Smith, J. (2020). Deep Learning for Crop Yield Prediction."

    sheet = load_workbook(BytesIO(references.render_xlsx(snap))).active
    headers = [c.value for c in sheet[1]]
    row = next(sheet.iter_rows(min_row=2, values_only=True))
    assert row[headers.index("Title")] == "Deep Learning for Crop Yield Prediction"
    assert row[headers.index("APA Reference")] == ref.apa


def test_references_repair_a_shouting_title_already_stored_in_the_reference():
    db = _db()
    _seed_paper(db, "p1", "DEEP LEARNING FOR CROPS", authors=["Smith, J."], year=2020,
                apa_reference="Smith, J. (2020). DEEP LEARNING FOR CROPS. JOURNAL OF THINGS.")
    db.commit()

    (ref,) = references.compile(snapshot_mod.build(db, "u1", "proj1"))

    # The embedded title is repaired; the rest of the stored reference, and the
    # journal, are left exactly as they were.
    assert ref.apa == "Smith, J. (2020). Deep Learning for Crops. JOURNAL OF THINGS."


def test_references_docx_keeps_incomplete_entries_in_their_own_section():
    db = _db()
    _seed_paper(db, "p1", "Complete Paper", authors=["Smith, J."], year=2020)
    _seed_paper(db, "p2", "Incomplete Paper", authors=None, year=None)
    db.commit()

    text = "\n".join(_paragraphs(references.render_docx(snapshot_mod.build(db, "u1", "proj1"))))

    assert "References" in text
    assert "References with incomplete metadata" in text
    assert "Smith, J. (2020). Complete Paper." in text
    assert "Incomplete Paper (n.d.)." in text
    assert "Incomplete: authors" in text


def test_references_docx_says_so_when_there_are_none():
    db = _db()
    db.commit()

    text = "\n".join(_paragraphs(references.render_docx(snapshot_mod.build(db, "u1", "proj1"))))

    assert "This project has no references yet." in text


def test_dossier_and_references_export_describe_the_gap_identically():
    db = _db()
    _seed_paper(db, "p1", "Incomplete Paper", authors=None, year=None)
    db.commit()
    snap = snapshot_mod.build(db, "u1", "proj1")

    dossier_text = "\n".join(_paragraphs(dossier.render_docx(snap)))
    refs_text = "\n".join(_paragraphs(references.render_docx(snap)))

    assert "Incomplete: authors, year, doi, journal" in dossier_text
    assert "Incomplete: authors, year, doi, journal" in refs_text


def test_references_xlsx_lists_every_reference_with_its_gaps():
    db = _db()
    _seed_paper(db, "p1", "Complete Paper", authors=["Smith, J."], year=2020,
                doi="10.1000/abc", journal="Journal of Things", verification_status="verified")
    _seed_paper(db, "p2", "Incomplete Paper", authors=None, year=None)
    db.commit()

    data = references.render_xlsx(snapshot_mod.build(db, "u1", "proj1"))
    sheet = load_workbook(BytesIO(data)).active

    headers = [c.value for c in sheet[1]]
    assert headers == references.HEADERS
    rows = {row[2]: row for row in sheet.iter_rows(min_row=2, values_only=True)}
    assert set(rows) == {"Complete Paper", "Incomplete Paper"}

    complete = rows["Complete Paper"]
    assert complete[headers.index("DOI")] == "10.1000/abc"
    assert complete[headers.index("Source")] == "verified"
    assert complete[headers.index("Missing metadata")] in (None, "")

    incomplete = rows["Incomplete Paper"]
    assert incomplete[headers.index("Authors")] == snapshot_mod.AUTHOR_UNKNOWN
    assert "authors" in incomplete[headers.index("Missing metadata")]


# --- router: the resource x format matrix -----------------------------------


def _call(coro):
    return asyncio.run(coro)


def test_router_serves_both_resources_in_both_formats():
    db = _db()
    _seed_paper(db, "p1", "A Paper", authors=["Smith, J."], year=2020,
                verification_status="verified")
    db.commit()
    user = {"id": "u1"}

    dossier_docx = _call(router.export_dossier("proj1", "docx", user, db))
    dossier_xlsx = _call(router.export_dossier("proj1", "xlsx", user, db))
    refs_docx = _call(router.export_references("proj1", "docx", user, db))
    refs_xlsx = _call(router.export_references("proj1", "xlsx", user, db))

    assert dossier_docx.media_type.endswith("wordprocessingml.document")
    assert refs_docx.media_type.endswith("wordprocessingml.document")
    assert dossier_xlsx.media_type.endswith("spreadsheetml.sheet")
    assert refs_xlsx.media_type.endswith("spreadsheetml.sheet")

    assert dossier_docx.headers["content-disposition"] == (
        'attachment; filename="my-thesis-dossier.docx"'
    )
    assert dossier_xlsx.headers["content-disposition"] == (
        'attachment; filename="my-thesis-dossier.xlsx"'
    )
    assert refs_docx.headers["content-disposition"] == (
        'attachment; filename="my-thesis-references.docx"'
    )
    assert refs_xlsx.headers["content-disposition"] == (
        'attachment; filename="my-thesis-references.xlsx"'
    )

    # Every payload is a real file of the promised kind.
    assert all(r.body.startswith(b"PK") for r in (dossier_docx, dossier_xlsx, refs_docx, refs_xlsx))
    assert Document(BytesIO(dossier_docx.body)).paragraphs
    assert load_workbook(BytesIO(refs_xlsx.body)).active["A1"].value == "Authors"


def test_router_dossier_xlsx_is_the_dossier_not_a_bare_matrix():
    db = _db()
    _seed_paper(db, "p1", "A Paper", authors=["Smith, J."], year=2020)
    db.commit()

    xlsx = _call(router.export_dossier("proj1", "xlsx", {"id": "u1"}, db))
    workbook = load_workbook(BytesIO(xlsx.body))

    assert workbook.sheetnames == [
        dossier.SUMMARY_SHEET,
        dossier.NOTES_SHEET,
        dossier.REFERENCES_SHEET,
    ]
    headers = [c.value for c in workbook[dossier.NOTES_SHEET][1]]
    assert headers[0] == "Paper Title"
    assert "Source" in headers


def test_router_refuses_project_without_papers():
    db = _db()
    db.commit()

    try:
        _call(router.export_references("proj1", "docx", {"id": "u1"}, db))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "no papers" in exc.detail
    else:
        raise AssertionError("expected an HTTPException for a project with no papers")


# --- conversation: the session report ---------------------------------------


def _seed_conversation(db, *, source_document="p1"):
    _seed_session(db, "s1", title="First pass", model_used="qwen2.5-0.5b")
    _seed_message(db, "m1", "s1", "user", "What did the paper conclude?")
    _seed_message(
        db,
        "m2",
        "s1",
        "assistant",
        "It concluded that yields improve.",
        sources=[
            {
                "chunk_id": "c1",
                "title": "Deep Learning Survey",
                "page": 4,
                "document_id": source_document,
                "apa_reference": "Smith, J. (2020). Deep Learning Survey.",
            }
        ],
    )
    db.commit()


def test_conversation_export_includes_questions_and_answers():
    db = _db()
    _seed_paper(db, "p1", "Deep Learning Survey", authors=["Smith, J."], year=2020)
    _seed_conversation(db)
    db.commit()

    text = "\n".join(
        _paragraphs(conversation.render_docx(conversation.build(db, "u1", "s1")))
    )

    assert "What did the paper conclude?" in text
    assert "It concluded that yields improve." in text
    assert "Smith, J. (2020). Deep Learning Survey. (p. 4)" in text
    # The cited paper is still in the library, so nothing is flagged.
    assert snapshot_mod.NOT_IN_PROJECT not in text


def test_conversation_export_marks_citation_to_deleted_document():
    db = _db()
    # No `documents` row for the cited id: the paper was deleted after the chat.
    _seed_conversation(db, source_document="deleted-paper")
    db.commit()

    report = conversation.build(db, "u1", "s1")
    text = "\n".join(_paragraphs(conversation.render_docx(report)))

    # The answer survives, the captured citation survives, and the loss is marked.
    assert "It concluded that yields improve." in text
    assert "Smith, J. (2020). Deep Learning Survey." in text
    assert snapshot_mod.NOT_IN_PROJECT in text
    assert any("no longer in this project" in item for item in report.unresolved)
    assert "no longer in this project" in text


def test_conversation_export_keeps_web_sources_unmarked():
    db = _db()
    _seed_session(db, "s1")
    _seed_message(
        db,
        "m1",
        "s1",
        "assistant",
        "From the web.",
        sources=[
            {
                "chunk_id": "c1",
                "title": "A Web Page",
                "page": None,
                "document_id": None,
                "apa_reference": "",
            }
        ],
    )
    db.commit()

    text = "\n".join(
        _paragraphs(conversation.render_docx(conversation.build(db, "u1", "s1")))
    )

    assert "A Web Page" in text
    assert snapshot_mod.NOT_IN_PROJECT not in text


def test_conversation_export_states_project_date_and_message_count():
    db = _db()
    _seed_conversation(db)
    db.commit()

    text = "\n".join(
        _paragraphs(conversation.render_docx(conversation.build(db, "u1", "s1")))
    )

    assert "First pass" in text
    assert "My Thesis" in text
    assert "Exported" in text
    assert "2 message(s)" in text


def test_conversation_export_is_scoped_to_owner():
    db = _db()
    _seed_conversation(db)
    db.commit()

    assert conversation.build(db, "someone-else", "s1") is None


def test_router_serves_conversation_as_docx():
    db = _db()
    _seed_paper(db, "p1", "Deep Learning Survey", authors=["Smith, J."], year=2020)
    _seed_conversation(db)
    db.commit()

    response = _call(router.export_conversation("proj1", "s1", "docx", {"id": "u1"}, db))

    assert response.media_type.endswith("wordprocessingml.document")
    assert response.headers["content-disposition"] == (
        'attachment; filename="first-pass-conversation.docx"'
    )
    assert response.body.startswith(b"PK")


def test_router_refuses_empty_conversation():
    db = _db()
    _seed_session(db, "s1")
    db.commit()

    try:
        _call(router.export_conversation("proj1", "s1", "docx", {"id": "u1"}, db))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "empty" in exc.detail
    else:
        raise AssertionError("expected an HTTPException for an empty conversation")


def test_router_404s_for_missing_conversation():
    db = _db()
    db.commit()

    try:
        _call(router.export_conversation("proj1", "nope", "docx", {"id": "u1"}, db))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected a 404 for a missing conversation")


# --- read batching: no query per row ----------------------------------------


class _CountingDb:
    """Wraps a connection to record the SQL each build issues."""

    def __init__(self, db):
        self._db = db
        self.queries: list[str] = []

    def execute(self, sql, *args):
        self.queries.append(sql)
        return self._db.execute(sql, *args)


def test_snapshot_reads_every_papers_row_in_one_query():
    db = _db()
    for i in range(6):
        _seed_paper(db, f"p{i}", f"Paper {i}", authors=[f"Author {i}"], year=2000 + i)
        _seed_entry(db, f"p{i}", research_objective="x")
    db.commit()

    counting = _CountingDb(db)
    snapshot_mod.build(counting, "u1", "proj1")

    document_queries = [q for q in counting.queries if "FROM documents" in q]
    entry_queries = [q for q in counting.queries if "FROM literature_entries" in q]
    # Six papers, still one query each — not one per paper.
    assert len(document_queries) == 1
    assert len(entry_queries) == 1


def test_conversation_checks_every_citation_in_one_query():
    db = _db()
    _seed_session(db, "s1")
    _seed_message(
        db,
        "m1",
        "s1",
        "assistant",
        "answer",
        sources=[
            {"chunk_id": f"c{i}", "title": f"T{i}", "page": 1,
             "document_id": f"d{i}", "apa_reference": ""}
            for i in range(6)
        ],
    )
    db.commit()

    counting = _CountingDb(db)
    conversation.build(counting, "u1", "s1")

    document_queries = [q for q in counting.queries if "FROM documents" in q]
    # Six cited sources, one batched lookup.
    assert len(document_queries) == 1
