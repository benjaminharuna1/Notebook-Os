import asyncio
import json
import re
from typing import List, Optional, Tuple

from app.features.literature.metadata import title_case
from app.features.models.service import ModelService

ENTRY_KEYS = ("research_objective", "methodology", "key_findings", "limitations", "relevance")
MAX_PAPER_CHUNKS = 15
CHUNK_CHAR_CAP = 2500

_FALLBACK_MARK = "LLM unavailable — derived from abstract."
_METHOD_HINTS = (
    "used",
    "survey",
    "model",
    "data",
    "sample",
    "method",
    "approach",
    "analysis",
    "design",
    "interview",
)

METADATA_SYSTEM_PROMPT = (
    "You extract bibliographic metadata from the first page of a document. "
    "The page may show a journal name, author name(s), the document's own title, the "
    "publication year, a link/DOI, and often an ISSN, volume, issue, page range, "
    "publisher, abstract, edition number, or ISBN.\n\n"
    "Reply with STRICT JSON only, using exactly these keys:\n"
    '- "title" (string — the document title, NOT the journal/container name)\n'
    '- "authors" (array of strings in "Family, Given" format)\n'
    '- "year" (integer or null)\n'
    '- "doi" (string like "10.1000/xyz123" or null — ONLY if a DOI is clearly '
    'printed on the page; never invent or guess a DOI)\n'
    '- "journal" (string — journal or container name, or null)\n'
    '- "volume" (string or null)\n'
    '- "issue" (string or null)\n'
    '- "pages" (string like "12-34" or null)\n'
    '- "publisher" (string or null)\n'
    '- "issn" (string or null — the ISSN printed on the page)\n'
    '- "isbn" (string or null — an ISBN printed on the page, for books/textbooks)\n'
    '- "abstract" (string — the abstract text shown on the page, or null)\n'
    '- "paper_type" (string — exactly one of: "journal_article", "conference_paper", '
    '"textbook", "preprint", "thesis", "newspaper", "other")\n'
    '- "edition" (string or null — e.g. "3rd", "Second Edition", for textbooks/books)\n\n'
    "Paper type guidelines:\n"
    '- "journal_article": Published in a named journal, has ISSN, volume/issue\n'
    '- "conference_paper": Published in conference proceedings, has conference name\n'
    '- "textbook": Has edition number, ISBN, educational publisher\n'
    '- "preprint": arXiv, SSRN, bioRxiv, EdArXiv headers; no peer-review markers\n'
    '- "thesis": University/department header, "submitted in partial fulfillment"\n'
    '- "newspaper": Newspaper masthead, article-style layout\n'
    '- "other": Does not fit any of the above\n\n'
    "Critical rules:\n"
    '- If you cannot find a DOI printed on the page, set doi to null. Do NOT '
    "invent or guess DOIs.\n"
    '- "title" must be the document title, NOT the journal name.\n'
    '- If a field cannot be determined, use null or an empty array.'
)

MAX_METADATA_TEXT_CHARS = 4000

MAX_AI_PAPERS = 30
MAX_AI_REF_LINES = 40
AI_ABSTRACT_CAP = 300

_ENTRY_RETRY_SYSTEM = (
    "Your previous reply was not usable. Reply again with STRICT JSON only — a "
    'single JSON object with exactly these keys: "research_objective", '
    '"methodology", "key_findings", "limitations", "relevance". No markdown code '
    "fences, no prose before or after, no extra keys. Every value must be 2-4 "
    "sentences grounded in the paper above; if a field is not covered by the "
    'paper, write "Not stated in the paper."'
)


class LiteratureLLMService:
    """LLM layer over the literature map.

    * ``label_clusters`` names each community (2-5 word label + 2-3 sentence
      summary) from the member papers' titles. Fallbacks keep the map usable
      when no model is configured or the model is unreachable.
    * ``cluster_sources`` + ``cluster_prompt`` back the "what does this theme
      cover" popup, pulling that cluster's paper chunks as grounding.
    * ``summarize_papers`` / ``summarize_paper`` fill each paper's editable
      literature-review entry (research objective, methodology & sample, key
      findings, limitations & gaps, relevance/contribution).
    """

    MAX_SOURCES = 8
    CHUNKS_PER_PAPER = 2

    def __init__(self, db):
        self.db = db
        self.model_service = ModelService(db)

    # --- model plumbing ------------------------------------------------------

    def active_model(self, user_id: str) -> Optional[dict]:
        try:
            return self.model_service.get_active_model(user_id)
        except Exception:
            return None

    def _provider(self, user_id: str):
        model = self.active_model(user_id)
        if not model:
            raise ValueError("No active model configured — pick one in Settings")
        return self.model_service.get_provider(model, user_id)

    async def _call(self, user_id: str, system_prompt: str, user_prompt: str) -> str:
        provider = self._provider(user_id)
        parts = []
        async for chunk in provider.stream_chat(
            system_prompt, [{"role": "user", "content": user_prompt}]
        ):
            parts.append(chunk)
        return "".join(parts)

    # --- paper metadata extraction (second layer for enrichment) -------------

    def extract_paper_metadata(self, user_id: str, first_page: str, filename: str = "") -> dict:
        """Asks the configured LLM to pull title/authors/year/DOI/journal,
        volume/issue/pages/publisher/ISSN/abstract off a paper's first page.
        Best-effort: returns ``{}`` when no model is configured or the call
        fails, so enrichment always degrades gracefully.
        """
        first_page = (first_page or "").strip()
        if not first_page:
            return {}
        try:
            model = self.active_model(user_id)
            if not model:
                return {}
            prompt = (
                f"Filename: {filename or 'unknown'}\n\n"
                f"First page text:\n{first_page[:MAX_METADATA_TEXT_CHARS]}\n\n"
                "Return only the JSON object."
            )
            raw = asyncio.run(self._call(user_id, METADATA_SYSTEM_PROMPT, prompt))
            parsed = self._parse_json(raw)
            if not isinstance(parsed, dict):
                return {}
            if parsed.get("title"):
                parsed["title"] = title_case(parsed["title"])
            return parsed
        except Exception:
            return {}

    # --- cluster labeling ----------------------------------------------------

    def cluster_inputs(self, user_id: str, project_id: str) -> List[dict]:
        """Cluster id -> member titles/doc_ids from the latest literature checkpoint."""
        try:
            row = self.db.execute(
                """SELECT graph_json FROM graph_history
                   WHERE user_id = ? AND project_id = ? AND map_type = 'literature'
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (user_id, project_id),
            ).fetchone()
        except Exception:
            row = None
        if row is None:
            return []
        data = json.loads(row["graph_json"])
        if not isinstance(data, dict):
            return []
        by_cluster: dict = {}
        for node in data.get("nodes", []):
            cid = node.get("cluster")
            if cid:
                meta = node.get("meta") or {}
                by_cluster.setdefault(cid, []).append({
                    "label": node.get("label", ""),
                    "doc_id": meta.get("doc_id"),
                })
        return [
            {
                "id": cid,
                "titles": [m["label"] for m in members],
                "doc_ids": [m["doc_id"] for m in members if m.get("doc_id")],
            }
            for cid, members in by_cluster.items()
        ]

    async def label_clusters(
        self,
        user_id: str,
        project_id: str,
        clusters: List[dict],
    ) -> List[dict]:
        """Returns ``[{id, label, summary}]``; never raises."""
        if not clusters:
            return []
        system = (
            "You analyze a set of research paper titles that form one thematic cluster. "
            "Name the shared theme and summarize what ties the papers together. "
            'Reply with STRICT JSON only: {"label": "...", "summary": "..."}. '
            "Keep the label to 2-5 words and the summary to 2-3 sentences."
        )
        out = []
        for cluster in clusters:
            cid = cluster.get("id", "")
            titles = [t for t in cluster.get("titles", []) if t]
            fallback = {"id": cid, "label": f"Cluster {cid[1:]}", "summary": ""}
            if len(titles) < 2:
                out.append(fallback)
                continue
            prompt = (
                "Papers in this cluster:\n"
                + "\n".join(f"- {t}" for t in titles)
                + "\n\nName this cluster and summarize what these papers have in common."
            )
            try:
                raw = await self._call(user_id, system, prompt)
                parsed = self._parse_json(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("cluster reply was not an object")
                out.append(
                    {
                        "id": cid,
                        "label": (parsed.get("label") or fallback["label"]).strip()[:80],
                        "summary": (parsed.get("summary") or "").strip(),
                    }
                )
            except Exception:
                out.append(fallback)
        return out

    @staticmethod
    def _parse_json(raw: str) -> dict | list:
        """Best-effort JSON extraction tolerant of code fences and trailing prose.

        Tries the raw reply as-is, then extracts the first balanced ``{...}``
        or ``[...]`` block (string-aware), which survives models that wrap the
        object in prose or markdown fences. Returns a dict or list, or ``{}``.
        """
        cleaned = (raw or "").strip()
        if not cleaned:
            return {}
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        candidates = [cleaned]
        for open_char in ("{", "["):
            block = LiteratureLLMService._first_json_block(cleaned, open_char)
            if block:
                candidates.append(block)
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, (dict, list)):
                return parsed
        return {}

    @staticmethod
    def _first_json_block(text: str, open_char: str = "{") -> Optional[str]:
        """Returns the first balanced block in ``text``, or None.

        Tracks string literals so braces/brackets inside quoted values don't
        confuse the depth counter. Stops at the first fully balanced block, so
        prose after the JSON is ignored.
        """
        start = text.find(open_char)
        if start == -1:
            return None
        close_char = "}" if open_char == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    @staticmethod
    def _as_list(parsed) -> List[dict]:
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("pairs", "matches", "related", "result", "results", "edges"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _entry_fields(raw: str) -> dict:
        """Extracts the five entry fields from an LLM reply as a dict.

        Tolerant of non-object replies (arrays, prose) so a model that wraps
        the answer differently still degrades to an empty/retryable pass."""
        parsed = LiteratureLLMService._parse_json(raw)
        if not isinstance(parsed, dict):
            return {}
        return {key: (parsed.get(key) or "").strip() for key in ENTRY_KEYS}

    # --- paper literature-review entries ------------------------------------

    def _paper_chunks(self, paper_id: str, limit: int = MAX_PAPER_CHUNKS) -> List[Tuple[Optional[int], str]]:
        """Evenly sampled excerpts from the paper's full text.

        Selecting evenly spaced chunks — instead of just the first ``limit`` in
        page order — means the prompt covers every major section (Introduction,
        Methods, Results, Discussion/Conclusion), so fields that only appear
        deep in the body are still captured even when the abstract omits them."""
        rows = self.db.execute(
            """SELECT content, page_number FROM chunks
               WHERE document_id = ?
               ORDER BY page_number ASC, chunk_index ASC""",
            (paper_id,),
        ).fetchall()
        items: List[Tuple[Optional[int], str]] = []
        for row in rows:
            text = (row["content"] or "").strip()
            if not text:
                continue
            if len(text) > CHUNK_CHAR_CAP:
                text = text[:CHUNK_CHAR_CAP]
            items.append((row["page_number"], text))
        if not items:
            return []
        if len(items) <= limit:
            return items
        picks = sorted({round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)})
        return [items[idx] for idx in picks]

    def _paper_prompt(self, paper: dict, chunks: List[Tuple[Optional[int], str]]) -> Tuple[str, str]:
        header = [f"Title: {paper.get('title') or 'Untitled'}"]
        authors = paper.get("authors") or []
        if authors:
            header.append("Authors: " + "; ".join(authors))
        if paper.get("year"):
            header.append(f"Year: {paper['year']}")
        if paper.get("abstract"):
            header.append(f"Abstract: {paper['abstract']}")
        excerpts = [
            f"[Excerpt {i} — page {page or 'n/a'}]\n{text}"
            for i, (page, text) in enumerate(chunks, 1)
        ]
        if not excerpts:
            excerpts = ["[No full text available — rely on the title and abstract.]"]
        system = (
            "You are a research analyst performing a deep reading of a paper to "
            "populate a literature review matrix. The paper's full text is provided "
            "as numbered excerpts spanning the Introduction, Methods, Results, and "
            "Discussion/Conclusion sections.\n\n"
            "Your task: produce five concise fields as STRICT JSON — a single JSON "
            "object with exactly these five keys and nothing else:\n"
            '{"research_objective": "...", "methodology": "...", '
            '"key_findings": "...", "limitations": "...", "relevance": "..."}\n\n'
            "Field definitions and WHERE to find each:\n"
            "- research_objective: Look in the Introduction section for the research "
            "question, hypothesis, or stated purpose. Often in the first 1-2 paragraphs "
            "of the body text. State it precisely — do not guess from the title alone.\n"
            "- methodology: Look in the Methods/Methodology section for: research design "
            "(experimental, survey, case study, etc.), data sources, sample size and "
            "demographics, analytical techniques (regression, thematic analysis, etc.), "
            "and any instruments or frameworks used. Include specific details like sample "
            "size (e.g. 'n=342 university students') when available.\n"
            "- key_findings: Look in the Results and Discussion sections for the main "
            "empirical or theoretical conclusions. Include specific numbers, effect sizes, "
            "or statistical significance when stated. Do not just paraphrase the abstract.\n"
            "- limitations: Look in the Discussion or Limitations section for acknowledged "
            "weaknesses — small samples, selection bias, scope limits, unaddressed "
            "confounders, generalizability concerns.\n"
            "- relevance: Based on all of the above, explain how this study could inform "
            "a literature review — what methodology it supports or challenges, what context "
            "it provides, or what gap it fills.\n\n"
            "Rules:\n"
            "- Every value must be 2-4 sentences, grounded in the EXCERPTS below. Do not "
            "invent facts not present in the text.\n"
            "- Do NOT rely on the abstract alone. The abstract often omits methodology "
            "details, effect sizes, sample specifics, and limitations. Search the full "
            "body text for each field.\n"
            "- If the paper genuinely does not address a field, write 'Not stated in the "
            "paper.' — do not guess.\n"
            "- Include parenthetical citations (Author, Year) when referencing specific "
            "claims or findings from the paper. Use the author names and year from the "
            "paper's metadata.\n"
            "- No markdown code fences, no commentary before or after the JSON, no extra keys."
        )
        user_prompt = (
            "\n\n".join(header)
            + "\n\n"
            + "\n\n".join(excerpts)
            + "\n\nRead the full excerpts carefully. Extract each field from the "
            "most relevant section of the body text, not just the abstract.\n"
            "Return only the JSON object now."
        )
        return system, user_prompt

    async def _generate_entry(
        self,
        service,
        user_id: str,
        project_id: str,
        paper: dict,
        overwrite: bool,
    ) -> None:
        """Runs one LLM entry pass. In auto mode failures fall back to a
        metadata-derived entry (so the review table is never empty) and never
        abort the build; in overwrite mode (explicit regenerate) failures
        raise so the UI can surface the reason."""
        try:
            model = self.active_model(user_id)
            if not model:
                raise ValueError("No active model configured — pick one in Settings")
            system, user_prompt = self._paper_prompt(paper, self._paper_chunks(paper["id"]))
            raw = await self._call(user_id, system, user_prompt)
            fields = self._entry_fields(raw)
            if not any(fields.values()):
                raw = await self._call(user_id, _ENTRY_RETRY_SYSTEM, user_prompt)
                fields = self._entry_fields(raw)
            if not any(fields.values()):
                raise ValueError("LLM returned no usable literature fields")
        except Exception:
            if overwrite:
                raise
            service.upsert_entry(
                paper["id"],
                user_id,
                project_id,
                self._fallback_entry(paper),
                auto=True,
                auto_generated=True,
            )
            return
        if overwrite:
            merged = {key: (fields.get(key) or None) for key in ENTRY_KEYS}
            merged["citation"] = service.auto_citation(paper)
            merged["apa_reference"] = paper.get("apa_reference") or service.apa_reference(paper)
            service.upsert_entry(
                paper["id"], user_id, project_id, merged, auto=False, auto_generated=True
            )
        else:
            existing = service.get_entry(paper["id"], user_id)
            overwrite_fields = (
                set(ENTRY_KEYS) if existing and self._is_fallback_entry(existing) else set()
            )
            service.upsert_entry(
                paper["id"],
                user_id,
                project_id,
                fields,
                auto=True,
                auto_generated=True,
                overwrite=overwrite_fields,
            )

    @staticmethod
    def _fallback_entry(paper: dict) -> dict:
        """Fills the five review fields from the paper's own title/abstract when
        no LLM is available. Content is always grounded in the paper's text and
        carries a marker so a later LLM pass replaces it."""
        title = (paper.get("title") or "Untitled").strip()
        abstract = (paper.get("abstract") or "").strip()
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|[\r\n]+", abstract)
            if s.strip()
        ]
        objective = sentences[0] if sentences else f"This paper examines {title}."
        methodology = next(
            (s for s in sentences if any(hint in s.lower() for hint in _METHOD_HINTS)),
            "Not stated in the abstract.",
        )
        findings = " ".join(sentences[1:]) or (abstract or "No findings available from the abstract.")
        return {
            "research_objective": objective[:2000],
            "methodology": methodology[:2000],
            "key_findings": findings[:2000],
            "limitations": f"{_FALLBACK_MARK} Full-text analysis requires the LLM.",
            "relevance": "Contributes to the project literature review.",
        }

    @staticmethod
    def _is_fallback_entry(entry: dict) -> bool:
        return any(_FALLBACK_MARK in (entry.get(key) or "") for key in ENTRY_KEYS)

    def _summarize_paper_sync(self, service, user_id: str, project_id: str, paper: dict, overwrite: bool) -> None:
        asyncio.run(self._generate_entry(service, user_id, project_id, paper, overwrite))

    def summarize_papers(
        self,
        user_id: str,
        project_id: str,
        on_paper=None,
    ) -> int:
        """Fills empty entry fields for every paper in the project.

        Runs inside the build job (sync context). Never raises; papers whose
        fields are already filled (including user edits) are skipped. Returns
        the number of papers considered.
        """
        from app.features.literature.service import LiteratureService

        service = LiteratureService(self.db)
        papers = service.papers(user_id, project_id)
        total = len(papers)
        for index, paper in enumerate(papers, 1):
            try:
                entry = service.get_entry(paper["id"], user_id)
                filled = bool(entry) and any(
                    (entry.get(key) or "").strip() for key in ENTRY_KEYS
                )
                is_fallback = bool(entry) and self._is_fallback_entry(entry)
                if not filled or is_fallback:
                    self._summarize_paper_sync(service, user_id, project_id, paper, overwrite=False)
            except Exception:
                pass
            if on_paper:
                on_paper(index, total)
        return total

    async def summarize_paper(
        self,
        user_id: str,
        project_id: str,
        paper_id: str,
    ) -> dict:
        """Regenerates one paper's entry on demand (async, used by the router).

        Overwrites the five content fields with fresh LLM output; raises when no
        model is configured or the call fails so the UI can surface the reason.
        """
        from app.features.literature.service import LiteratureService

        service = LiteratureService(self.db)
        paper = next(
            (p for p in service.papers(user_id, project_id) if p["id"] == paper_id),
            None,
        )
        if paper is None:
            raise ValueError("Paper not found in this project")
        await self._generate_entry(service, user_id, project_id, paper, overwrite=True)
        return service.get_entry(paper_id, user_id)

    # --- cluster summary -----------------------------------------------------

    def cluster_sources(self, user_id: str, project_id: str, cluster_id: str) -> List[dict]:
        inputs = self.cluster_inputs(user_id, project_id)
        cluster = next((c for c in inputs if c["id"] == cluster_id), None)
        if not cluster:
            return []
        doc_ids = set(cluster.get("doc_ids") or [])
        rows = self.db.execute(
            """SELECT c.document_id, c.content, c.page_number, d.title AS title
               FROM chunks c
               JOIN documents d ON d.id = c.document_id
               WHERE d.user_id = ? AND d.project_id = ? AND c.content != ''""",
            (user_id, project_id),
        ).fetchall()
        per_doc: dict = {}
        for row in rows:
            if doc_ids:
                if row["document_id"] not in doc_ids:
                    continue
            else:
                title_set = {t.lower() for t in cluster.get("titles", [])}
                if (row["title"] or "").lower() not in title_set:
                    continue
            per_doc.setdefault(row["document_id"], []).append(row)
        selected = []
        for doc_rows in per_doc.values():
            doc_rows.sort(key=lambda r: r["page_number"] or 0)
            selected.extend(doc_rows[: self.CHUNKS_PER_PAPER])
        selected.sort(key=lambda r: (r["title"] or "", r["page_number"] or 0))
        return [
            {
                "document_id": row["document_id"],
                "title": row["title"],
                "page": row["page_number"],
                "content": row["content"],
            }
            for row in selected[: self.MAX_SOURCES]
        ]

    def cluster_prompt(self, cluster_label: str, sources: List[dict]) -> Tuple[str, str]:
        context = []
        for source in sources:
            page = f", Page {source['page']}" if source.get("page") else ""
            context.append(f"[Source: {source['title']}{page}]\n{source['content']}")
        system = (
            "You are a research summarizer. Summarize what a cluster of research "
            "papers says about its shared theme. Use APA 7th edition citations: "
            "include parenthetical citations (Author, Year) for every factual claim."
        )
        user_prompt = (
            f'Theme: "{cluster_label}"\n\n'
            "Passages:\n"
            + "\n\n".join(context)
            + f'\n\nWrite a concise summary (3-5 sentences) of the theme "{cluster_label}": '
            "what these papers contribute, their shared methods or findings, and any "
            "gaps or contradictions. Cite sources using parenthetical references "
            "(Author, Year) where appropriate. Base it strictly on the passages."
        )
        return system, user_prompt

    # --- per-paper summary (for graph popup) ---------------------------------

    def paper_summary_sources(self, user_id: str, project_id: str, paper_id: str) -> List[dict]:
        """Gathers text chunks for a specific paper to use in summary generation."""
        rows = self.db.execute(
            """SELECT c.document_id, c.content, c.page_number, d.title AS title
               FROM chunks c
               JOIN documents d ON d.id = c.document_id
               WHERE d.user_id = ? AND d.project_id = ? AND c.document_id = ?
                 AND c.content != ''
               ORDER BY c.page_number""",
            (user_id, project_id, paper_id),
        ).fetchall()
        selected = []
        step = max(1, len(rows) // self.CHUNKS_PER_PAPER) if rows else 1
        for i in range(0, len(rows), step):
            selected.append(rows[i])
            if len(selected) >= self.CHUNKS_PER_PAPER:
                break
        return [
            {
                "document_id": row["document_id"],
                "title": row["title"],
                "page": row["page_number"],
                "content": row["content"],
            }
            for row in selected
        ]

    def paper_summary_prompt(self, paper_title: str, sources: List[dict]) -> Tuple[str, str]:
        """Builds a prompt to generate a concise summary of a single paper with citations."""
        context = []
        for source in sources:
            page = f", Page {source['page']}" if source.get("page") else ""
            context.append(f"[Source: {source['title']}{page}]\n{source['content']}")
        system = (
            "You are a research analyst summarizing a single academic paper. "
            "Provide a concise, accurate summary grounded in the provided excerpts. "
            "Use parenthetical citations (Author, Year) or (Author, Year, p. X) when "
            "referencing specific claims. Follow APA 7th edition citation rules."
        )
        user_prompt = (
            f'Paper: "{paper_title}"\n\n'
            "Excerpts:\n"
            + "\n\n".join(context)
            + "\n\nWrite a concise summary (3-5 sentences) of this paper's contribution, "
            "methods, and key findings. Cite sources using parenthetical references "
            "(Author, Year) where appropriate. Base it strictly on the excerpts."
        )
        return system, user_prompt

    # --- AI-judged graph edges (similarity + citations) ----------------------

    def related_pairs(self, user_id: str, papers: List[dict]) -> List[dict]:
        """Asks the configured LLM which paper pairs are topically related, so
        the map gets similarity edges that embedding cosine similarity missed
        (or when no embedding provider is configured). Best-effort: returns []
        when no model is available or the call fails.

        Returns edge-like rows: ``{"source", "target", "weight", "edge_type"}``.
        """
        papers = (papers or [])[:MAX_AI_PAPERS]
        if len(papers) < 2:
            return []
        lines = []
        for i, paper in enumerate(papers, 1):
            title = (paper.get("title") or "Untitled").strip()
            year = paper.get("year")
            abstract = (paper.get("abstract") or "").strip().replace("\n", " ")
            abstract = abstract[:AI_ABSTRACT_CAP]
            meta = f"{title} ({year})." if year else f"{title}."
            if abstract:
                meta += f" Abstract: {abstract}"
            lines.append(f"{i}. {meta}")
        system = (
            "You are a research assistant. Given a numbered list of research papers, "
            'identify pairs of papers that are topically related — they share a research '
            'area, method, subject matter or directly build on each other. Reply with '
            'STRICT JSON only: an array of objects with keys "a" (integer paper index), '
            '"b" (integer paper index, distinct from a) and "similarity" (number 0-1). '
            "Return [] if no pairs are related."
        )
        user = "\n".join(lines) + "\n\nReturn the related pairs as JSON."
        try:
            raw = asyncio.run(self._call(user_id, system, user))
            parsed = self._as_list(self._parse_json(raw))
        except Exception:
            return []
        by_index = {i: p["id"] for i, p in enumerate(papers, 1)}
        out: List[dict] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            a, b = item.get("a"), item.get("b")
            if a not in by_index or b not in by_index or a == b:
                continue
            sim = item.get("similarity")
            try:
                sim = float(sim) if sim is not None else 0.7
            except (TypeError, ValueError):
                sim = 0.7
            weight = round(min(max(sim, 0.55), 1.0), 3)
            out.append(
                {
                    "source": by_index[a],
                    "target": by_index[b],
                    "weight": weight,
                    "edge_type": "similarity",
                }
            )
        return out

    def match_reference_lines(
        self,
        user_id: str,
        refs: List[dict],
        papers: List[dict],
    ) -> List[dict]:
        """Asks the configured LLM to match bibliography lines that the fuzzy
        title matcher could not resolve against the project's papers. Best-
        effort: returns [] when no model is available or the call fails.

        ``refs`` is a list of ``{"paper_id", "raw_ref"}``. Returns matched rows
        shaped like ``save_references`` expects.
        """
        refs = (refs or [])[:MAX_AI_REF_LINES]
        papers = (papers or [])[:MAX_AI_PAPERS]
        if not refs or len(papers) < 2:
            return []
        paper_lines = []
        for i, p in enumerate(papers, 1):
            line = f"{i}. {(p.get('title') or 'Untitled').strip()}"
            authors = (p.get("authors") or [])[:3]
            if authors:
                line += f" — {', '.join(authors)}"
            if p.get("year"):
                line += f", {p['year']}"
            paper_lines.append(line)
        ref_lines = [f"[{i}] {r['raw_ref']}" for i, r in enumerate(refs, 1)]
        system = (
            "You match bibliography reference lines to a numbered list of candidate "
            "papers. Decide which reference lines cite one of the listed papers — an "
            "exact title match, or a plausible match despite abbreviations, initials "
            "or minor garbling (OCR errors) still counts. Reply with STRICT JSON only: "
            'an array of objects with keys "ref_index" (integer), "paper_index" '
            '(integer) and "confidence" (number 0-1). Return [] if none of the lines '
            "cite a listed paper. Do not invent matches."
        )
        user = (
            "Papers:\n"
            + "\n".join(paper_lines)
            + "\n\nReference lines:\n"
            + "\n".join(ref_lines)
            + "\n\nReturn the matches as JSON."
        )
        try:
            raw = asyncio.run(self._call(user_id, system, user))
            parsed = self._as_list(self._parse_json(raw))
        except Exception:
            return []
        by_paper = {i: p["id"] for i, p in enumerate(papers, 1)}
        out: List[dict] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            ri = item.get("ref_index")
            pi = item.get("paper_index")
            if not isinstance(ri, int) or not 1 <= ri <= len(refs):
                continue
            if pi not in by_paper:
                continue
            ref = refs[ri - 1]
            if ref["paper_id"] == by_paper[pi]:
                continue
            conf = item.get("confidence")
            try:
                conf = float(conf) if conf is not None else 0.7
            except (TypeError, ValueError):
                conf = 0.7
            confidence = round(min(max(conf, 0.5), 1.0), 3)
            out.append(
                {
                    "paper_id": ref["paper_id"],
                    "raw_ref": ref["raw_ref"],
                    "matched_paper_id": by_paper[pi],
                    "confidence": confidence,
                }
            )
        return out
