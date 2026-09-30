"""Title casing for paper titles and references.

One definition of how a title is capitalised, shared by the literature feature
(stored metadata) and the export feature (references, dossiers), so the same
paper never reads differently in two places.

Standard Title Case:

* the first and last word always keep their capital, even if minor;
* minor words — ``of``, ``for``, ``in``, ``the``, ``and`` … — stay lowercase in
  between;
* acronyms (``LLM``, ``AI``), tokens containing digits (``COVID-19``) and words
  with deliberate internal capitals (``iPhone``) are left alone;
* a title written ENTIRELY in upper case is repaired rather than trusted,
  because shouting carries no case information to recover.
"""

import re
from typing import Optional

# Minor words stay lowercase unless they open or close the title.
_MINOR_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "onto", "or", "over", "per", "the", "to", "up", "via",
    "vs", "with",
}

# An all-caps title has lost its case information, so the acronyms worth keeping
# have to be named explicitly. Extend this list rather than loosening the rules.
_ACRONYMS = {
    "AI", "API", "CPU", "DNA", "GPU", "GPT", "GPS", "HTML", "HTTP", "IEEE",
    "ISBN", "ISSN", "LLM", "ML", "MRI", "NLP", "PCR", "PHD", "RAG", "RNA",
    "SQL", "UI", "URL", "USB", "UX", "XML",
}

# Splits a token into leading punctuation, the word, and trailing punctuation,
# so "of," and "(deep)" are still recognised as words.
_AFFIX_RE = re.compile(r"^([^\w]*)(.*?)([^\w]*)$")

# A word long enough to prove a title was written as prose rather than as a
# string of acronyms. Used only to decide whether a title is shouting.
_PROSE_WORD_LENGTH = 5


def _affixes(token: str) -> tuple[str, str, str]:
    match = _AFFIX_RE.match(token)
    return match.groups() if match else ("", token, "")


def _is_shouting(text: str) -> bool:
    """True when the whole title was written in caps.

    Requires more than one word and at least one word of five or more letters,
    so a genuine acronym phrase like ``AI IN ML`` is left alone instead of being
    mangled into ``Ai in Ml``.
    """
    if not text.isupper():
        return False
    words = text.split()
    if len(words) < 2:
        return False
    return any(
        core.isalpha() and len(core) >= _PROSE_WORD_LENGTH
        for _, core, _ in (_affixes(word) for word in words)
    )


def _preserve(token: str, shouting: bool) -> bool:
    """Whether this token's own casing should be kept as written."""
    _, core, _ = _affixes(token)
    if not core:
        return True
    if core.upper() in _ACRONYMS:
        return True
    if any(character.isdigit() for character in core):
        return True
    if shouting:
        # The title's casing is gone, so nothing here can be trusted as
        # deliberate — only the named acronyms and digit-bearing tokens above.
        return False
    if len(core) >= 2 and core.isupper():
        return True
    return any(character.isupper() for character in core[1:])


def _capitalise_word(token: str, *, is_first: bool, is_last: bool) -> str:
    prefix, core, suffix = _affixes(token)
    if not core:
        return token
    lowered = core.lower()
    if lowered in _MINOR_WORDS and not (is_first or is_last):
        return f"{prefix}{lowered}{suffix}"
    return f"{prefix}{core[:1].upper()}{core[1:].lower()}{suffix}"


def _capitalise(token: str, *, is_first: bool, is_last: bool, shouting: bool) -> str:
    if _preserve(token, shouting):
        return token
    parts = token.split("-")
    if len(parts) > 1:
        last = len(parts) - 1
        return "-".join(
            _capitalise_word(
                part,
                is_first=is_first and index == 0,
                is_last=is_last and index == last,
            )
            for index, part in enumerate(parts)
        )
    return _capitalise_word(token, is_first=is_first, is_last=is_last)


def title_case(text: Optional[str]) -> Optional[str]:
    """Title-cases a paper title, repairing an all-caps one.

    Returns short-circuiting falsy input unchanged (``None`` → ``None``,
    ``""`` → ``""``).
    """
    if not text:
        return text
    words = str(text).split()
    if not words:
        return text
    shouting = _is_shouting(str(text))
    last_index = len(words) - 1
    return " ".join(
        _capitalise(word, is_first=index == 0, is_last=index == last_index, shouting=shouting)
        for index, word in enumerate(words)
    )
