"""Consultas académicas para las herramientas MCP: plan académico (matrícula, estado,
proyección y recomendaciones), calendario y noticias filtradas por categoría.

La lógica pesada vive en SQL (db/academico.sql → academic_plan), así la misma regla la
usan n8n, el servidor MCP y cualquier otro cliente.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .db import get_pool

NEWS_CATEGORIES = ("educacion", "tecnologia", "ingenieria-sistemas", "general")
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _clean(value: str | None) -> str:
    v = (value or "").strip()
    if v and not _ID_RE.match(v):
        raise ValueError("Identificador inválido")
    return v


async def resolve_session(student_id: str | None = None, session_id: str | None = None) -> str | None:
    """Devuelve el session_id a partir del ID del estudiante (U00000010) o del session_id."""
    sid, sess = _clean(student_id).upper(), _clean(session_id)
    if not sid and not sess:
        raise ValueError("Indica student_id o session_id")
    pool = await get_pool()
    if sess:
        return await pool.fetchval("SELECT session_id FROM student_sessions WHERE session_id = $1", sess)
    return await pool.fetchval("SELECT session_id FROM session_by_student($1)", sid)


async def academic_plan(student_id: str | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    sess = await resolve_session(student_id, session_id)
    if not sess:
        return None
    pool = await get_pool()
    raw = await pool.fetchval("SELECT academic_plan($1)::text", sess)
    if not raw:
        return None
    plan = json.loads(raw)
    # Alertas de requisitos pendientes y avance en el CCD (db/ccd.sql); si no existen, el plan sigue igual
    try:
        plan["alerts"] = json.loads(await pool.fetchval("SELECT student_alerts($1)::text", sess) or "[]")
        plan["ccd"] = json.loads(await pool.fetchval("SELECT ccd_progress($1)::text", sess) or "null")
    except Exception:
        plan.setdefault("alerts", [])
    return plan


async def ccd_progress(student_id: str | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    """Cursos del Centro de Competencias Digitales, prueba diagnóstica y avance hacia la insignia."""
    sess = await resolve_session(student_id, session_id)
    if not sess:
        return None
    pool = await get_pool()
    raw = await pool.fetchval("SELECT ccd_progress($1)::text", sess)
    return json.loads(raw) if raw else None


CCD_STATUS = {"completed": "aprobado", "homologated": "homologado por la prueba diagnóstica",
              "in_progress": "en curso", "failed": "reprobado (repetir)", "pending": "pendiente"}


def ccd_summary(ccd: dict[str, Any]) -> str:
    """Texto del avance CCD para el LLM (chat y agente)."""
    b, d = ccd.get("badge", {}), ccd.get("diagnostic") or {}
    lines = [
        f"CENTRO DE COMPETENCIAS DIGITALES (CCD) — estudiante {ccd.get('student_id')}:",
        f"Prueba diagnóstica: {d.get('score', 'no presentada')} puntos, nivel {d.get('level', '-')}.",
        f"Insignia de competencias digitales: {'OBTENIDA' if b.get('earned') else 'pendiente'}; "
        f"{b.get('required_done')} de {b.get('required_total')} cursos obligatorios y {b.get('electives_done')} electivo(s) aprobados.",
    ]
    # Agrupados por estado: un LLM pequeño no confunde "tomados" con "pendientes"
    groups = [("YA TOMADOS (aprobados u homologados)", ("completed", "homologated")), ("EN CURSO", ("in_progress",)),
              ("REPROBADOS (debe repetirlos)", ("failed",)), ("PENDIENTES (NO los ha tomado)", ("pending",))]
    for label, statuses in groups:
        items = [c for c in ccd.get("courses", []) if c["status"] in statuses]
        if not items:
            continue
        lines.append(f"{label}:")
        for c in items:
            extra = " — homologado por la prueba diagnóstica" if c["status"] == "homologated" else (
                f" — nota {c['grade']}" if c.get("grade") is not None else "")
            lines.append(f"- {c['course_code']} {c['course_name']} ({'obligatorio' if c['required'] else 'electivo'}){extra}")
    if b.get("next"):
        lines.append(f"Siguiente curso recomendado: {b['next']}.")
    if ccd.get("enrollment_info"):
        lines.append(f"Inscripción: {ccd['enrollment_info']}")
    return "\n".join(lines)


async def academic_calendar(upcoming_only: bool = False, limit: int = 30) -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT event_name, to_char(event_date, 'YYYY-MM-DD') AS event_date, description "
        "FROM academic_calendar WHERE NOT $1 OR event_date >= (now() AT TIME ZONE 'America/Bogota')::date "
        "ORDER BY event_date LIMIT $2", upcoming_only, max(1, min(int(limit), 100)))
    return [dict(r) for r in rows]


async def news(category: str | None = None, limit: int = 10, today_only: bool = False) -> list[dict[str, Any]]:
    cat = (category or "").strip().lower()
    if cat and cat not in NEWS_CATEGORIES:
        raise ValueError(f"Categoría inválida. Usa una de: {', '.join(NEWS_CATEGORIES)}")
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT title, summary, source_url, source_name, category, image_url, "
        "to_char(published_at AT TIME ZONE 'America/Bogota', 'YYYY-MM-DD') AS published_at "
        "FROM noticias WHERE ($1 = '' OR category = $1) "
        "AND (NOT $2 OR (published_at AT TIME ZONE 'America/Bogota')::date = (now() AT TIME ZONE 'America/Bogota')::date) "
        "ORDER BY published_at DESC LIMIT $3", cat, today_only, max(1, min(int(limit), 50)))
    return [dict(r) for r in rows]


def plan_summary(plan: dict[str, Any]) -> str:
    """Resumen en texto del plan académico (para agentes LLM: corto y sin ambigüedades)."""
    s, st = plan.get("student", {}), plan.get("status", {})
    en, pr = plan.get("enrollment", {}), plan.get("projection", {})
    lines = [
        f"Estudiante: {s.get('full_name')} ({s.get('student_id')}), {s.get('program')}, semestre {s.get('current_semester')}.",
        f"ESTADO ACADÉMICO: promedio ponderado {st.get('gpa') if st.get('gpa') is not None else 'sin notas'}; "
        f"situación: {st.get('standing')}; créditos aprobados {st.get('approved_credits')} de {st.get('total_credits')} "
        f"({st.get('progress_percentage')} %); materias reprobadas pendientes: {st.get('failed_courses')}.",
        "En curso este periodo: " + (", ".join(c["course_name"] for c in st.get("in_progress", [])) or "ninguna") + ".",
        f"MATRÍCULA SUGERIDA {en.get('term')} ({en.get('credits')} créditos de un máximo de {en.get('max_credits')}):",
    ]
    for c in en.get("courses", []):
        extra = []
        if c.get("repeat"):
            extra.append("la reprobó, debe repetirla")
        if c.get("conditional"):
            extra.append("condicionada a aprobar " + " y ".join(x["course_name"] for x in c.get("conditional_on", [])))
        lines.append(f"- {c['course_code']} {c['course_name']}, {c['credits']} créditos" + (f" ({'; '.join(extra)})" if extra else ""))
    if not en.get("courses"):
        lines.append("- No hay materias disponibles para matricular.")
    blocked = en.get("blocked", [])[:3]
    if blocked:
        lines.append("Bloqueadas por prerrequisitos: " + "; ".join(
            f"{b['course_name']} (falta {', '.join(m['course_name'] for m in b['missing_prerequisites'])})" for b in blocked) + ".")
    lines.append(f"PROYECCIÓN: faltan {pr.get('remaining_credits')} créditos y {pr.get('terms_remaining')} periodos; "
                 f"grado estimado en el periodo {pr.get('estimated_graduation_term')}; "
                 f"{'va al día' if pr.get('on_track') else 'tiene atrasos'}.")
    lines.append("RECOMENDACIONES:")
    lines += [f"- {r['text']}" for r in plan.get("recommendations", [])]
    if plan.get("alerts"):
        lines.append("ALERTAS DE REQUISITOS PENDIENTES:")
        lines += [f"- [{a['level']}] {a['text']}" for a in plan["alerts"]]
    return "\n".join(lines)
