from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    title: str
    file_type: str
    size_bytes: int
    status: str
    page_count: int
    chunk_count: int
    ocr_pages: list[int]
    source_date: str | None = None
    outdated: bool = False
    created_at: datetime


class Citation(BaseModel):
    document_id: str
    document_title: str
    page: int
    excerpt: str
    source_date: str | None = None
    outdated: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class AnswerOut(BaseModel):
    id: str
    question: str
    answer: str
    abstained: bool
    citations: list[Citation]
    latency_ms: float
    warnings: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    rating: Literal["helpful", "unhelpful"]
    comment: str | None = Field(default=None, max_length=2000)
