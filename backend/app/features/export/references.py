"""Compiles and renders the project's references in APA 7th style.

The compilation is shared: the dossier's reference list and the standalone
references export both come from `compile()`, so the two can never disagree
about what a reference is or how it is ordered.
"""

from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.features.export import snapshot as snapshot_mod

HEADERS = [
    "Authors",
    "Year",
    "Title",
    "Journal",
    "DOI",
    "APA Reference",
    "Missing metadata",
    "Source",
]

WIDTHS = [30, 8, 42, 28, 26, 60, 22, 16]


@dataclass
class Reference:
    paper_id: str
    apa: str
    authors: str
    year: str
    title: str
    journal: str
    doi: str
    provenance: str
    missing_fields: list[str]
    complete: bool

    @property
    def gap(self) -> str:
        """What is missing from this reference, phrased for the reader.

        Single definition, so the dossier and the standalone references export
        cannot describe the same gap differently.
        """
        return ", ".join(self.missing_fields) or self.provenance


def compile(snapshot) -> list[Reference]:
    """Every paper's APA reference, de-duplicated and sorted alphabetically.

    Papers with no recorded author are included but flagged ``complete=False``
    — an exported bibliography should account for all of them, not quietly
    drop the ones the app could not enrich.
    """
    seen: dict[str, Reference] = {}
    for paper in snapshot.papers:
        apa = (paper.apa_reference or "").strip()
        if not apa or apa in seen:
            continue
        seen[apa] = Reference(
            paper_id=paper.id,
            apa=apa,
            authors="; ".join(paper.authors) if paper.authors else snapshot_mod.AUTHOR_UNKNOWN,
            year=str(paper.year) if paper.year else "",
            title=paper.title,
            journal=paper.journal or "",
            doi=paper.doi or "",
            provenance=paper.provenance,
            missing_fields=paper.missing_fields,
            complete=bool(paper.authors),
        )
    return [seen[apa] for apa in sorted(seen, key=str.lower)]


def render_docx(snapshot) -> bytes:
    from docx import Document
    from docx.shared import Pt

    refs = compile(snapshot)
    complete = [r for r in refs if r.complete]
    incomplete = [r for r in refs if not r.complete]

    document = Document()
    document.add_heading(snapshot.project_name, level=0)
    document.add_heading("References", level=1)

    if not refs:
        document.add_paragraph("This project has no references yet.")
    elif not complete:
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
            note.add_run(f"Incomplete: {ref.gap}").italic = True
            note.paragraph_format.left_indent = Pt(36)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render_xlsx(snapshot) -> bytes:
    refs = compile(snapshot)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "References"
    sheet.append(HEADERS)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4F46E5")
    for col, width in enumerate(WIDTHS, start=1):
        cell = sheet.cell(row=1, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.freeze_panes = "A2"

    for ref in refs:
        sheet.append(
            [
                ref.authors,
                ref.year,
                ref.title,
                ref.journal,
                ref.doi,
                ref.apa,
                ", ".join(ref.missing_fields) if ref.missing_fields else "",
                ref.provenance,
            ]
        )

    for row_index in range(2, sheet.max_row + 1):
        for col_index in range(1, len(HEADERS) + 1):
            sheet.cell(row=row_index, column=col_index).alignment = Alignment(
                wrap_text=True, vertical="top"
            )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
