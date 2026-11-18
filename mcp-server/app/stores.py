"""Acceso a datos. Cada store tiene implementación PostgreSQL (asyncpg) y en memoria (tests)."""
from __future__ import annotations

import math
from typing import Protocol, Sequence

from .embeddings import to_pgvector
from .models import Article, ChunkRecord, Course, DocumentChunk


# ---------------------------------------------------------------- protocolos
class DocumentStore(Protocol):
    async def search(self, embedding: Sequence[float], top_k: int) -> list[DocumentChunk]: ...
    async def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> None: ...
    async def get_chunk(self, document_name: str, chunk_index: int) -> ChunkRecord | None: ...


class CourseStore(Protocol):
    async def get_by_session(self, session_id: str) -> list[Course]: ...


class NewsStore(Protocol):
    async def existing_urls(self, urls: Sequence[str]) -> set[str]: ...
    async def insert(self, articles: Sequence[Article]) -> int: ...


# ---------------------------------------------------------------- PostgreSQL
class PgDocumentStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def search(self, embedding: Sequence[float], top_k: int) -> list[DocumentChunk]:
        rows = await self.pool.fetch(
            """
            SELECT document_name, chunk_index, content,
                   1 - (embedding <=> $1::vector) AS similarity_score
              FROM document_chunks
             WHERE embedding IS NOT NULL
             ORDER BY embedding <=> $1::vector
             LIMIT $2
            """,
            to_pgvector(embedding), top_k,
        )
        return [DocumentChunk(document_name=r["document_name"], chunk_index=r["chunk_index"],
                              text=r["content"], similarity_score=float(r["similarity_score"]))
                for r in rows]

    async def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO document_chunks (document_name, chunk_index, total_chunks, content, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    ON CONFLICT (document_name, chunk_index) DO UPDATE
                       SET total_chunks = EXCLUDED.total_chunks,
                           content = EXCLUDED.content,
                           embedding = EXCLUDED.embedding,
                           created_at = now()
                    """,
                    [(c.document_name, c.chunk_index, c.total_chunks, c.content, to_pgvector(c.embedding))
                     for c in chunks],
                )
                # Si el documento se acortó, elimina chunks sobrantes de ingestas anteriores
                if chunks:
                    await conn.execute(
                        "DELETE FROM document_chunks WHERE document_name = $1 AND chunk_index >= $2",
                        chunks[0].document_name, chunks[0].total_chunks,
                    )

    async def get_chunk(self, document_name: str, chunk_index: int) -> ChunkRecord | None:
        r = await self.pool.fetchrow(
            "SELECT document_name, chunk_index, total_chunks, content, embedding::text AS emb "
            "FROM document_chunks WHERE document_name = $1 AND chunk_index = $2",
            document_name, chunk_index,
        )
        if r is None:
            return None
        emb = [float(x) for x in r["emb"].strip("[]").split(",")] if r["emb"] else []
        return ChunkRecord(document_name=r["document_name"], chunk_index=r["chunk_index"],
                           total_chunks=r["total_chunks"], content=r["content"], embedding=emb)


class PgCourseStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def get_by_session(self, session_id: str) -> list[Course]:
        # Aislamiento estricto: el único filtro es el session_id del estudiante autenticado.
        rows = await self.pool.fetch(
            "SELECT course_code, course_name, semester, status, grade FROM student_courses "
            "WHERE student_session = $1 ORDER BY semester, course_code",
            session_id,
        )
        return [Course(course_code=r["course_code"], course_name=r["course_name"], semester=r["semester"],
                       status=r["status"], grade=float(r["grade"]) if r["grade"] is not None else None)
                for r in rows]


class PgNewsStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def existing_urls(self, urls: Sequence[str]) -> set[str]:
        if not urls:
            return set()
        rows = await self.pool.fetch("SELECT source_url FROM noticias WHERE source_url = ANY($1::text[])", list(urls))
        return {r["source_url"] for r in rows}

    async def insert(self, articles: Sequence[Article]) -> int:
        inserted = 0
        async with self.pool.acquire() as conn:
            for a in articles:
                status = await conn.execute(
                    "INSERT INTO noticias (title, published_at, summary, source_url) VALUES ($1, $2, $3, $4) "
                    "ON CONFLICT (source_url) DO NOTHING",
                    a.title, a.published_at, a.summary, a.source_url,
                )
                inserted += int(status.split()[-1])
        return inserted


# ---------------------------------------------------------------- en memoria
def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class InMemoryDocumentStore:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.rows: dict[tuple[str, int], ChunkRecord] = {}
        self.fail_on = fail_on or set()

    async def search(self, embedding: Sequence[float], top_k: int) -> list[DocumentChunk]:
        scored = [DocumentChunk(document_name=c.document_name, chunk_index=c.chunk_index, text=c.content,
                                similarity_score=_cosine(embedding, c.embedding)) for c in self.rows.values()]
        scored.sort(key=lambda d: d.similarity_score, reverse=True)
        return scored[:top_k]

    async def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> None:
        if chunks and chunks[0].document_name in self.fail_on:
            raise RuntimeError(f"fallo simulado de almacenamiento: {chunks[0].document_name}")
        for c in chunks:
            self.rows[(c.document_name, c.chunk_index)] = c

    async def get_chunk(self, document_name: str, chunk_index: int) -> ChunkRecord | None:
        return self.rows.get((document_name, chunk_index))


class InMemoryCourseStore:
    def __init__(self, data: dict[str, list[Course]] | None = None) -> None:
        self.data = data or {}

    async def get_by_session(self, session_id: str) -> list[Course]:
        return list(self.data.get(session_id, []))


class InMemoryNewsStore:
    def __init__(self) -> None:
        self.rows: dict[str, Article] = {}

    async def existing_urls(self, urls: Sequence[str]) -> set[str]:
        return {u for u in urls if u in self.rows}

    async def insert(self, articles: Sequence[Article]) -> int:
        n = 0
        for a in articles:
            if a.source_url not in self.rows:
                self.rows[a.source_url] = a
                n += 1
        return n
