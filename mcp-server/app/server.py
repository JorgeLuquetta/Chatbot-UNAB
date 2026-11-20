"""Servidor FastMCP: expone las herramientas por MCP (/mcp) y por REST (/tools/*).

* /mcp          → protocolo MCP (streamable HTTP) para clientes MCP (p. ej. nodo
                  "MCP Client Tool" de n8n o cualquier agente).
* /tools/<name> → puente REST JSON con la misma lógica, usado por los nodos
                  HTTP Request de los workflows n8n (respuesta determinista y simple).
* /health       → health-check interno.

El servicio solo es alcanzable dentro de la red Docker "backend".
"""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import academic, mailer
from . import ingest as ingest_mod
from . import rag
from . import scraper as scraper_mod
from .config import settings
from .models import DocumentChunk, IngestionReport, ScraperReport, StudentCourseRecord
from .services import services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mcp-server")

mcp = FastMCP(
    "unab-chatbot-mcp",
    instructions="Herramientas del chatbot académico UNAB: búsqueda en documentos CCD (reglamento, plan de "
                 "estudios, requisitos), cursos del estudiante, plan académico (matrícula sugerida, estado "
                 "académico, proyección de grado y recomendaciones), calendario académico, noticias del día "
                 "(educación, tecnología, ingeniería de sistemas), ingesta de documentos y scraping de noticias.",
)


# ------------------------------------------------------------------ lógica compartida
async def _search(query: str, top_k: int = 5) -> list[DocumentChunk]:
    return await rag.search_documents(query, top_k, await services.document_store(), services.embedder())


async def _courses(session_id: str) -> StudentCourseRecord:
    return await rag.get_student_courses(session_id, await services.course_store())


async def _ingest(file_paths: list[str] | None = None) -> IngestionReport:
    paths = ingest_mod.resolve_paths(file_paths or [], settings.ccd_data_dir)
    return await ingest_mod.ingest_documents(
        paths, await services.document_store(), services.embedder(),
        max_tokens=settings.chunk_max_tokens, overlap=settings.chunk_overlap,
    )


async def _scrape(sources: list[str] | None = None) -> ScraperReport:
    if sources:
        configs = [scraper_mod.SourceConfig(url=u) for u in sources]
    else:
        configs = scraper_mod.load_sources(settings.sources_file)
    return await scraper_mod.run_news_scraper(
        configs, await services.news_store(), scraper_mod.make_http_fetcher(settings.http_timeout_s))


# ------------------------------------------------------------------ herramientas MCP
@mcp.tool
async def search_documents(query: str, top_k: int = 5) -> list[DocumentChunk]:
    """Genera el embedding del query y busca por similitud coseno en pgvector.
    Retorna los top_k chunks más similares con texto y score (orden descendente)."""
    return await _search(query, top_k)


@mcp.tool
async def get_student_courses(session_id: str) -> StudentCourseRecord:
    """Historial de cursos del estudiante asociado a session_id (aislamiento estricto)."""
    return await _courses(session_id)


@mcp.tool
async def ingest_documents(file_paths: list[str] | None = None) -> IngestionReport:
    """Ingesta de documentos CCD: chunking (CHUNK_MAX_TOKENS / CHUNK_OVERLAP; 220 / 30 en docker-compose)
    → embedding → pgvector.
    Sin argumentos procesa todos los archivos del directorio de datos."""
    return await _ingest(file_paths)


@mcp.tool
async def run_news_scraper(sources: list[str] | None = None) -> ScraperReport:
    """Scraping one-shot de fuentes UNAB con deduplicación por source_url."""
    return await _scrape(sources)


@mcp.tool
async def get_academic_plan(student_id: str = "", session_id: str = "") -> str:
    """Plan académico personalizado del estudiante (ID tipo U00000010, o session_id):
    estado académico (promedio ponderado, créditos, situación), matrícula sugerida para el
    próximo periodo según prerrequisitos y carga máxima, materias bloqueadas, proyección de
    grado (periodos restantes, periodo estimado) y recomendaciones para el éxito académico."""
    plan = await academic.academic_plan(student_id, session_id)
    if plan is None:
        raise ValueError("No existe un estudiante con ese ID")
    # Texto compacto para el LLM; el JSON completo está en /tools/get_academic_plan (REST)
    return academic.plan_summary(plan)


@mcp.tool
async def get_academic_calendar(upcoming_only: bool = True) -> list[dict[str, Any]]:
    """Calendario académico UNAB (matrículas, parciales, finales, inicio y fin de clases)."""
    return await academic.academic_calendar(upcoming_only)


@mcp.tool
async def get_news(category: str = "", limit: int = 5, today_only: bool = False) -> list[dict[str, Any]]:
    """Noticias recientes con fuente y fecha. category: educacion | tecnologia |
    ingenieria-sistemas | general (vacío = todas)."""
    return await academic.news(category, limit, today_only)


@mcp.tool
async def get_ccd_progress(student_id: str = "", session_id: str = "") -> str:
    """Cursos de competencias digitales (Centro de Competencias Digitales, CCD) del estudiante: prueba
    diagnóstica, cursos aprobados/en curso/pendientes y avance hacia la insignia de competencias digitales
    (requisito de grado). student_id tipo U00000010."""
    ccd = await academic.ccd_progress(student_id, session_id)
    if ccd is None:
        raise ValueError("No existe un estudiante con ese ID")
    return academic.ccd_summary(ccd)


# ------------------------------------------------------------------ puente REST
async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/tools/search_documents", methods=["POST"])
async def rest_search(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        chunks = await _search(str(body.get("query", "")), int(body.get("top_k", 5)))
    except (ValueError, ValidationError) as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("search_documents falló")
        return _error(503, "La base de conocimiento no está disponible")
    return JSONResponse({"chunks": [c.model_dump() for c in chunks]})


@mcp.custom_route("/tools/get_student_courses", methods=["POST"])
async def rest_courses(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        record = await _courses(str(body.get("session_id", "")))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("get_student_courses falló")
        return _error(503, "La base de datos de estudiantes no está disponible")
    return JSONResponse(record.model_dump(mode="json"))


@mcp.custom_route("/tools/ingest_documents", methods=["POST"])
async def rest_ingest(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        report = await _ingest(body.get("file_paths") or [])
    except ValueError as exc:
        return _error(400, str(exc))
    return JSONResponse(report.model_dump(mode="json"))


@mcp.custom_route("/tools/run_news_scraper", methods=["POST"])
async def rest_scrape(request: Request) -> JSONResponse:
    body = await _body(request)
    report = await _scrape(body.get("sources") or [])
    return JSONResponse(report.model_dump(mode="json"))


@mcp.custom_route("/tools/get_academic_plan", methods=["POST"])
async def rest_academic_plan(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        plan = await academic.academic_plan(str(body.get("student_id", "")), str(body.get("session_id", "")))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("get_academic_plan falló")
        return _error(503, "La base de datos de estudiantes no está disponible")
    if plan is None:
        return _error(404, "No existe un estudiante con ese ID")
    return JSONResponse(plan)


@mcp.custom_route("/tools/get_academic_calendar", methods=["POST"])
async def rest_calendar(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        events = await academic.academic_calendar(bool(body.get("upcoming_only", False)))
    except Exception:
        log.exception("get_academic_calendar falló")
        return _error(503, "El calendario no está disponible")
    return JSONResponse({"events": events})


@mcp.custom_route("/tools/get_news", methods=["POST"])
async def rest_news(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        items = await academic.news(str(body.get("category", "")), int(body.get("limit", 10)),
                                    bool(body.get("today_only", False)))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("get_news falló")
        return _error(503, "Las noticias no están disponibles")
    return JSONResponse({"news": items})


# ------------------------------------------------------------------ correo (solo puente REST: requiere confirmación
# del estudiante en el chat, por eso no se expone como herramienta autónoma del agente)
@mcp.custom_route("/tools/request_email", methods=["POST"])
async def rest_request_email(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        result = await mailer.request(str(body.get("session_id", "")), str(body.get("message", "")))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("request_email falló")
        return _error(503, "El servicio de correo no está disponible")
    return JSONResponse(result)


@mcp.custom_route("/tools/confirm_email", methods=["POST"])
async def rest_confirm_email(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        result = await mailer.confirm(str(body.get("session_id", "")), str(body.get("message", "")))
    except Exception:
        log.exception("confirm_email falló")
        return JSONResponse({"handled": False})   # si falla, el chat sigue normal
    return JSONResponse(result)


@mcp.custom_route("/tools/get_ccd_progress", methods=["POST"])
async def rest_ccd(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        ccd = await academic.ccd_progress(str(body.get("student_id", "")), str(body.get("session_id", "")))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        log.exception("get_ccd_progress falló")
        return _error(503, "La base de datos de estudiantes no está disponible")
    if ccd is None:
        return _error(404, "No existe un estudiante con ese ID")
    return JSONResponse({**ccd, "summary": academic.ccd_summary(ccd)})
