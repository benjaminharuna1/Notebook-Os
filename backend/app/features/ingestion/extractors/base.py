from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedDocument:
    text: str
    title: Optional[str] = None
    author: Optional[str] = None
    page_count: Optional[int] = None
    pages: Optional[list] = None


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> ExtractedDocument:
        pass
