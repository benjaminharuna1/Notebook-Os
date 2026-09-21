"""Renders the project dossier (.docx) from an export snapshot.

Layout: a cover page that states what is missing, the APA reference list, the
per-paper reading notes, and (on request) the saved chat answers with the
citations they were written against.
"""

from io import BytesIO

from docx import Document
from docx.shared import Pt

from app.features.export import snapshot as snapshot_mod

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
    if snapshot.model_used:
        info.add_run(f" · model: {snapshot.model_used}")
    info.add_run(f" · {len(snapshot.papers)} paper(s)")
    if snapshot.sessions:
        info.add_run(f" · {len(snapshot.sessions)} saved conversation(s)")

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
    complete = sorted(
        {p.apa_reference for p in snapshot.papers if p.authors and p.apa_reference}
    )
    if not complete:
        document.add_paragraph("No paper in this project has a recorded author yet.")
        return
    for ref in complete:
        paragraph = document.add_paragraph(ref)
        try:
            paragraph.style = document.styles["List Number"]
        except KeyError:
            pass
        paragraph.paragraph_format.left_indent = Pt(36)
        paragraph.paragraph_format.first_line_indent = Pt(-36)
        paragraph.paragraph_format.space_after = Pt(6)

    incomplete = [p for p in snapshot.papers if not p.authors]
    if incomplete:
        document.add_heading("References with incomplete metadata", level=2)
        document.add_paragraph(
            "These papers have no author recorded, so the entries below are not "
            "complete APA references. Add the author in the app and export again."
        )
        for paper in sorted(incomplete, key=lambda p: p.title.lower()):
            paragraph = document.add_paragraph(paper.apa_reference)
            paragraph.paragraph_format.left_indent = Pt(36)
            paragraph.paragraph_format.space_after = Pt(6)
            note = document.add_paragraph()
            run = note.add_run(f"Incomplete: {', '.join(paper.missing_fields)}")
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


def _add_answers(document, snapshot) -> None:
    document.add_heading("Saved answers", level=1)
    if not snapshot.has_answers:
        document.add_paragraph("No saved conversations in this project yet.")
        return
    for session in snapshot.sessions:
        if not session.messages:
            continue
        document.add_heading(session.title, level=2)
        for message in session.messages:
            paragraph = document.add_paragraph()
            paragraph.add_run("Researcher: " if message.role == "user" else "Assistant: ").bold = True
            document.add_paragraph(message.content)
            if message.sources:
                for source in message.sources:
                    bullet = document.add_paragraph(source.label, style="List Bullet")
                    bullet.paragraph_format.space_after = Pt(2)


def render(snapshot, include_answers: bool = False) -> bytes:
    document = Document()
    _add_cover(document, snapshot)
    _add_references(document, snapshot)
    _add_paper_notes(document, snapshot)
    if include_answers:
        _add_answers(document, snapshot)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
