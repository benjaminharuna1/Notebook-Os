import json
import re
from typing import Dict, List, Optional, Tuple

from app.features.models.service import ModelService


class GraphLLMService:
    """LLM-assisted second layer over the knowledge graph.

    Two jobs:
    * ``refine_query`` maps a user's free-form keyword to the exact concept
      labels that already exist in the graph, so searches that use a different
      phrasing still light up the right nodes.
    * ``summary_sources`` + ``summary_prompt`` back the "what do the papers
      say about this concept" popup, gathering the project's relevant chunks
      (with page numbers) as grounding context for a streamed summary.
    """

    MAX_SOURCES = 8

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
        async for chunk in provider.stream_chat(system_prompt, [{"role": "user", "content": user_prompt}]):
            parts.append(chunk)
        return "".join(parts)

    # --- query refinement ----------------------------------------------------

    def concept_labels(self, user_id: str, project_id: str) -> List[str]:
        row = self.db.execute(
            """SELECT graph_json FROM graph_history
               WHERE user_id = ? AND project_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (user_id, project_id),
        ).fetchone()
        if not row:
            return []
        raw = json.loads(row["graph_json"])
        if not isinstance(raw, dict):
            return []
        return [n.get("label", "") for n in raw.get("nodes", []) if n.get("label")]

    async def refine_query(self, user_id: str, project_id: str, query: str) -> Dict:
        labels = self.concept_labels(user_id, project_id)
        if not labels:
            return {"matches": []}

        system = (
            "You map a user's free-form search keyword to the exact concept labels "
            "from a knowledge graph that best match what they mean."
        )
        user_prompt = (
            f'User search: "{query}"\n\n'
            "Available concept labels:\n"
            + "\n".join(f"- {l}" for l in labels)
            + "\n\nReturn ONLY the matching labels, one per line, exactly as written. "
            "If nothing matches, reply with exactly: NONE"
        )
        try:
            raw = await self._call(user_id, system, user_prompt)
        except ValueError as exc:
            return {"matches": [], "error": str(exc)}

        label_set = set(labels)
        matches: List[str] = []
        for line in raw.splitlines():
            line = line.strip().strip("*").strip("-").strip().strip('"')
            if not line or line.upper() == "NONE":
                continue
            if line in label_set:
                matches.append(line)
                continue
            for lab in labels:
                if lab in line or line in lab:
                    matches.append(lab)

        seen: set = set()
        deduped = [m for m in matches if not (m in seen or seen.add(m))]
        return {"matches": deduped[:12]}

    # --- concept summary -----------------------------------------------------

    def summary_sources(self, user_id: str, project_id: str, label: str) -> List[dict]:
        rows = self.db.execute(
            """SELECT c.id, c.document_id, c.content, c.page_number, d.title AS title
               FROM chunks c
               JOIN documents d ON d.id = c.document_id
               WHERE d.user_id = ? AND d.project_id = ? AND c.content != ''""",
            (user_id, project_id),
        ).fetchall()

        needle = re.compile(rf"\b{re.escape(label)}\b", re.IGNORECASE)
        ranked = []
        for row in rows:
            count = len(needle.findall(row["content"]))
            if count == 0:
                continue
            ranked.append({
                "document_id": row["document_id"],
                "title": row["title"],
                "page": row["page_number"],
                "content": row["content"],
                "count": count,
            })
        ranked.sort(key=lambda r: (-r["count"], r["title"] or "", r["page"] or 0))
        return ranked[: self.MAX_SOURCES]

    def summary_prompt(self, label: str, sources: List[dict]) -> Tuple[str, str]:
        context = []
        for s in sources:
            page = f", Page {s['page']}" if s.get("page") else ""
            context.append(f"[Source: {s['title']}{page}]\n{s['content']}")

        system = (
            "You are a research summarizer. Summarize what the provided passages "
            "from research papers say about a single topic. Use APA 7th edition "
            "citations: include parenthetical citations (Author, Year) for every "
            "factual claim drawn from the sources."
        )
        user_prompt = (
            f'Topic: "{label}"\n\n'
            "Passages:\n"
            + "\n\n".join(context)
            + f'\n\nWrite a concise summary (3-5 sentences) of what the papers say about "{label}". '
            "Cite sources using parenthetical references (Author, Year) where appropriate. "
            "Base it strictly on the passages — do not invent facts."
        )
        return system, user_prompt
