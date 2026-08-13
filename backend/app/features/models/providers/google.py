import json
from typing import AsyncGenerator, List

import httpx

from app.features.models.providers.base import BaseLLMProvider


class GoogleProvider(BaseLLMProvider):
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
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_id}:streamGenerateContent"
        )
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].append({"text": m["content"]})
            else:
                contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        params = {"alt": "sse", "key": self.api_key}

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream("POST", url, json=payload, params=params) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data:
                        continue
                    try:
                        chunk = json.loads(data)
                        candidates = chunk.get("candidates", [])
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            if "text" in p:
                                yield p["text"]
                    except json.JSONDecodeError:
                        continue
