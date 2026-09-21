"""Citation formatting shared across features.

One definition of how this app writes an in-text citation and an APA 7th-edition
reference, so the literature feature and any consumer of paper metadata (export,
chat) can never drift apart.
"""

import re
from typing import Optional


def auto_citation(paper: dict) -> str:
    """Derives a `Author, Year` citation from the paper's metadata."""
    authors = paper.get("authors") or []
    family = None
    if authors:
        first = authors[0]
        family = first.split(",", 1)[0].strip() if ", " in first else (first.split()[-1] or None)
    if not family and paper.get("author"):
        parts = [a for a in re.split(r"[;,]", paper["author"]) if a.strip()]
        if parts:
            family = parts[0].split()[-1]
    if not family:
        family = (paper.get("title") or "Untitled")[:30]
    year = paper.get("year")
    return f"{family}, {year}" if year else f"{family}, n.d."


def apa_reference(paper: dict) -> str:
    """Builds an APA 7th-edition reference string from a paper's metadata."""
    authors = paper.get("authors") or []
    year = paper.get("year") or "n.d."
    title = (paper.get("title") or "Untitled").strip()
    paper_type = (paper.get("paper_type") or "").strip()
    edition = (paper.get("edition") or "").strip()
    isbn = (paper.get("isbn") or "").strip()

    if authors:
        shown = "; ".join(authors[:7])
        if len(authors) > 7:
            shown += " …"
        ref = f"{shown} ({year}). {title}"
    else:
        ref = f"{title} ({year})"

    if paper_type == "textbook" and edition:
        ref += f" ({edition} ed.)."
    else:
        ref += "."

    journal = (paper.get("journal") or "").strip()
    if paper_type == "textbook":
        pass
    elif paper_type == "newspaper" and journal:
        pages = (paper.get("pages") or "").strip()
        ref += f" {journal}"
        if pages:
            ref += f", {pages}"
        ref += "."
    elif paper_type == "preprint":
        ref += " Preprint."
    elif paper_type == "thesis":
        publisher = (paper.get("publisher") or "").strip()
        if publisher:
            ref += f" {publisher}."
    elif journal:
        ref += f" {journal}"
        volume = (paper.get("volume") or "").strip()
        issue = (paper.get("issue") or "").strip()
        if volume:
            ref += f", {volume}" + (f"({issue})" if issue else "")
        elif issue:
            ref += f" ({issue})"
        pages = (paper.get("pages") or "").strip()
        if pages:
            ref += f", {pages}"
        ref += "."
    else:
        pages = (paper.get("pages") or "").strip()
        if pages:
            ref += f" {pages}."
        publisher = (paper.get("publisher") or "").strip()
        if publisher:
            ref += f" {publisher}."

    if paper_type == "textbook" and isbn:
        ref += f" ISBN {isbn}"
    else:
        doi = (paper.get("doi") or "").strip().rstrip(".,")
        url = (paper.get("url") or "").strip().rstrip(".,")
        if doi:
            ref += f" https://doi.org/{doi}"
        elif url:
            ref += f" {url}"
    return ref


def title_from_apa(apa: str) -> Optional[str]:
    """Extract the article title from an APA 7th-edition reference string.

    APA format: ``Author, A. A. (Year). Title of the article. Journal …``
    The title sits between the year-closing ``). `` and the next sentence
    boundary (``. `` followed by a capital letter or end of string).
    """
    if not apa:
        return None
    # Match the "(Year). " anchor — year may be "n.d."
    m = re.search(r"\)\.\s+", apa)
    if not m:
        return None
    rest = apa[m.end():]
    # Title runs until the next ". " followed by a capital letter (journal
    # name) or end of string.
    end = re.search(r"\.\s+[A-Z]", rest)
    title = rest[:end.start() + 1].strip() if end else rest.strip().rstrip(".")
    return title if len(title.split()) >= 3 else None
