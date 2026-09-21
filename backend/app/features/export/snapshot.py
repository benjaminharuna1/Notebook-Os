"""Assembles the export snapshot — one normalized, read-only view of a project.

Both renderers (``workbook`` and ``dossier``) walk this same snapshot, which is
why every rule about how missing data is shown lives here and cannot drift
between the two artifacts.

The snapshot is built by reading SQLite directly rather than calling the
literature or chat services, so the export feature does not import from other
features.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.core import citations

# --- placeholders -----------------------------------------------------------
#
# A missing value must never be disguised as a plausible one. These strings are
# the vocabulary the researcher sees instead of a blank cell.

AUTHOR_UNKNOWN = "(author unknown)"
NOT_GENERATED = "not generated yet"
CLEARED_BY_YOU = "cleared by you"
EMPTY = "empty"
NOT_IN_PROJECT = "not in this project any more"
UNENRICHED = "never enriched"

ENTRY_FIELDS = (
    "research_objective",
    "methodology",
    "key_findings",
    "limitations",
    "relevance",
)

# Columns this snapshot wants from `documents`. Several are added by migrations
# that the literature feature runs on construction, so a project that never
# opened the literature page may be missing them entirely — see
# `_existing_columns`.
_PAPER_COLUMNS = (
    "id",
    "title",
    "filename",
    "author",
    "year",
    "doi",
    "abstract",
    "authors",
    "verification_status",
    "apa_reference",
    "metadata_user_edited",
    "paper_type",
    "edition",
    "issn",
    "isbn",
    "journal",
    "volume",
    "issue",
    "pages",
    "publisher",
    "url",
)


def _existing_columns(db, table: str) -> set[str]:
    try:
        rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return set()
    return {row["name"] for row in rows}


def _has_table(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _parse_authors(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(a) for a in parsed] if isinstance(parsed, list) else []


def _parse_json_list(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in parsed] if isinstance(parsed, list) else []


@dataclass
class SourceRef:
    """A citation as it stood when the answer was written."""

    citation: str
    title: str
    page: Optional[int]
    document_id: Optional[str]
    deleted: bool = False

    @property
    def label(self) -> str:
        """Never blank: falls back to the title, then to an explicit marker."""
        label = (self.citation or "").strip() or (self.title or "").strip()
        if not label:
            return AUTHOR_UNKNOWN
        return f"{label} {NOT_IN_PROJECT}" if self.deleted else label


@dataclass
class Message:
    role: str
    content: str
    created_at: Optional[str]
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class Session:
    id: str
    title: str
    model_used: Optional[str]
    created_at: Optional[str]
    messages: list[Message] = field(default_factory=list)


@dataclass
class Entry:
    values: dict[str, str] = field(default_factory=dict)


@dataclass
class Paper:
    id: str
    title: str
    filename: str
    authors: list[str]
    year: Optional[int]
    doi: Optional[str]
    journal: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    publisher: Optional[str]
    url: Optional[str]
    abstract: Optional[str]
    verification_status: Optional[str]
    metadata_user_edited: bool
    citation: str
    apa_reference: str
    provenance: str
    missing_fields: list[str]
    entry: Optional[Entry]


@dataclass
class Snapshot:
    project_name: str
    generated_at: str
    model_used: Optional[str]
    papers: list[Paper]
    sessions: list[Session]
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_answers(self) -> bool:
        return any(session.messages for session in self.sessions)


def _provenance(row: dict) -> str:
    if row.get("metadata_user_edited"):
        return "edited by you"
    status = (row.get("verification_status") or "").strip().lower()
    if status == "verified":
        return "verified"
    if status == "ai":
        return "ai-suggested"
    if status:
        return status
    return UNENRICHED


def _citation_label(paper: dict) -> str:
    """The in-text citation, or an honest marker when there is no author."""
    if not paper.get("authors"):
        return AUTHOR_UNKNOWN
    return citations.auto_citation(paper)


def _blank_state(entry_row: dict, user_edited: set[str], key: str) -> str:
    """Distinguishes the three ways a cell can end up empty."""
    if entry_row is None:
        return NOT_GENERATED
    if key in user_edited:
        return CLEARED_BY_YOU
    if entry_row.get("auto_generated"):
        return NOT_GENERATED
    return EMPTY


def _build_entry(db, user_id: str, project_id: str, paper_id: str) -> Optional[Entry]:
    if not _has_table(db, "literature_entries"):
        return None
    row = db.execute(
        "SELECT * FROM literature_entries WHERE paper_id = ? AND user_id = ? AND project_id = ?",
        (paper_id, user_id, project_id),
    ).fetchone()
    if row is None:
        return None
    entry_row = dict(row)
    user_edited = set(_parse_json_list(entry_row.get("user_edited")))
    values = {}
    for key in ENTRY_FIELDS:
        value = (entry_row.get(key) or "").strip()
        values[key] = value or _blank_state(entry_row, user_edited, key)
    return Entry(values=values)


def _build_paper(db, user_id: str, project_id: str, row: dict) -> Paper:
    authors = _parse_authors(row.get("authors"))
    if not authors and row.get("author"):
        authors = [a.strip() for a in str(row["author"]).replace(";", ",").split(",") if a.strip()]

    apa = (row.get("apa_reference") or "").strip()
    if not apa:
        apa = citations.apa_reference({**row, "authors": authors})

    missing = []
    if not authors:
        missing.append("authors")
    if not row.get("year"):
        missing.append("year")
    if not row.get("doi"):
        missing.append("doi")
    if not row.get("journal"):
        missing.append("journal")

    return Paper(
        id=row["id"],
        title=(row.get("title") or "").strip(),
        filename=(row.get("filename") or "").strip(),
        authors=authors,
        year=row.get("year"),
        doi=row.get("doi"),
        journal=row.get("journal"),
        volume=row.get("volume"),
        issue=row.get("issue"),
        pages=row.get("pages"),
        publisher=row.get("publisher"),
        url=row.get("url"),
        abstract=row.get("abstract"),
        verification_status=row.get("verification_status"),
        metadata_user_edited=bool(row.get("metadata_user_edited")),
        citation=_citation_label({**row, "authors": authors}),
        apa_reference=apa,
        provenance=_provenance(row),
        missing_fields=missing,
        entry=_build_entry(db, user_id, project_id, row["id"]),
    )


def _build_sessions(db, user_id: str, project_id: str, live_doc_ids: set[str]) -> list[Session]:
    rows = db.execute(
        """SELECT id, title, model_used, created_at FROM chat_sessions
           WHERE user_id = ? AND project_id = ?
           ORDER BY created_at, rowid""",
        (user_id, project_id),
    ).fetchall()

    sessions: list[Session] = []
    for row in rows:
        messages = []
        for msg in db.execute(
            """SELECT role, content, sources, created_at FROM chat_messages
               WHERE session_id = ? ORDER BY created_at, rowid""",
            (row["id"],),
        ).fetchall():
            sources = []
            for raw in _source_entries(msg["sources"]):
                doc_id = raw.get("document_id")
                # A source whose document is gone keeps the citation captured at
                # answer time, marked rather than silently dropped.
                deleted = bool(doc_id) and doc_id not in live_doc_ids
                sources.append(
                    SourceRef(
                        citation=str(raw.get("citation") or ""),
                        title=str(raw.get("title") or ""),
                        page=raw.get("page"),
                        document_id=doc_id,
                        deleted=deleted,
                    )
                )
            messages.append(
                Message(
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                    sources=sources,
                )
            )
        sessions.append(
            Session(
                id=row["id"],
                title=(row["title"] or "").strip() or "Untitled session",
                model_used=row["model_used"],
                created_at=row["created_at"],
                messages=messages,
            )
        )
    return sessions


def _source_entries(raw: Any) -> list[dict]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def build(db, user_id: str, project_id: str) -> Snapshot:
    """Reads a project into an export snapshot. Never touches the network."""
    project = db.execute(
        "SELECT name FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    ).fetchone()
    project_name = ((project["name"] if project else "") or "Project").strip()

    available = _existing_columns(db, "documents")
    wanted = [column for column in _PAPER_COLUMNS if column in available]
    select = ", ".join(wanted) if wanted else "id, title, filename"
    rows = db.execute(
        f"""SELECT {select} FROM documents
            WHERE user_id = ? AND project_id = ? AND file_type = 'pdf'
            ORDER BY title COLLATE NOCASE""",
        (user_id, project_id),
    ).fetchall()

    papers = [_build_paper(db, user_id, project_id, dict(row)) for row in rows]
    live_doc_ids = {paper.id for paper in papers}
    sessions = _build_sessions(db, user_id, project_id, live_doc_ids)

    unresolved = []
    if not papers:
        unresolved.append("This project has no papers yet.")
    missing_apa = [p for p in papers if not p.authors]
    if missing_apa:
        unresolved.append(
            f"{len(missing_apa)} paper(s) have no author recorded, so no in-text citation can be built."
        )
    unenriched = [p for p in papers if p.provenance == UNENRICHED]
    if unenriched:
        unresolved.append(
            f"{len(unenriched)} paper(s) were never metadata-enriched."
        )
    deleted = sum(
        1
        for session in sessions
        for message in session.messages
        for source in message.sources
        if source.deleted
    )
    if deleted:
        unresolved.append(
            f"{deleted} citation(s) in saved answers point to documents no longer in this project."
        )

    model_used = next(
        (session.model_used for session in reversed(sessions) if session.model_used), None
    )

    return Snapshot(
        project_name=project_name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        model_used=model_used,
        papers=papers,
        sessions=sessions,
        unresolved=unresolved,
    )
