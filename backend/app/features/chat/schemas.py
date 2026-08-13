from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    document_ids: Optional[List[str]] = None
    project_id: Optional[str] = None


class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: Optional[str] = None
    model_used: Optional[str] = None
    created_at: Optional[str] = None


class ChatSession(BaseModel):
    id: str
    title: Optional[str] = None
    model_used: Optional[str] = None
    project_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
