"""Metadata lookup helpers for papers.

Two public sources are queried — Crossref and OpenAlex — plus lightweight
heuristic extraction (DOI, year, likely title) from a PDF's first page so that
queries start from real paper text rather than upload filenames.

Every network call is best-effort: failures return ``None`` / ``[]`` and never
raise. Records share a common shape::

    {
        "source": "crossref" | "openalex",
        "doi": str | None,
        "title": str,
        "authors": [str, ...],        # "Family, Given"
        "year": int | None,
        "abstract": str | None,
        "journal": str | None,        # container / publication title
        "volume": str | None,
        "issue": str | None,
        "pages": str | None,          # page range, e.g. "12-34"
        "publisher": str | None,
        "url": str | None,
    }
"""

import re
from typing import List, Optional

import requests

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
MAILTO = "notebook-os@localhost"
HTTP_TIMEOUT = 8.0
MAX_CANDIDATES = 6

_DOI_CORE_RE = re.compile(r"(10\.\d{4,9}/[^\s()[\]{}<>;,\"'\\]+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_ISSN_RE = re.compile(r"\bISSN\s*[:.]?\s*(\d{4}-?\d{3}[\dXx])\b")

_TITLE_BOILERPLATE = re.compile(
    r"journal|proceedings|issn|e-issn|p-issn|\bdoi\b|volume|\bvol\.\b|issue|\bno\.\b|"
    r"abstract|keywords?|copyright|©|\bwww\.|\bhttp|printed by|publisher|"
    r"all rights reserved|\bpage\b|editorial board|manuscript|received|accepted|"
    r"university|institute|department|correspondence|affiliation|school of",
    re.IGNORECASE,
)
_HEADER_END_RE = re.compile(r":\s*$")
_TITLE_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "with",
    "by", "at", "from", "its", "their", "is", "are", "as", "via",
}


def title_case(text: Optional[str]) -> Optional[str]:
    """Capitalises the first letter of every word (Title Case).

    Acronyms and tokens already in all caps of two or more characters (AI, LLM,
    MRI, COVID-19) are preserved verbatim instead of being lowercased."""
    if not text:
        return text
    words = []
    for word in str(text).split():
        if len(word) >= 2 and word.isupper():
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _plausible_doi(token: str) -> bool:
    token = token.rstrip(".").lower()
    return bool(_DOI_CORE_RE.fullmatch(token))


def extract_doi(text: Optional[str]) -> Optional[str]:
    """Finds a DOI-like token in arbitrary text (e.g. a PDF first page).

    Handles line-wrapped DOIs: PDF text extraction commonly breaks a long
    ``https://doi.org/10.1000/xyz1234`` across two lines. A break is trusted as
    a continuation only when the resumed fragment looks like DOI identifier
    characters (including a digit); otherwise the token simply ended at its line.
    """
    if not text:
        return None
    for m in _DOI_CORE_RE.finditer(text):
        if not _plausible_doi(m.group(1)):
            continue
        token = m.group(1).rstrip(".").lower()
        tail = text[m.end():]
        wrap = re.match(r"[\r\n]+\s*([a-zA-Z0-9._\-/]+)", tail)
        if wrap and re.search(r"\d", wrap.group(1)):
            joined = token + wrap.group(1)
            if _plausible_doi(joined):
                return joined
        return token
    match = re.search(r"doi\.org/\s*([^\s()]+)", text, re.IGNORECASE) or re.search(
        r"doi:\s*([^\s()]+)", text, re.IGNORECASE
    )
    if match:
        candidate = match.group(1).rstrip(".,;").lower()
        if _plausible_doi(candidate):
            return candidate
    return None


def extract_year(text: Optional[str]) -> Optional[int]:
    """First plausible publication year found in text."""
    if not text:
        return None
    for match in _YEAR_RE.finditer(text):
        year = int(match.group(0))
        if 1900 <= year <= 2030:
            return year
    return None


def extract_issn(text: Optional[str]) -> Optional[str]:
    """Finds an ISSN printed on the first page, e.g. ``ISSN 1234-5678``."""
    if not text:
        return None
    match = _ISSN_RE.search(text)
    if not match:
        return None
    return match.group(1).replace(" ", "").upper()


def heuristic_title(text: Optional[str]) -> Optional[str]:
    """Best guess at a paper title from first-page text.

    Scores lines that look like titles: Title Case, 3-18 significant words,
    and no journal/boilerplate tokens (the journal name, ISSN, DOI, headers
    and author/affiliation lines are rejected so they never win).
    """
    if not text:
        return None
    best, best_score = None, 0.0
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 250:
            continue
        words = line.split()
        significant = [
            w
            for w in words
            if w.lower().rstrip(".,;:") not in _TITLE_STOPWORDS and any(c.isalpha() for c in w)
        ]
        if not (3 <= len(significant) <= 18):
            continue
        if _HEADER_END_RE.search(line):
            continue
        if _TITLE_BOILERPLATE.search(line):
            continue
        if re.search(r"\d{4}", line) and not re.search(r"\b20\d\d\b", line):
            continue
        if ";" in line:
            continue
        capitalized = sum(1 for w in significant if w[0].isupper())
        score = 2.0 * capitalized / len(significant)
        if 4 <= len(significant) <= 12:
            score += 1.0
        elif len(significant) <= 16:
            score += 0.5
        score += min(len(significant), 8) * 0.1
        if score > best_score:
            best, best_score = line, score
    return best


def strip_xml(text: Optional[str]) -> str:
    """Removes JATS/XML tags from an abstract string."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()


# --- Crossref ---------------------------------------------------------------


def _crossref_year(message: dict) -> Optional[int]:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (message.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def _crossref_record(message: dict, source: str = "crossref") -> dict:
    raw_titles = message.get("title") or []
    title = raw_titles[0] if isinstance(raw_titles, list) and raw_titles else raw_titles
    title = str(title) if title else ""
    authors = []
    for author in message.get("author") or []:
        family = (author.get("family") or "").strip()
        given = (author.get("given") or "").strip()
        if family:
            authors.append(f"{family}, {given}" if given else family)
    return {
        "source": source,
        "doi": ((message.get("DOI") or "").lower() or None),
        "title": title,
        "authors": authors,
        "year": _crossref_year(message),
        "abstract": strip_xml(message.get("abstract")) or None,
        "journal": (message.get("container-title") or [None])[0] or None,
        "container_title": (message.get("container-title") or [None])[0] or None,
        "volume": (message.get("volume") or "").strip() or None,
        "issue": (message.get("issue") or "").strip() or None,
        "pages": (message.get("page") or "").strip() or None,
        "publisher": (message.get("publisher") or "").strip() or None,
        "url": (message.get("URL") or "").strip() or None,
    }


def crossref_by_doi(doi: str) -> Optional[dict]:
    """Exact lookup by DOI — the highest-confidence match available."""
    try:
        response = requests.get(
            f"{CROSSREF_WORKS_URL}/{doi}",
            params={"mailto": MAILTO},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
    except Exception:
        return None
    if not message:
        return None
    record = _crossref_record(message)
    record["confidence"] = 1.0
    return record


def crossref_by_title(title: str) -> List[dict]:
    try:
        response = requests.get(
            CROSSREF_WORKS_URL,
            params={"query.bibliographic": title, "rows": MAX_CANDIDATES, "mailto": MAILTO},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
    except Exception:
        return []
    return [_crossref_record(item) for item in items]


# --- OpenAlex ---------------------------------------------------------------


def _parse_openalex_author(name: str) -> str:
    name = (name or "").strip()
    if ", " in name:
        return name
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {' '.join(parts[:-1])}"
    return name


def _reconstruct_abstract(inverted_index: dict) -> Optional[str]:
    if not inverted_index:
        return None
    positions = {}
    for word, indices in inverted_index.items():
        for index in indices:
            positions[index] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def _openalex_record(work: dict) -> dict:
    authors = [
        _parse_openalex_author(a.get("author", {}).get("display_name", ""))
        for a in work.get("authorships") or []
        if a.get("author", {}).get("display_name")
    ]
    raw_title = work.get("title") or ""
    if isinstance(raw_title, list):
        raw_title = raw_title[0] if raw_title else ""
    raw_doi = work.get("doi") or ""
    if raw_doi:
        raw_doi = str(raw_doi).replace("https://doi.org/", "").lower()
    source = (work.get("primary_location") or {}).get("source", {}) or {}
    biblio = work.get("biblio") or {}
    first_page = (biblio.get("first_page") or "").strip()
    last_page = (biblio.get("last_page") or "").strip()
    if first_page and last_page:
        pages = f"{first_page}-{last_page}"
    elif first_page:
        pages = first_page
    else:
        pages = None
    return {
        "source": "openalex",
        "doi": raw_doi or None,
        "title": str(raw_title),
        "authors": authors,
        "year": work.get("publication_year"),
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "journal": source.get("display_name") or None,
        "container_title": source.get("display_name") or None,
        "volume": (biblio.get("volume") or "").strip() or None,
        "issue": (biblio.get("issue") or "").strip() or None,
        "pages": pages,
        "publisher": (source.get("host_organization_name") or "").strip() or None,
        "url": ((work.get("primary_location") or {}).get("landing_page_url") or "").strip() or None,
    }


def openalex_by_title(title: str) -> List[dict]:
    try:
        response = requests.get(
            OPENALEX_WORKS_URL,
            params={"search": title, "per-page": MAX_CANDIDATES, "mailto": MAILTO},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    except Exception:
        return []
    return [_openalex_record(item) for item in results]
