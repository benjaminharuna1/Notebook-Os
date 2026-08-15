import json
from typing import AsyncGenerator, List

import httpx

from app.core.config import settings
from app.features.models.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=timeout) as client:
            ollama_messages = [{"role": "system", "content": prompt}]
            for m in messages:
                ollama_messages.append({"role": m["role"], "content": m["content"]})

            async with client.stream(
                "POST",
                "/api/chat",
                json={"model": self.model_id, "messages": ollama_messages, "stream": True},
            ) as response:
                if response.status_code != 200:
                    try:
                        body = json.loads(await response.aread())
                        detail = body.get("error", response.reason_phrase)
                    except Exception:
                        detail = response.reason_phrase
                    if "not found" in str(detail).lower():
                        detail = f"{detail} — pull it with: ollama pull {self.model_id}"
                    raise RuntimeError(f"Ollama error ({response.status_code}): {detail}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "error" in data:
                        raise RuntimeError(f"Ollama error: {data['error']}")
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
