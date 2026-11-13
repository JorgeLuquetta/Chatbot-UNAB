"""Integración con PostgreSQL + pgvector real (se omite si TEST_DB_URL no está definida).

    TEST_DB_URL=postgresql://postgres@localhost:5432/chatbot_test pytest tests/test_pg_stores.py
La base debe tener aplicado db/schema.sql.
"""
import asyncio

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from app.embeddings import HashEmbedder
from app.models import Article, ChunkRecord
from conftest import TEST_DB_URL

pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DB_URL no definida")

DOC = "__test_roundtrip__.pdf"


def _with_pool(fn):
    import asyncpg

    async def run():
        pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=2, statement_cache_size=0)
        try:
            return await fn(pool)
        finally:
            await pool.execute("DELETE FROM document_chunks WHERE document_name LIKE '__test%'")
            await pool.execute("DELETE FROM noticias WHERE source_url LIKE 'https://test.local/%'")
            await pool.execute("DELETE FROM student_courses WHERE student_session LIKE '__test%'")
            await pool.close()

    return asyncio.run(run())


# Feature: chatbot-apoyo-academico, Property 11: Round-trip de almacenamiento de chunks
@hsettings(max_examples=100)
@given(contents=st.lists(st.text(min_size=1, max_size=300).filter(lambda s: "\x00" not in s), min_size=1, max_size=5))
def test_property_11_pg_roundtrip(contents):
    from app.stores import PgDocumentStore

    async def body(pool):
        store = PgDocumentStore(pool)
        vecs = await HashEmbedder().embed(contents)
        recs = [ChunkRecord(document_name=DOC, chunk_index=i, total_chunks=len(contents), content=c, embedding=v)
                for i, (c, v) in enumerate(zip(contents, vecs))]
        await store.upsert_chunks(recs)
        for r in recs:
            got = await store.get_chunk(DOC, r.chunk_index)
            assert got is not None and got.content == r.content
        # re-ingesta más corta elimina sobrantes
        await store.upsert_chunks(recs[:1] and [recs[0].model_copy(update={"total_chunks": 1})])
        assert await store.get_chunk(DOC, 1) is None

    _with_pool(body)


def test_pg_search_returns_min_k_sorted():
    from app.rag import search_documents
    from app.stores import PgDocumentStore

    texts = ["requisitos de grado", "matrícula financiera", "créditos académicos", "horario de clases",
             "prácticas empresariales", "intercambio internacional", "biblioteca", "bienestar universitario"]

    async def body(pool):
        store = PgDocumentStore(pool)
        emb = HashEmbedder()
        vecs = await emb.embed(texts)
        await store.upsert_chunks([ChunkRecord(document_name=f"__test_{i}.pdf", chunk_index=0, total_chunks=1,
                                               content=t, embedding=v) for i, (t, v) in enumerate(zip(texts, vecs))])
        res = await search_documents("requisitos de grado", 5, store, emb)
        assert len(res) == 5
        assert res[0].text == "requisitos de grado"
        assert [r.similarity_score for r in res] == sorted((r.similarity_score for r in res), reverse=True)

    _with_pool(body)


def test_pg_courses_isolation_and_news_dedup():
    from datetime import datetime, timezone

    from app.stores import PgCourseStore, PgNewsStore

    async def body(pool):
        await pool.execute(
            "INSERT INTO student_courses (student_session, course_code, course_name, semester, status) VALUES "
            "('__testA','X1','Curso',1,'completed'), ('__testB','X1','Curso',1,'pending')")
        a = await PgCourseStore(pool).get_by_session("__testA")
        assert [c.status for c in a] == ["completed"]
        news = PgNewsStore(pool)
        art = Article(title="t", published_at=datetime.now(timezone.utc), summary="s",
                      source_url="https://test.local/1")
        assert await news.insert([art]) == 1
        assert await news.insert([art]) == 0
        assert await news.existing_urls([art.source_url]) == {art.source_url}

    _with_pool(body)
