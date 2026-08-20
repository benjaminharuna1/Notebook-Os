from pydantic import BaseModel
from typing import Optional


class ModelConfig(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    is_active: bool = False
    is_default: bool = False
    config: Optional[str] = None


class SwitchModelRequest(BaseModel):
    model_id: str


class DownloadModelRequest(BaseModel):
    key: str


class CustomDownloadRequest(BaseModel):
    url: str
    name: Optional[str] = None
