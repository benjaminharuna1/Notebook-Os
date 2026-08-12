from pydantic import BaseModel
from typing import Optional


class Chunk(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    token_count: int = 0
