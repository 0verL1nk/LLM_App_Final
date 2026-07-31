from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    archived: bool | None = None


class SessionCreate(BaseModel):
    session_name: str = Field(default="新会话", max_length=120)
    parent_session_uid: str | None = Field(default=None, max_length=120)


class SessionUpdate(BaseModel):
    session_name: str | None = Field(default=None, max_length=120)
    is_pinned: bool | None = None


class TurnCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)


class RunCreate(TurnCreate):
    client_request_id: str = Field(min_length=8, max_length=200)


class SettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=1000)
    model_name: str = Field(default="", max_length=200)
    base_url: str = Field(default="", max_length=1000)
    rag_index_batch_size: int | None = Field(default=None, ge=1, le=4096)
    local_rag_project_max_chars: int | None = Field(default=None, ge=0)
    local_rag_project_max_chunks: int | None = Field(default=None, ge=0)


class ApiEnvelope(BaseModel):
    data: Any
