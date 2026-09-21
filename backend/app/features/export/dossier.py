"""Renders the project dossier (.docx) from an export snapshot.

Layout: a cover page that states what is missing, the APA reference list, and
the per-paper reading notes.
"""

from io import BytesIO

from docx import Document
from docx.shared import Pt

from app.features.export import references, snapshot as snapshot_mod

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


def _add_paper_notes(document, snapshot) -> None:
    document.add_heading("Paper notes", level=1)
    if not snapshot.papers:
        document.add_paragraph("This project has no papers yet.")
        return
    for paper in snapshot.papers:
        document.add_heading(paper.title or paper.filename, level=2)
        meta = document.add_paragraph()
        meta.add_run(f"{paper.citation} · source: {paper.provenance}").italic = True

        entry = paper.entry.values if paper.entry else {}
        for key, label in _ENTRY_LABELS:
            value = entry.get(key, snapshot_mod.NOT_GENERATED)
            paragraph = document.add_paragraph()
            paragraph.add_run(f"{label}: ").bold = True
            run = paragraph.add_run(value)
            if value in _PLACEHOLDERS:
                run.italic = True


def render(snapshot) -> bytes:
    document = Document()
    _add_cover(document, snapshot)
    _add_references(document, snapshot)
    _add_paper_notes(document, snapshot)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
