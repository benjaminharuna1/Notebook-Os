import asyncio
import json
import re
from typing import List, Optional, Tuple

from app.features.models.service import ModelService

ENTRY_KEYS = ("research_objective", "methodology", "key_findings", "limitations", "relevance")
MAX_PAPER_CHUNKS = 8
CHUNK_CHAR_CAP = 1800


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

    # --- cluster labeling ----------------------------------------------------

    def cluster_inputs(self, user_id: str, project_id: str) -> List[dict]:
        """Cluster id -> member titles from the latest literature checkpoint."""
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
        by_cluster: dict = {}
        for node in data.get("nodes", []):
            cid = node.get("cluster")
            if cid:
                by_cluster.setdefault(cid, []).append(node.get("label", ""))
        return [{"id": cid, "titles": titles} for cid, titles in by_cluster.items()]

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
    def _parse_json(raw: str) -> dict:
        cleaned = raw.strip()
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return {}

    # --- paper literature-review entries ------------------------------------

    def _paper_chunks(self, paper_id: str, limit: int = MAX_PAPER_CHUNKS) -> List[str]:
        rows = self.db.execute(
            """SELECT content FROM chunks
               WHERE document_id = ?
               ORDER BY page_number ASC, chunk_index ASC""",
            (paper_id,),
        ).fetchall()
        out: List[str] = []
        for row in rows:
            text = (row["content"] or "").strip()
            if not text:
                continue
            if len(text) > CHUNK_CHAR_CAP:
                text = text[:CHUNK_CHAR_CAP]
            out.append(text)
            if len(out) >= limit:
                break
        return out

    def _paper_prompt(self, paper: dict, chunks: List[str]) -> Tuple[str, str]:
        header = [f"Title: {paper.get('title') or 'Untitled'}"]
        authors = paper.get("authors") or []
        if authors:
            header.append("Authors: " + "; ".join(authors))
        if paper.get("year"):
            header.append(f"Year: {paper['year']}")
        if paper.get("abstract"):
            header.append(f"Abstract: {paper['abstract']}")
        excerpts = [f"[Excerpt {i}]\n{chunk}" for i, chunk in enumerate(chunks, 1)]
        if not excerpts:
            excerpts = ["[No full text available — rely on the title and abstract.]"]
        system = (
            "You are a research analyst building a literature review matrix. "
            "For the given paper, produce five concise fields. Reply with STRICT "
            'JSON only, with exactly these keys: "research_objective", "methodology", '
            '"key_findings", "limitations", "relevance". Each value should be 2-4 '
            "sentences, grounded in the paper's text. Define each field as: "
            "research_objective = primary purpose/hypothesis; "
            "methodology = research design, data sources, sample size/demographics; "
            "key_findings = main empirical or theoretical conclusions; "
            "limitations = constrained samples, bias, scope limits, unaddressed variables; "
            "relevance = how this study could inform the researcher's own work "
            "(supports a method, contradicts a theory, provides context)."
        )
        user_prompt = (
            "\n\n".join(header)
            + "\n\n"
            + "\n\n".join(excerpts)
            + '\n\nReturn only the JSON object now.'
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
        """Runs one LLM entry pass. In auto mode failures are silent (the build
        must not abort); in overwrite mode (explicit regenerate) failures raise."""
        try:
            model = self.active_model(user_id)
            if not model:
                raise ValueError("No active model configured — pick one in Settings")
            system, prompt = self._paper_prompt(paper, self._paper_chunks(paper["id"]))
            raw = await self._call(user_id, system, prompt)
            parsed = self._parse_json(raw)
        except Exception:
            if overwrite:
                raise
            return
        fields = {key: (parsed.get(key) or "").strip() for key in ENTRY_KEYS}
        if overwrite:
            merged = {key: (fields.get(key) or None) for key in ENTRY_KEYS}
            service.upsert_entry(
                paper["id"], user_id, project_id, merged, auto=False, auto_generated=True
            )
        else:
            service.upsert_entry(paper["id"], user_id, project_id, fields, auto=True)

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
                if not filled:
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
        titles = next((c["titles"] for c in inputs if c["id"] == cluster_id), [])
        if not titles:
            return []
        title_set = {t.lower() for t in titles}
        rows = self.db.execute(
            """SELECT c.document_id, c.content, c.page_number, d.title AS title
               FROM chunks c
               JOIN documents d ON d.id = c.document_id
               WHERE d.user_id = ? AND d.project_id = ? AND c.content != ''""",
            (user_id, project_id),
        ).fetchall()
        per_doc: dict = {}
        for row in rows:
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
            "papers says about its shared theme."
        )
        user_prompt = (
            f'Theme: "{cluster_label}"\n\n'
            "Passages:\n"
            + "\n\n".join(context)
            + f'\n\nWrite a concise summary (3-5 sentences) of the theme "{cluster_label}": '
            "what these papers contribute, their shared methods or findings, and any "
            "gaps or contradictions. Base it strictly on the passages."
        )
        return system, user_prompt
