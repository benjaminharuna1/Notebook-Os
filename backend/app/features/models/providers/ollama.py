from typing import AsyncGenerator, List

import httpx

from app.core.config import settings
from app.features.models.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL) as client:
            ollama_messages = [{"role": "system", "content": prompt}]
            for m in messages:
                ollama_messages.append({"role": m["role"], "content": m["content"]})

            async with client.stream(
                "POST",
                "/api/chat",
                json={"model": self.model_id, "messages": ollama_messages, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
