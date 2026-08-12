from abc import ABC, abstractmethod
from typing import AsyncGenerator, List


class BaseLLMProvider(ABC):
    def __init__(self, model_id: str):
        self.model_id = model_id

    @abstractmethod
    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        pass
