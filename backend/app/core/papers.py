"""Reading a `documents` row into paper metadata.

Lives in `core` so the literature feature and the export feature cannot drift
apart about how a paper's authors are derived. The two had separate copies of
this, which is exactly the kind of duplication that goes stale in one place.
"""

import json
import re


def authors_from_row(row: dict) -> list[str]:
    """The paper's author list from a `documents` row.

    ``documents.authors`` holds a JSON array and is the enriched source; the
    plain ``documents.author`` column is the raw upload-time fallback, split on
    commas or semicolons.
    """
    raw = row.get("authors")
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            # An empty array (`[]`) is common — it means the paper was never
            # enriched with authors, so fall through to the raw column rather
            # than reporting no authors.
            names = [str(a).strip() for a in parsed if str(a).strip()]
            if names:
                return names

    author = row.get("author")
    if not author:
        return []
    return [a.strip() for a in re.split(r"[;,]", str(author)) if a.strip()]
