"""Renders the project dossier from an export snapshot.

Both formats carry the same three sections, in the same order:

    1. Summary          — what the export could not resolve
    2. References       — the compiled APA bibliography
    3. Paper notes      — one section per paper / one row per paper

Word renders the notes as narrative sections; Excel renders them as a sheet of
rows. Same content, two shapes.
"""

from io import BytesIO

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook

from app.features.export import references, sheets, snapshot as snapshot_mod

_PLACEHOLDERS = {
    snapshot_mod.NOT_GENERATED,
    snapshot_mod.CLEARED_BY_YOU,
    snapshot_mod.EMPTY,
}

_ENTRY_LABELS = (
    ("research_objective", "Research objective / questions"),
    ("methodology", "Methodology & sample"),
    ("key_findings", "Key findings"),
    ("limitations", "Limitations & gaps"),
    ("relevance", "Relevance / contribution"),
)

# Sheet order mirrors the document's section order.
SUMMARY_SHEET = "Summary"
REFERENCES_SHEET = "References"
NOTES_SHEET = "Paper notes"

_MATRIX_HEADERS = [
    "Paper Title",
    "Citation (Author, Year)",
    "Research Objective / Questions",
    "Methodology & Sample",
    "Key Findings",
    "Limitations & Gaps",
    "Relevance / Contribution",
    "APA Reference",
    "Authors",
    "Year",
    "DOI",
    "Journal",
    "Missing metadata",
    "Provenance",
]

_MATRIX_WIDTHS = [42, 22, 46, 42, 46, 42, 42, 52, 28, 8, 24, 26, 24, 16]


# --- section 1: summary -----------------------------------------------------


def _add_cover(document, snapshot) -> None:
    document.add_heading(snapshot.project_name, level=0)
    info = document.add_paragraph()
    info.add_run(f"Exported {snapshot.generated_at}").italic = True
    info.add_run(f" · {len(snapshot.papers)} paper(s)")

    document.add_heading("Before you rely on this", level=1)
    if snapshot.unresolved:
        document.add_paragraph(
            "The app could not resolve the following. They appear in the sections "
            "below rather than being filled in with a guess:"
        )
        for item in snapshot.unresolved:
            document.add_paragraph(item, style="List Bullet")
    else:
        document.add_paragraph("Nothing was missing when this export ran.")


def _summary_rows(snapshot) -> list[list]:
    rows = [
        ["Project", snapshot.project_name],
        ["Exported", snapshot.generated_at],
        ["Papers", len(snapshot.papers)],
    ]
    if snapshot.unresolved:
        rows += [["Unresolved", item] for item in snapshot.unresolved]
    else:
        rows.append(["Unresolved", "Nothing was missing when this export ran."])
    return rows


# --- section 2: references --------------------------------------------------


def _add_references(document, snapshot) -> None:
    document.add_heading("References", level=1)
    refs = references.compile(snapshot)
    complete = [r for r in refs if r.complete]
    incomplete = [r for r in refs if not r.complete]

    if not refs:
        document.add_paragraph("This project has no references yet.")
        return
    if not complete:
        document.add_paragraph("No paper in this project has a recorded author yet.")

    for ref in complete:
        paragraph = document.add_paragraph(ref.apa)
        try:
            paragraph.style = document.styles["List Number"]
        except KeyError:
            pass
        paragraph.paragraph_format.left_indent = Pt(36)
        paragraph.paragraph_format.first_line_indent = Pt(-36)
        paragraph.paragraph_format.space_after = Pt(6)

    if incomplete:
        document.add_heading("References with incomplete metadata", level=2)
        document.add_paragraph(
            "These papers have no author recorded, so the entries below are not "
            "complete APA references. Add the author in the app and export again."
        )
        for ref in incomplete:
            paragraph = document.add_paragraph(ref.apa)
            paragraph.paragraph_format.left_indent = Pt(36)
            paragraph.paragraph_format.space_after = Pt(6)
            note = document.add_paragraph()
            run = note.add_run(f"Incomplete: {ref.gap}")
            run.italic = True
            note.paragraph_format.left_indent = Pt(36)


# --- section 3: paper notes -------------------------------------------------


def _add_paper_notes(document, snapshot) -> None:
    document.add_heading("Paper notes", level=1)
    if not snapshot.papers:
        document.add_paragraph("This project has no papers yet.")
        return
    for paper in snapshot.papers:
        document.add_heading(paper.title or paper.filename, level=2)
        meta = document.add_paragraph()
        meta.add_run(f"{paper.citation} · provenance: {paper.provenance}").italic = True

        entry = paper.entry.values if paper.entry else {}
        for key, label in _ENTRY_LABELS:
            value = entry.get(key, snapshot_mod.NOT_GENERATED)
            paragraph = document.add_paragraph()
            paragraph.add_run(f"{label}: ").bold = True
            run = paragraph.add_run(value)
            if value in _PLACEHOLDERS:
                run.italic = True


def _matrix_rows(snapshot) -> list[list]:
    rows = []
    for paper in snapshot.papers:
        entry = paper.entry.values if paper.entry else {}
        rows.append(
            [
                paper.title,
                paper.citation,
                entry.get("research_objective", snapshot_mod.NOT_GENERATED),
                entry.get("methodology", snapshot_mod.NOT_GENERATED),
                entry.get("key_findings", snapshot_mod.NOT_GENERATED),
                entry.get("limitations", snapshot_mod.NOT_GENERATED),
                entry.get("relevance", snapshot_mod.NOT_GENERATED),
                paper.apa_reference,
                "; ".join(paper.authors) if paper.authors else snapshot_mod.AUTHOR_UNKNOWN,
                # Year/DOI/Journal stay blank when absent so the columns remain
                # usable as data; "Missing metadata" and "Source" carry why.
                paper.year,
                paper.doi or "",
                paper.journal or "",
                ", ".join(paper.missing_fields),
                paper.provenance,
            ]
        )
    return rows


# --- entry points -----------------------------------------------------------


def render_docx(snapshot) -> bytes:
    document = Document()
    _add_cover(document, snapshot)
    _add_references(document, snapshot)
    _add_paper_notes(document, snapshot)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render_xlsx(snapshot) -> bytes:
    workbook = Workbook()

    summary = workbook.active
    summary.title = SUMMARY_SHEET
    sheets.write_sheet(summary, ["Item", "Value"], [22, 90], _summary_rows(snapshot))

    notes = workbook.create_sheet(NOTES_SHEET)
    sheets.write_sheet(notes, _MATRIX_HEADERS, _MATRIX_WIDTHS, _matrix_rows(snapshot))

    refs = workbook.create_sheet(REFERENCES_SHEET)
    sheets.write_sheet(
        refs, references.HEADERS, references.WIDTHS, references.table(references.compile(snapshot))
    )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
