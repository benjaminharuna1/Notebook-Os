from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    """Self-contained description of a skill. Prompt-level skills carry
    instructions that are injected into the chat prompt when enabled; the
    format is designed so tool/MCP fields can be added later."""

    id: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9-_]*$")
    name: str
    version: str = "1.0.0"
    description: str
    category: str = "general"
    author: str = "unknown"
    instructions: str
    example_workflow: str | None = None
    tags: list[str] = []


class SkillInstallRequest(BaseModel):
    skill_id: str


class SkillEnableRequest(BaseModel):
    enabled: bool
