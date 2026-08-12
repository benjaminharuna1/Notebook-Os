from typing import AsyncGenerator, List

from app.features.models.providers.base import BaseLLMProvider


class GoogleProvider(BaseLLMProvider):
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Google provider is planned for Phase 2")
