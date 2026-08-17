from typing import List


class PromptBuilder:
    def build(self, sources: List, question: str, skill_instructions: str = "") -> str:
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
- Never invent page numbers, authors, or years not in the provided context."""

        if skill_instructions:
            prompt += (
                "\n\nActive skills you should follow:\n"
                f"{skill_instructions}"
            )

        prompt += f"""

Context:
{context}

Question: {question}

Answer concisely and cite ALL sources using parenthetical references (Author, Year)."""

        return prompt
