from typing import List


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

    def build(
        self,
        sources: List,
        question: str,
        skill_instructions: str = "",
        cluster_context: str = "",
        lit_entries_context: str = "",
        slash_extra: str = "",
    ) -> str:
        # --- format source chunks ---
        raw_source_parts = []
        for s in sources:
            raw_source_parts.append(
                f"[Indexed Paper: {s.document_title}, Page {s.page_number}]\n{s.content}"
            )

        # Budget: 6000 tokens for search-result chunks (most important context)
        source_parts = self._truncate_to_budget(raw_source_parts, 6000)
        context = "\n\n".join(source_parts)

        has_sources = len(source_parts) > 0

        # --- base system prompt ---
        prompt = """You are a research assistant integrated into a Notebook OS. The user has indexed their own collection of academic papers and journals into this system. Your primary job is to answer questions accurately using THOSE indexed documents as your ground truth.

CORE RULES:
1. ALWAYS base your answer on the indexed journal content provided in the context below. These are the user's own papers — they are your primary knowledge source.
2. When search results and literature entries are provided, those are excerpts from the user's indexed journals. Treat them as authoritative and grounded evidence.
3. If the context contains relevant indexed content, use it exclusively. Do not draw on outside general knowledge unless the user explicitly asks for it.
4. When multiple indexed papers are relevant, synthesize across them — highlight areas of agreement, disagreement, and gaps.
5. If the indexed content does NOT contain enough information to answer the question fully, say so clearly. Do not fabricate claims that are not supported by the provided context.
6. NEVER invent paper titles, authors, years, DOIs, page numbers, or any factual detail not explicitly present in the provided context.

CITATION RULES (APA 7th Edition):
- Every factual claim MUST include a parenthetical citation: (Author, Year) or (Author, Year, p. X).
- For multiple sources: (Author1, Year1; Author2, Year2).
- When no author: ("Short Title", Year). When no date: (Author, n.d.).
- End answers with a References section listing all cited works when there are 3+ sources.
- Never invent page numbers, authors, or years not in the provided context.

Use Markdown formatting for your answers: headers for sections, bullet lists for points, bold for emphasis, and tables when comparing items."""

        # --- no-results signal (Fix 7) ---
        if not has_sources:
            prompt += "\n\nIMPORTANT: No relevant content was found in the indexed journals for this question. State that you cannot answer from the available indexed content and suggest what the user could search for. Do NOT guess or use outside knowledge."

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

        # --- literature entries (budget: 4000 tokens) ---
        if lit_entries_context:
            lit_tokens = self._estimate_tokens(lit_entries_context)
            if lit_tokens > 4000:
                # Truncate by cutting entries (each ~200 tokens, so keep ~20)
                lit_entries_context = lit_entries_context[:4000 * 4]
            prompt += (
                "\n\nLiterature mapping entries for papers in this project:\n"
                f"{lit_entries_context}"
            )

        # --- search results and question (MOST IMPORTANT — at the end for recency bias) ---
        prompt += f"""

Context from the user's indexed journals:
{context}

Question: {question}

Based on the indexed journals above, provide an accurate, well-cited answer.
If the indexed content is insufficient, state what is missing rather than guessing.
Always cite your sources using parenthetical references (Author, Year)."""

        return prompt
