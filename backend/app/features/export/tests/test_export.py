import asyncio
import json
import sqlite3
from io import BytesIO

from docx import Document
from fastapi import HTTPException
from openpyxl import load_workbook

from app.features.export import dossier, references, router, snapshot as snapshot_mod

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
    assert "Provenance" in headers
    assert "Missing metadata" in headers
    assert headers.index("DOI") >= 0

    rows = {row[0]: row for row in sheet.iter_rows(min_row=2, values_only=True)}
    sourced = rows["Sourced Paper"]
    assert sourced[headers.index("Provenance")] == "verified"
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


def test_dossier_references_are_sorted_and_hanging_indented():
    db = _db()
    _seed_paper(db, "p1", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p3", "Alpha Study", authors=["Alpha, A."], year=2021)
    db.commit()

    snap = snapshot_mod.build(db, "u1", "proj1")
    data = dossier.render_docx(snap)

    # One entry per paper — two identical works are still two papers.
    assert _section(data, "References") == [
        "Alpha, A. (2021). Alpha Study.",
        "Alpha, A. (2021). Alpha Study.",
        "Zeta, Z. (2020). Zeta Study.",
    ]

    document = Document(BytesIO(data))
    numbered = [p for p in document.paragraphs if p.text.startswith("Alpha, A.")]
    assert numbered[0].paragraph_format.first_line_indent.pt == -36


# --- references -------------------------------------------------------------


def test_references_compile_is_one_per_paper_and_sorted():
    db = _db()
    _seed_paper(db, "p1", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p2", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p3", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p4", "Unattributed Report", authors=None, year=None)
    db.commit()

    refs = references.compile(snapshot_mod.build(db, "u1", "proj1"))

    # Four papers, four entries — the two identical works are not collapsed.
    assert [r.apa for r in refs] == [
        "Alpha, A. (2021). Alpha Study.",
        "Alpha, A. (2021). Alpha Study.",
        "Unattributed Report (n.d.).",
        "Zeta, Z. (2020). Zeta Study.",
    ]
    by_title = {r.title: r for r in refs}
    assert by_title["Alpha Study"].complete is True
    assert by_title["Unattributed Report"].complete is False
    assert by_title["Unattributed Report"].fields["authors"] == references.UNKNOWN_AUTHOR
    assert by_title["Unattributed Report"].fields["year"] == references.NO_DATE
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
    assert complete[headers.index("Source")] == "Journal of Things"
    assert complete[headers.index("Provenance")] == "verified"
    assert complete[headers.index("Missing metadata")] in (None, "")

    incomplete = rows["Incomplete Paper"]
    assert incomplete[headers.index("Authors")] == references.UNKNOWN_AUTHOR
    assert "authors" in incomplete[headers.index("Missing metadata")]


def _ris_records(text: str) -> list[list[str]]:
    """The RIS records, with the leading `#` header lines ignored."""
    records: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        current.append(line)
        if line.startswith("ER  -"):
            records.append(current)
            current = []
    return records


def _ris_tags(record: list[str]) -> list[str]:
    # Splits "TY  - JOUR" and the terminator "ER  -" alike.
    return [line.split("  -", 1)[0] for line in record]


def test_ris_lists_one_record_per_paper_in_a_consistent_field_order():
    db = _db()
    _seed_paper(db, "p1", "Alpha Study", authors=["Alpha, A.", "Beta, B."], year=2021,
                journal="Journal of Things", doi="10.1000/abc", verification_status="verified")
    _seed_paper(db, "p2", "Zeta Study", authors=["Zeta, Z."], year=2020)
    _seed_paper(db, "p3", "Zeta Study", authors=["Zeta, Z."], year=2020)
    db.commit()

    records = _ris_records(
        references.render_ris(snapshot_mod.build(db, "u1", "proj1")).decode("utf-8")
    )

    # Three papers, three records — the duplicate pair is not collapsed.
    assert len(records) == 3
    # Same field order in every entry; the optional DOI line is the only difference.
    assert _ris_tags(records[0]) == ["TY", "AU", "AU", "PY", "TI", "JO", "DO", "ER"]
    assert _ris_tags(records[1]) == ["TY", "AU", "PY", "TI", "JO", "ER"]
    assert _ris_tags(records[2]) == ["TY", "AU", "PY", "TI", "JO", "ER"]
    assert records[0] == [
        "TY  - JOUR",
        "AU  - Alpha, A.",
        "AU  - Beta, B.",
        "PY  - 2021",
        "TI  - Alpha Study",
        "JO  - Journal of Things",
        "DO  - 10.1000/abc",
        "ER  -",
    ]


def test_ris_marks_every_missing_field_with_a_placeholder():
    db = _db()
    _seed_paper(db, "p1", "Only Paper", authors=None, year=None)
    db.commit()

    text = references.render_ris(snapshot_mod.build(db, "u1", "proj1")).decode("utf-8")

    assert "AU  - Unknown author" in text
    assert "PY  - No date" in text
    assert "TI  - Only Paper" in text
    assert "JO  - Unknown source" in text
    # A missing DOI is omitted rather than written out, because a reference
    # manager would store the placeholder as a literal DOI.
    assert "DO  - " not in text


def test_reference_sheet_cells_are_never_blank():
    db = _db()
    _seed_paper(db, "p1", "Only Paper", authors=None, year=None)
    db.commit()

    data = references.render_xlsx(snapshot_mod.build(db, "u1", "proj1"))
    sheet = load_workbook(BytesIO(data))[references.REFERENCES_SHEET]
    headers = [c.value for c in sheet[1]]
    row = dict(zip(headers, next(sheet.iter_rows(min_row=2, values_only=True))))

    for column in ("Authors", "Year", "Title", "Source", "DOI"):
        assert row[column], f"{column} was blank"
    assert row["Authors"] == references.UNKNOWN_AUTHOR
    assert row["Year"] == references.NO_DATE
    assert row["Source"] == references.UNKNOWN_SOURCE
    assert row["DOI"] == references.NO_DOI


def test_every_reference_file_states_project_date_and_entry_count():
    db = _db()
    _seed_paper(db, "p1", "Alpha Study", authors=["Alpha, A."], year=2021)
    _seed_paper(db, "p2", "Beta Study", authors=["Beta, B."], year=2022)
    db.commit()
    snap = snapshot_mod.build(db, "u1", "proj1")

    ris = references.render_ris(snap).decode("utf-8")
    assert "# Project: My Thesis" in ris
    assert f"# Generated: {snap.generated_at}" in ris
    assert "# Entries: 2" in ris

    words = "\n".join(_paragraphs(references.render_docx(snap)))
    assert "My Thesis" in words
    assert f"Generated {snap.generated_at} · 2 entries" in words

    workbook = load_workbook(BytesIO(references.render_xlsx(snap)))
    summary = {
        row[0]: row[1]
        for row in workbook[references.SUMMARY_SHEET].iter_rows(min_row=2, values_only=True)
    }
    assert summary == {"Project": "My Thesis", "Generated": snap.generated_at, "Entries": 2}
    # The entries stay on their own sheet, so the data is still a clean table.
    assert workbook.sheetnames == [references.REFERENCES_SHEET, references.SUMMARY_SHEET]


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
    assert "Provenance" in headers


def test_router_refuses_project_without_papers():
    db = _db()
    db.commit()

    for export_format in ("ris", "docx", "xlsx"):
        try:
            _call(router.export_references("proj1", export_format, {"id": "u1"}, db))
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "no papers" in exc.detail
        else:
            raise AssertionError(f"expected a 400 for format={export_format}, got a file")


def test_router_serves_references_as_ris():
    db = _db()
    _seed_paper(db, "p1", "Alpha Study", authors=["Alpha, A."], year=2021)
    db.commit()

    response = _call(router.export_references("proj1", "ris", {"id": "u1"}, db))

    assert response.media_type == "application/x-research-info-systems"
    assert response.headers["content-disposition"] == (
        'attachment; filename="my-thesis-references.ris"'
    )
    text = response.body.decode("utf-8")
    assert text.count("TY  - ") == 1
    assert text.count("ER  -") == 1
