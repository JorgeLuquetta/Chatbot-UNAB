"""Properties 6 y 8."""
import asyncio

from hypothesis import given
from hypothesis import strategies as st

from app.embeddings import HashEmbedder
from app.models import ChunkRecord, Course
from app.rag import get_student_courses, search_documents
from app.stores import InMemoryCourseStore, InMemoryDocumentStore

words = st.text(alphabet="abcdefghijklmnopqrstuvwxyzáéíóúñ ", min_size=1, max_size=40)


def _store_with(texts):
    emb = HashEmbedder(dim=64)
    store = InMemoryDocumentStore()
    vectors = asyncio.run(emb.embed(texts))
    asyncio.run(store.upsert_chunks([
        ChunkRecord(document_name=f"doc{i}.pdf", chunk_index=0, total_chunks=1, content=t, embedding=v)
        for i, (t, v) in enumerate(zip(texts, vectors))
    ]))
    return store, emb


# Feature: chatbot-apoyo-academico, Property 6: RAG retorna a lo sumo top-k chunks ordenados por similitud
@given(texts=st.lists(words, min_size=0, max_size=30), query=words.filter(lambda s: s.strip()),
       top_k=st.integers(min_value=1, max_value=20))
def test_property_6_top_k_sorted(texts, query, top_k):
    store, emb = _store_with(texts)
    result = asyncio.run(search_documents(query, top_k, store, emb))
    assert len(result) == min(top_k, len(texts))
    scores = [c.similarity_score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_empty_query_returns_nothing():
    store, emb = _store_with(["matrícula académica"])
    assert asyncio.run(search_documents("   ", 5, store, emb)) == []


course_st = st.builds(
    Course,
    course_code=st.text(alphabet="ABCDEFGHIJ0123456789", min_size=3, max_size=8),
    course_name=st.text(min_size=1, max_size=30),
    semester=st.integers(1, 10),
    status=st.sampled_from(["completed", "pending", "in_progress"]),
    grade=st.none() | st.floats(0, 5, allow_nan=False),
)


# Feature: chatbot-apoyo-academico, Property 8: Aislamiento de historial de cursos por sesión
@given(a=st.text(min_size=1, max_size=20).filter(str.strip), b=st.text(min_size=1, max_size=20).filter(str.strip),
       courses_a=st.lists(course_st, max_size=15, unique_by=lambda c: c.course_code),
       courses_b=st.lists(course_st, max_size=15, unique_by=lambda c: c.course_code))
def test_property_8_course_isolation(a, b, courses_a, courses_b):
    if a == b:
        return
    # Mismo código de curso en ambos estudiantes = registros distintos (otra sesión)
    store = InMemoryCourseStore({a: courses_a, b: courses_b})
    ra = asyncio.run(get_student_courses(a, store))
    rb = asyncio.run(get_student_courses(b, store))
    ids_a = {(ra.session_id, c.course_code) for c in ra.courses}
    ids_b = {(rb.session_id, c.course_code) for c in rb.courses}
    assert ids_a.isdisjoint(ids_b)
    assert sorted(c.course_code for c in ra.courses) == sorted(c.course_code for c in courses_a)
    assert ra.total == len(courses_a)
    assert ra.completed + ra.pending + ra.in_progress == ra.total


def test_progress_percentage():
    store = InMemoryCourseStore({"s": [
        Course(course_code="A", course_name="A", semester=1, status="completed"),
        Course(course_code="B", course_name="B", semester=2, status="pending"),
        Course(course_code="C", course_name="C", semester=2, status="in_progress"),
        Course(course_code="D", course_name="D", semester=1, status="completed"),
    ]})
    r = asyncio.run(get_student_courses("s", store))
    assert r.progress_percentage == 50.0
    assert [c.course_code for c in r.courses] == ["A", "D", "B", "C"]


def test_unknown_session_gets_empty_record():
    r = asyncio.run(get_student_courses("otra", InMemoryCourseStore({"s": []})))
    assert r.courses == [] and r.total == 0
