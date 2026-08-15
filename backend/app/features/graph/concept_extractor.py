import re
from collections import Counter
from typing import List

# Common English stopwords — filtered out of single-word concepts.
_STOPWORDS = frozenset(
    """a about after all also am an and any are as at be because been before being
    between both but by can could did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in
    into is it its itself just me more most my myself no nor not of off on once only
    or other our ours ourselves out over own same she should so some such than that
    the their theirs them themselves then there these they this those through to too
    under until up very was we were what when where which while who whom why will
    with would you your yours yourself yourselves""".split()
)

_PHRASE_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z-]{2,}")


class ConceptExtractor:
    """Extracts candidate knowledge-graph concepts from document text.

    Two passes over the text:
      1. Capitalized phrases ("Project Management", "SQL Injection") are the
         primary entities.
      2. Frequent standalone words not in the stopword list backfill concepts
         when a document has few proper nouns.

    Concepts are ranked by frequency (ties broken by phrase priority).
    """

    def __init__(self, max_concepts: int = 10, min_length: int = 3):
        self.max_concepts = max_concepts
        self.min_length = min_length

    def extract(self, text: str) -> List[str]:
        if not text:
            return []

        phrase_counts = Counter()
        for match in _PHRASE_RE.finditer(text):
            phrase = match.group(0)
            if any(word.lower() in _STOPWORDS for word in phrase.split()):
                continue
            phrase_counts[phrase] += 1

        scored = [(count, 1, phrase) for phrase, count in phrase_counts.items()]

        # Only fall back to frequent standalone words when the text has no
        # proper-noun phrases; backfilled single words are too noisy next to
        # capitalized concepts.
        if not scored:
            word_counts = Counter()
            total_words = 0
            for word in _WORD_RE.findall(text):
                total_words += 1
                if len(word) < self.min_length or word.lower() in _STOPWORDS:
                    continue
                word_counts[word.lower()] += 1
            for word, count in word_counts.items():
                if count >= 2 or (total_words and count / total_words > 0.1):
                    scored.append((count, 0, word))

        scored.sort(key=lambda item: (-item[0], -item[1]))
        return [concept for _, _, concept in scored[: self.max_concepts]]
