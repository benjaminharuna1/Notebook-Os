from pathlib import Path
from typing import List

from app.core.config import settings

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "_system" / "prompts"


class PromptBuilder:

    # Rough token estimator: ~4 chars per token (English)
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _truncate_to_budget(parts: list[str], budget_tokens: int) -> list[str]:
        """Keep as many parts as fit within the token budget, preserving order."""
        result = []
        used = 0
        for p in parts:
            t = PromptBuilder._estimate_tokens(p)
            if used + t > budget_tokens:
                break
            result.append(p)
            used += t
        return result

    @staticmethod
    def _load_prompt(name: str) -> str:
        """Load a prompt section from the _system/prompts/ directory.
        Falls back to empty string if the file doesn't exist."""
        path = _PROMPTS_DIR / name
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        return ""

    def build(
        self,
        sources: List,
        question: str,
        skill_instructions: str = "",
        cluster_context: str = "",
        lit_entries_context: str = "",
        slash_extra: str = "",
        apa_references: str = "",
        web_results: str = "",
        past_project_chats: str = "",
        project_memory: str = "",
    ) -> str:
        # --- format source chunks ---
        raw_source_parts = []
        for s in sources:
            raw_source_parts.append(
                f"[Indexed Paper: {s.document_title}, Page {s.page_number}]\n{s.content}"
            )

        # Budget for search-result chunks (most important context)
        source_parts = self._truncate_to_budget(raw_source_parts, settings.PROMPT_BUDGET_SOURCES)
        context = "\n\n".join(source_parts)

        has_sources = len(source_parts) > 0

        # --- base system prompt (loaded from _system/prompts/) ---
        prompt = self._load_prompt("base_system.md")

        # --- APA citation rules (loaded from _system/prompts/) ---
        apa_citation = self._load_prompt("apa_citation.md")
        if apa_citation:
            prompt += "\n\n" + apa_citation

        # --- secondary sources (loaded from _system/prompts/) ---
        secondary = self._load_prompt("secondary_sources.md")
        if secondary:
            prompt += "\n\n" + secondary

        # --- reference handling (loaded from _system/prompts/) ---
        ref_handling = self._load_prompt("reference_handling.md")
        if ref_handling:
            prompt += "\n\n" + ref_handling

        # --- no-results signal ---
        if not has_sources:
            prompt += """

IMPORTANT: No relevant content was found in the indexed journals for this question. You MUST respond with exactly:
"This information is not available in the indexed journals. You may want to try rephrasing your question or checking if the relevant papers have been uploaded."
Do NOT attempt to answer using general knowledge. Do NOT guess."""

        # --- skills (after base, before context) ---
        if skill_instructions:
            prompt += (
                "\n\nActive skills you should follow:\n"
                f"{skill_instructions}"
            )

        if slash_extra:
            prompt += (
                "\n\nSpecial instruction for this request:\n"
                f"{slash_extra}"
            )

        # --- cluster context ---
        if cluster_context:
            prompt += (
                "\n\nLiterature themes in this project (clusters of related papers):\n"
                f"{cluster_context}"
            )

        # --- literature entries ---
        if lit_entries_context:
            lit_tokens = self._estimate_tokens(lit_entries_context)
            if lit_tokens > settings.PROMPT_BUDGET_LIT_ENTRIES:
                lit_entries_context = lit_entries_context[:settings.PROMPT_BUDGET_LIT_ENTRIES * 4]
            prompt += (
                "\n\nLiterature mapping entries for papers in this project:\n"
                f"{lit_entries_context}"
            )

        # --- past project conversations ---
        if past_project_chats:
            pc_tokens = self._estimate_tokens(past_project_chats)
            if pc_tokens > settings.PROMPT_BUDGET_PAST_CHATS:
                past_project_chats = past_project_chats[:settings.PROMPT_BUDGET_PAST_CHATS * 4]
            prompt += (
                "\n\nPrevious conversations in this project (for context — do NOT repeat this information unless the user asks):\n"
                f"{past_project_chats}"
            )

        # --- accumulated project memory (learned facts/preferences) ---
        if project_memory:
            pm_tokens = self._estimate_tokens(project_memory)
            if pm_tokens > settings.PROMPT_BUDGET_PROJECT_MEMORY:
                project_memory = project_memory[:settings.PROMPT_BUDGET_PROJECT_MEMORY * 4]
            prompt += (
                "\n\nAccumulated knowledge about this project (learned from prior interactions):\n"
                f"{project_memory}"
            )

        # --- search results and question (MOST IMPORTANT — at the end for recency bias) ---
        prompt += f"""

Context from the user's indexed journals:
{context}"""

        if apa_references:
            prompt += f"""

Available APA references (use these exact formats for in-text citation author names and years):
{apa_references}"""

        if web_results:
            prompt += web_results

        prompt += f"""

Question: {question}

Read ALL the context chunks above carefully. Answer the question using information from the indexed journals. Cite sources with (Author, Year) or Author (Year) as appropriate. When multiple papers support a claim, cite them: (Author1, Year1; Author2, Year2). Synthesize across chunks — the answer may require combining information from multiple papers. Do NOT start with formal preambles — just answer naturally."""

        return prompt
