"""Modelos de datos que retornan las herramientas MCP."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CourseStatus = Literal["completed", "pending", "in_progress"]


class DocumentChunk(BaseModel):
    document_name: str
    chunk_index: int
    text: str
    similarity_score: float


class Course(BaseModel):
    course_code: str
    course_name: str
    semester: int
    status: CourseStatus
    grade: float | None = None


class StudentCourseRecord(BaseModel):
    session_id: str
    courses: list[Course] = Field(default_factory=list)
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    pending: int = 0
    progress_percentage: float = 0.0

    @classmethod
    def build(cls, session_id: str, courses: list[Course]) -> "StudentCourseRecord":
        total = len(courses)
        completed = sum(c.status == "completed" for c in courses)
        in_progress = sum(c.status == "in_progress" for c in courses)
        pending = sum(c.status == "pending" for c in courses)
        pct = round(100.0 * completed / total, 1) if total else 0.0
        ordered = sorted(courses, key=lambda c: (c.semester, c.course_code))
        return cls(session_id=session_id, courses=ordered, total=total, completed=completed,
                   in_progress=in_progress, pending=pending, progress_percentage=pct)


class ChunkRecord(BaseModel):
    document_name: str
    chunk_index: int
    total_chunks: int
    content: str
    embedding: list[float]


class IngestionError(BaseModel):
    document_name: str
    chunk_index: int | None = None
    error_message: str


class IngestionReport(BaseModel):
    total_documents: int = 0
    processed_documents: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    errors: list[IngestionError] = Field(default_factory=list)


class Article(BaseModel):
    title: str
    published_at: datetime
    summary: str
    source_url: str
    # educacion | tecnologia | ingenieria-sistemas | general (ver scraper.classify)
    category: str = "general"
    source_name: str = "UNAB"
    image_url: str | None = None   # imagen de la noticia (RSS, listado HTML u og:image de la página)
    tags: list[str] = Field(default_factory=list, exclude=True)  # etiquetas del RSS (solo para clasificar)


class ScraperReport(BaseModel):
    total_sources: int = 0
    total_extracted: int = 0
    total_inserted: int = 0
    skipped_duplicates: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    with_image: int = 0
    failed_sources: list[str] = Field(default_factory=list)
