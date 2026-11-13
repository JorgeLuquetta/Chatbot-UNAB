"""Lógica de las herramientas de consulta: búsqueda vectorial y cursos del estudiante."""
from __future__ import annotations

from .embeddings import Embedder
from .models import DocumentChunk, StudentCourseRecord
from .stores import CourseStore, DocumentStore

MAX_TOP_K = 20


async def search_documents(query: str, top_k: int, store: DocumentStore, embedder: Embedder) -> list[DocumentChunk]:
    """Top-k chunks más similares (coseno), ordenados por similarity_score descendente."""
    if not query or not query.strip():
        return []
    top_k = max(1, min(int(top_k), MAX_TOP_K))
    [embedding] = await embedder.embed([query.strip()])
    results = await store.search(embedding, top_k)
    return sorted(results, key=lambda c: c.similarity_score, reverse=True)[:top_k]


async def get_student_courses(session_id: str, store: CourseStore) -> StudentCourseRecord:
    """Cursos del estudiante dueño de `session_id`. Nunca mezcla registros de otras sesiones."""
    if not session_id or not session_id.strip():
        raise ValueError("session_id es obligatorio")
    courses = await store.get_by_session(session_id)
    return StudentCourseRecord.build(session_id, courses)
