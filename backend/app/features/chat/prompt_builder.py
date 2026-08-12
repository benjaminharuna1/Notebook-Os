from typing import List


class PromptBuilder:
    def build(self, sources: List, question: str) -> str:
        context_parts = []
        for s in sources:
            context_parts.append(f"[Source: {s.document_title}, Page {s.page_number}]\n{s.content}")

        context = "\n\n".join(context_parts)

        return f"""You are a research assistant. Answer the question based on the provided context.

Context:
{context}

Question: {question}

Answer concisely and cite sources when relevant."""
