from typing import List


class PromptBuilder:
    def build(
        self,
        sources: List,
        question: str,
        skill_instructions: str = "",
        cluster_context: str = "",
        lit_entries_context: str = "",
        slash_extra: str = "",
    ) -> str:
        context_parts = []
        for s in sources:
            context_parts.append(f"[Source: {s.document_title}, Page {s.page_number}]\n{s.content}")

        context = "\n\n".join(context_parts)

        prompt = """You are a research assistant. Answer the question based on the provided context.

CITATION RULES (APA 7th Edition):
- Every factual claim MUST include a parenthetical citation: (Author, Year) or (Author, Year, p. X).
- For multiple sources: (Author1, Year1; Author2, Year2).
- When no author: ("Short Title", Year). When no date: (Author, n.d.).
- End answers with a References section listing all cited works when there are 3+ sources.
- Never invent page numbers, authors, or years not in the provided context.

Use Markdown formatting for your answers: headers for sections, bullet lists for points, bold for emphasis, and tables when comparing items."""

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

        if cluster_context:
            prompt += (
                "\n\nLiterature themes in this project (clusters of related papers):\n"
                f"{cluster_context}"
            )

        if lit_entries_context:
            prompt += (
                "\n\nLiterature mapping entries for papers in this project:\n"
                f"{lit_entries_context}"
            )

        prompt += f"""

Context:
{context}

Question: {question}

Answer concisely and cite ALL sources using parenthetical references (Author, Year)."""

        return prompt
