from abc import ABC, abstractmethod
from typing import AsyncGenerator, List


class BaseLLMProvider(ABC):
    def __init__(self, model_id: str, settings: dict | None = None):
        self.model_id = model_id
        self.settings = settings or {}

    @abstractmethod
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        pass
