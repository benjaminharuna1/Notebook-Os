from typing import List


class PromptBuilder:
    def build(self, sources: List, question: str, skill_instructions: str = "") -> str:
        context_parts = []
        for s in sources:
            context_parts.append(f"[Source: {s.document_title}, Page {s.page_number}]\n{s.content}")

        context = "\n\n".join(context_parts)

        prompt = """You are a research assistant. Answer the question based on the provided context."""

        if skill_instructions:
            prompt += (
                "\n\nActive skills you should follow:\n"
                f"{skill_instructions}"
            )

        prompt += f"""

Context:
{context}

Question: {question}

Answer concisely and cite sources when relevant."""

        return prompt
