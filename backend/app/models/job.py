"""Pydantic models for ingestion job state."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class IngestionJobCreate(BaseModel):
    file_name: str


class IngestionJobStatus(BaseModel):
    id: UUID
    user_id: str
    chat_id: UUID | None = None
    status: str
    current_step: str
    total_messages: int = 0
    processed_messages: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    voyage_tokens_used: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    job_id: str
    message: str
