"""Contenedor de dependencias perezoso (se puede sustituir en tests)."""
from __future__ import annotations

import os

from .db import get_pool
from .embeddings import Embedder, HashEmbedder, OpenAIEmbedder
from .stores import (CourseStore, DocumentStore, NewsStore, PgCourseStore, PgDocumentStore,
                     PgNewsStore)


class Services:
    def __init__(self) -> None:
        self._embedder: Embedder | None = None
        self._docs: DocumentStore | None = None
        self._courses: CourseStore | None = None
        self._news: NewsStore | None = None

    def embedder(self) -> Embedder:
        if self._embedder is None:
            # EMBEDDINGS_PROVIDER=hash permite desarrollo local sin API key (no semántico).
            if os.getenv("EMBEDDINGS_PROVIDER", "openai").lower() == "hash":
                self._embedder = HashEmbedder()
            else:
                self._embedder = OpenAIEmbedder()
        return self._embedder

    async def document_store(self) -> DocumentStore:
        if self._docs is None:
            self._docs = PgDocumentStore(await get_pool())
        return self._docs

    async def course_store(self) -> CourseStore:
        if self._courses is None:
            self._courses = PgCourseStore(await get_pool())
        return self._courses

    async def news_store(self) -> NewsStore:
        if self._news is None:
            self._news = PgNewsStore(await get_pool())
        return self._news

    def override(self, *, embedder=None, documents=None, courses=None, news=None) -> None:
        self._embedder = embedder or self._embedder
        self._docs = documents or self._docs
        self._courses = courses or self._courses
        self._news = news or self._news


services = Services()
