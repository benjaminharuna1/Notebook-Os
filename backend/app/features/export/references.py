"""Compiles and renders the project's reference list.

`compile()` produces one `Reference` per paper — never fewer — so exporting a
project of N papers yields exactly N entries. Every renderer reads the same
`Reference`, so the RIS file, the Word list and the Excel sheet cannot disagree
about an entry, its order, or how a missing field is worded.

RIS (`render_ris`) is the format a reference manager imports directly; Word and
Excel are the human-readable forms.
"""

from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook

from app.features.export import sheets

REFERENCES_SHEET = "References"
SUMMARY_SHEET = "Summary"

HEADERS = [
    "Authors",
    "Year",
    "Title",
    "Source",
    "DOI",
    "APA Reference",
    "Missing metadata",
    "Provenance",
]

WIDTHS = [30, 8, 42, 28, 26, 60, 22, 16]

# A missing field gets an explicit placeholder rather than an empty cell, so a
# gap is always visible and never mistaken for data. One definition, read by
# every renderer.
UNKNOWN_AUTHOR = "Unknown author"
NO_DATE = "No date"
UNTITLED = "Untitled"
UNKNOWN_SOURCE = "Unknown source"
NO_DOI = "No DOI"

# RIS record type per paper type the app collects. Anything else is a journal
# article, which is the common case for the uploaded PDFs.
RIS_TYPE_BY_PAPER_TYPE = {
    "book": "BOOK",
    "textbook": "BOOK",
    "thesis": "THES",
    "newspaper": "NEWS",
    "preprint": "GEN",
}


@dataclass
class Reference:
    paper_id: str
    apa: str
    author_list: list[str]
    year: str
    title: str
    journal: str
    doi: str
    paper_type: str
    provenance: str
    missing_fields: list[str]
    complete: bool

    @property
    def fields(self) -> dict[str, str]:
        """The attribution, with each missing field visibly marked.

        Single definition, so RIS, Word and Excel cannot word the same gap
        differently — and no field is ever silently blank.
        """
        return {
            "authors": "; ".join(self.author_list) or UNKNOWN_AUTHOR,
            "year": self.year or NO_DATE,
            "title": self.title or UNTITLED,
            "source": self.journal or UNKNOWN_SOURCE,
            "doi": self.doi or NO_DOI,
        }

    @property
    def gap(self) -> str:
        """What is missing from this reference, phrased for the reader.

        Single definition, so the dossier and the standalone references export
        cannot describe the same gap differently.
        """
        return ", ".join(self.missing_fields) or self.provenance

    @property
    def ris_type(self) -> str:
        return RIS_TYPE_BY_PAPER_TYPE.get(self.paper_type.strip().lower(), "JOUR")


def compile(snapshot) -> list[Reference]:
    """One reference per paper, sorted alphabetically by APA string.

    Deliberately **not** de-duplicated: a project of N papers must export N
    entries so the count matches what the researcher sees, even when two papers
    describe the same work. Papers the app could not enrich are included too,
    with their gaps marked rather than dropped.
    """
    refs = [
        Reference(
            paper_id=paper.id,
            apa=(paper.apa_reference or "").strip(),
            author_list=list(paper.authors),
            year=str(paper.year) if paper.year else "",
            title=paper.title,
            journal=paper.journal or "",
            doi=paper.doi or "",
            paper_type=paper.paper_type or "",
            provenance=paper.provenance,
            missing_fields=paper.missing_fields,
            complete=bool(paper.authors),
        )
        for paper in snapshot.papers
    ]
    return sorted(refs, key=lambda ref: ref.apa.lower())


def table(refs: list[Reference]) -> list[list]:
    """The reference list as sheet rows.

    Single definition, used both by the references workbook and by the dossier's
    References sheet, so the two can never lay out the same reference differently.
    """
    return [
        [
            ref.fields["authors"],
            ref.fields["year"],
            ref.fields["title"],
            ref.fields["source"],
            ref.fields["doi"],
            ref.apa,
            ", ".join(ref.missing_fields),
            ref.provenance,
        ]
        for ref in refs
    ]


def _summary_rows(snapshot, entries: int) -> list[list]:
    """What the file contains, stated in the file itself."""
    return [
        ["Project", snapshot.project_name],
        ["Generated", snapshot.generated_at],
        ["Entries", entries],
    ]


def render_docx(snapshot) -> bytes:
    from docx import Document
    from docx.shared import Pt

    refs = compile(snapshot)
    complete = [r for r in refs if r.complete]
    incomplete = [r for r in refs if not r.complete]

    document = Document()
    document.add_heading(snapshot.project_name, level=0)
    info = document.add_paragraph()
    info.add_run(f"Generated {snapshot.generated_at} · {len(refs)} entries").italic = True
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
    # The data sheet stays the active/first sheet so it opens on the entries;
    # the summary is appended.
    sheet = workbook.active
    sheet.title = REFERENCES_SHEET
    sheets.write_sheet(sheet, HEADERS, WIDTHS, table(refs))

    summary = workbook.create_sheet(SUMMARY_SHEET)
    sheets.write_sheet(summary, ["Item", "Value"], [22, 60], _summary_rows(snapshot, len(refs)))

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_ris(snapshot) -> bytes:
    """The reference list as RIS, for import into a reference manager.

    Every record carries the same fields in the same order, and each missing
    attribution value is written as an explicit placeholder rather than omitted,
    so entries stay uniform and a gap stays visible. ``DO`` is the one exception:
    a reference manager would store ``No DOI`` as a literal DOI, so the line is
    left out when there is no DOI.

    The leading ``#`` lines are a widely-supported convention for stating what
    the file contains; RIS has no comment syntax of its own.

    A zero-paper project never reaches here — the endpoint refuses it first.
    """
    refs = compile(snapshot)
    lines = [
        f"# Project: {snapshot.project_name}",
        f"# Generated: {snapshot.generated_at}",
        f"# Entries: {len(refs)}",
        "",
    ]

    for ref in refs:
        fields = ref.fields
        lines.append(f"TY  - {ref.ris_type}")
        if ref.author_list:
            lines.extend(f"AU  - {author}" for author in ref.author_list)
        else:
            lines.append(f"AU  - {fields['authors']}")
        lines.append(f"PY  - {fields['year']}")
        lines.append(f"TI  - {fields['title']}")
        lines.append(f"JO  - {fields['source']}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        lines.append("ER  -")
        lines.append("")

    return "\n".join(lines).encode("utf-8")
