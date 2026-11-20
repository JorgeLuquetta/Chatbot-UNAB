"""Tests del servidor HTTP (REST bridge + MCP) con dependencias en memoria."""
import asyncio

import pytest
from starlette.testclient import TestClient

from app.embeddings import HashEmbedder
from app.models import ChunkRecord, Course
from app.services import services
from app.stores import InMemoryCourseStore, InMemoryDocumentStore


@pytest.fixture
def client():
    emb = HashEmbedder(dim=32)
    docs = InMemoryDocumentStore()
    texts = ["requisitos de grado ingeniería de sistemas", "calendario de matrícula", "créditos por semestre"]
    vecs = asyncio.run(emb.embed(texts))
    asyncio.run(docs.upsert_chunks([ChunkRecord(document_name="ccd.pdf", chunk_index=i, total_chunks=3,
                                                content=t, embedding=v) for i, (t, v) in enumerate(zip(texts, vecs))]))
    courses = InMemoryCourseStore({"sess_a": [Course(course_code="ISC601", course_name="Ciencia de Datos",
                                                     semester=6, status="in_progress")]})
    services.override(embedder=emb, documents=docs, courses=courses)
    from main import app
    with TestClient(app, base_url="http://mcp-server:8000") as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_rest_search(client):
    r = client.post("/tools/search_documents", json={"query": "requisitos de grado", "top_k": 2})
    assert r.status_code == 200
    chunks = r.json()["chunks"]
    assert len(chunks) == 2
    assert chunks[0]["text"] == "requisitos de grado ingeniería de sistemas"


def test_rest_courses(client):
    r = client.post("/tools/get_student_courses", json={"session_id": "sess_a"})
    assert r.status_code == 200 and r.json()["courses"][0]["course_code"] == "ISC601"
    assert client.post("/tools/get_student_courses", json={}).status_code == 400


def test_mcp_tools_listed():
    from fastmcp import Client

    from app.server import mcp

    async def go():
        async with Client(mcp) as c:
            tools = {t.name for t in await c.list_tools()}
            result = await c.call_tool("get_student_courses", {"session_id": "sess_a"})
            return tools, result

    tools, result = asyncio.run(go())
    assert tools == {"search_documents", "get_student_courses", "ingest_documents", "run_news_scraper",
                     "get_academic_plan", "get_academic_calendar", "get_news", "get_ccd_progress"}
    assert result.data is not None
