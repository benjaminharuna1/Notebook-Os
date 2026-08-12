from pydantic import BaseModel
from typing import Optional


class IngestionResponse(BaseModel):
    document_id: str
    status: str
    estimated_time: int


class IngestionStatus(BaseModel):
    document_id: str
    status: str
    progress: int
    chunks_created: int
    error: Optional[str] = None
