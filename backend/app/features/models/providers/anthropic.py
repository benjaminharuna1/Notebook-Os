from typing import AsyncGenerator, List

from app.features.models.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Anthropic provider is planned for Phase 2")
