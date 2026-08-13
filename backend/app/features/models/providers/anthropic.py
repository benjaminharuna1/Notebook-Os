import json
from typing import AsyncGenerator, List

import httpx

from app.features.models.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self,
        model_id: str,
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.model_id = model_id
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        anthropic_messages = []
        for m in messages:
            role = "assistant" if m["role"] == "assistant" else "user"
            anthropic_messages.append({"role": role, "content": m["content"]})

        payload = {
            "model": self.model_id,
            "system": prompt,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {}).get("text", "")
                            if delta:
                                yield delta
                    except json.JSONDecodeError:
                        continue
