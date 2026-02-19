from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)


class ReviewRequest(BaseModel):
    human_decision: Literal["approved", "needs_script_revision", "find_more_assets", "reassemble"]
    review_notes: str = ""


class JobSummary(BaseModel):
    job_id: str
    topic: str
    status: str
    created_at: datetime
    updated_at: datetime


class JobDetail(BaseModel):
    job_id: str
    thread_id: str
    topic: str
    status: str
    created_at: datetime
    updated_at: datetime
    state: dict[str, Any]
    review_payload: dict[str, Any] | None = None
    error: str | None = None


class LibraryItem(BaseModel):
    job_id: str | None = None
    topic: str | None = None
    script: str | None = None
    final_video: str | None = None
    final_video_url: str | None = None
    metadata_path: str | None = None
    created_at: datetime | None = None
