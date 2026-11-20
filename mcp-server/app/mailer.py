"""Envío por correo de noticias, informes de avance e informes de materias.

Flujo en dos pasos (lo orquesta el workflow de chat de n8n):
  1. request(session_id, mensaje)  → detecta QUÉ enviar (solo 3 tipos permitidos), deja la solicitud
     'pending' y responde con el correo registrado del estudiante para que lo confirme o lo cambie.
  2. confirm(session_id, mensaje)  → "sí" envía, un correo nuevo lo actualiza y envía, "no" cancela.
     Si el mensaje no responde a la solicitud, devuelve handled=False y el chat sigue normal.

SMTP configurable (Brevo, Gmail, ...). Sin SMTP_HOST externo se usa Mailpit (bandeja local de prueba).
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import mimetypes
import os
import re
import smtplib
import unicodedata
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Any

from .db import get_pool

log = logging.getLogger("mailer")

KINDS = {"noticias": "las noticias", "avance": "tu informe de avance", "materias": "tu informe de materias"}
ONLY_KINDS = ("Solo puedo enviar por correo: **noticias**, tu **informe de avance** (estado académico, matrícula "
              "sugerida y proyección) o tu **informe de materias**. Por ejemplo: *envíame mi informe de avance al correo*.")
PENDING_MINUTES = 15
MAX_SENT_PER_HOUR = 5
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}\b")
YES_RE = re.compile(r"^\s*(si|sip|claro|correcto|dale|ok|okay|confirmo|confirmar|envialo|enviala|envia|mandalo|"
                    r"de acuerdo|listo|adelante|hazlo|perfecto|ese|ese mismo|esta bien)\b")
NO_RE = re.compile(r"^\s*(no|cancela|cancelar|cancelalo|olvidalo|mejor no|ya no|detente)\b")
MAX_IMAGE_BYTES = 1_500_000


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def detect_kind(message: str) -> str | None:
    t = _norm(message)
    if re.search(r"\b(noticias?|novedades)\b", t):
        return "noticias"
    if re.search(r"\b(avance|progreso|estado academico|plan academico|proyeccion|matricula|promedio|situacion academica)\b", t):
        return "avance"
    if re.search(r"\b(materias|cursos|asignaturas|notas|calificaciones|historial|ruta academica)\b", t):
        return "materias"
    return None


def news_category(message: str) -> str:
    t = _norm(message)
    if re.search(r"\b(ingenieria de sistemas|software|programacion|sistemas)\b", t):
        return "ingenieria-sistemas"
    if re.search(r"\b(tecnolog\w*|inteligencia artificial|ia|digital|innovacion|ingenieria\w*)\b", t):
        return "tecnologia"
    if re.search(r"\b(educacion|educativ\w*|becas?|cursos?|diplomados?|posgrados?)\b", t):
        return "educacion"
    return ""


_STOP = set("""envia enviame enviar enviarme manda mandame mandar reenvia correo email mail noticia noticias novedades
sobre acerca del de la las los una unos unas que por para con mis mi al el en hoy dia ultima ultimas reciente
recientes tecnologia educacion ingenieria sistemas favor porfa porfavor gracias quiero puedes podrias""".split())


def news_keywords(message: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{5,}", _norm(message)) if w not in _STOP][:4]


# ------------------------------------------------------------------ SMTP
def smtp_settings() -> dict[str, Any]:
    host = os.getenv("SMTP_HOST", "mailpit")
    port = int(os.getenv("SMTP_PORT", "1025"))
    starttls = os.getenv("SMTP_STARTTLS", "").lower() in ("1", "true", "yes") or port == 587
    return {"host": host, "port": port, "user": os.getenv("SMTP_USER", ""), "password": os.getenv("SMTP_PASSWORD", ""),
            "from": os.getenv("SMTP_FROM", "Asistente UNAB <asistente@chatbot-unab.local>"), "starttls": starttls,
            "is_test_inbox": host in ("mailpit", "localhost", "127.0.0.1")}


def _smtp_send(msg: EmailMessage, cfg: dict[str, Any]) -> None:
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
        if cfg["starttls"]:
            s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


async def _download_image(url: str) -> tuple[bytes, str, str] | None:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (UNAB-Chatbot)"}) as c:
            r = await c.get(url)
            ctype = r.headers.get("content-type", "").split(";")[0].strip()
            if r.status_code != 200 or not ctype.startswith("image/") or len(r.content) > MAX_IMAGE_BYTES:
                return None
            ext = mimetypes.guess_extension(ctype) or ".jpg"
            return r.content, ctype, ext
    except Exception as exc:
        log.info("No se pudo descargar la imagen %s: %s", url, exc)
        return None


# ------------------------------------------------------------------ contenido de los correos
STYLE = ("font-family:Segoe UI,Arial,sans-serif;color:#1C2A48;max-width:640px;margin:auto")
e = html.escape


def _shell(title: str, name: str, body: str) -> str:
    return (f'<div style="{STYLE}"><div style="background:#1C2A48;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
            f'<div style="color:#F5A800;font-weight:700;font-size:13px">ASISTENTE ACADÉMICO UNAB</div>'
            f'<div style="font-size:22px;font-weight:800">{e(title)}</div></div>'
            f'<div style="border:1px solid #E2E5EE;border-top:0;padding:18px 22px;border-radius:0 0 12px 12px">'
            f'<p>Hola, {e(name)}:</p>{body}'
            f'<p style="color:#5B6478;font-size:12px;margin-top:24px">Enviado a solicitud tuya desde el chat. '
            f'Datos sintéticos del proyecto de Ciencia de Datos UNAB.</p></div></div>')


async def build_news(student: dict, query: str) -> tuple[str, str, list[tuple[bytes, str, str]]]:
    pool = await get_pool()
    cat, words = news_category(query), news_keywords(query)
    rows = []
    if words:
        rows = await pool.fetch(
            "SELECT title, summary, source_url, source_name, category, image_url, published_at FROM noticias "
            "WHERE ($1 = '' OR category = $1) AND (" + " OR ".join(f"title ILIKE ${i + 2}" for i in range(len(words))) +
            ") ORDER BY published_at DESC LIMIT 5", cat, *[f"%{w}%" for w in words])
    if not rows:
        rows = await pool.fetch(
            "SELECT title, summary, source_url, source_name, category, image_url, published_at FROM noticias "
            "WHERE ($1 = '' OR category = $1) ORDER BY (image_url IS NOT NULL) DESC, published_at DESC LIMIT 5", cat)
    rows = sorted(rows, key=lambda r: r["published_at"], reverse=True)
    images, cards = [], []
    for i, n in enumerate(rows, 1):
        img = await _download_image(n["image_url"]) if n["image_url"] else None
        if img:
            images.append((img[0], img[1], f"noticia-{i}{img[2]}"))
        pic = (f'<img src="{e(n["image_url"])}" alt="" style="width:100%;max-height:240px;object-fit:cover;'
               f'border-radius:8px">' if n["image_url"] else "")
        cards.append(
            f'<div style="border:1px solid #E2E5EE;border-radius:10px;padding:12px;margin:12px 0">{pic}'
            f'<div style="font-size:12px;color:#8A00E6;font-weight:700;margin-top:8px">{e(n["category"])} · '
            f'{e(n["source_name"])} · {n["published_at"]:%Y-%m-%d}</div>'
            f'<div style="font-size:16px;font-weight:700;margin:4px 0">{e(n["title"])}</div>'
            f'<div style="font-size:14px;color:#5B6478">{e((n["summary"] or "")[:300])}</div>'
            f'<a href="{e(n["source_url"])}" style="color:#8A00E6;font-size:13px">Leer la noticia</a></div>')
    label = {"ingenieria-sistemas": "de ingeniería de sistemas", "tecnologia": "de tecnología",
             "educacion": "de educación"}.get(cat, "recientes")
    body = (f"<p>Estas son las noticias {label} que pediste"
            f"{' (las imágenes van adjuntas)' if images else ''}:</p>" + ("".join(cards) or "<p>No hay noticias.</p>"))
    return f"Noticias {label} · Asistente UNAB", _shell(f"Noticias {label}", student["full_name"], body), images


async def build_progress(student: dict, session_id: str) -> tuple[str, str, list]:
    pool = await get_pool()
    plan = json.loads(await pool.fetchval("SELECT academic_plan($1)::text", session_id))
    st, en, pr = plan["status"], plan["enrollment"], plan["projection"]
    courses = "".join(
        f"<tr><td>{e(c['course_code'])}</td><td>{e(c['course_name'])}</td><td>{c['credits']}</td>"
        f"<td>{'Repetir (reprobada)' if c['repeat'] else ''}"
        f"{'Si apruebas ' + e(' y '.join(x['course_name'] for x in c['conditional_on'])) if c['conditional'] else ''}</td></tr>"
        for c in en["courses"])
    recs = "".join(f"<li>{e(r['text'])}</li>" for r in plan["recommendations"])
    td = 'style="padding:6px 8px;border-bottom:1px solid #E2E5EE"'
    body = (
        f"<h3>Estado académico</h3><table style='border-collapse:collapse'>"
        f"<tr><td {td}>Programa</td><td {td}><b>{e(plan['student']['program'])}</b> · semestre {plan['student']['current_semester']}</td></tr>"
        f"<tr><td {td}>Promedio ponderado</td><td {td}><b>{st['gpa'] if st['gpa'] is not None else 'sin notas'}</b></td></tr>"
        f"<tr><td {td}>Situación</td><td {td}><b>{e(st['standing'])}</b></td></tr>"
        f"<tr><td {td}>Créditos aprobados</td><td {td}>{st['approved_credits']} de {st['total_credits']} ({st['progress_percentage']} %)</td></tr>"
        f"<tr><td {td}>Materias reprobadas por repetir</td><td {td}>{st['failed_courses']}</td></tr></table>"
        f"<h3>Matrícula sugerida {e(en['term'])} ({en['credits']} de {en['max_credits']} créditos)</h3>"
        f"<table style='border-collapse:collapse;width:100%;font-size:14px'><tr style='background:#F6F7FB'>"
        f"<th align=left>Código</th><th align=left>Materia</th><th>Créd.</th><th align=left>Nota</th></tr>{courses}</table>"
        f"<h3>Proyección de grado</h3><p>Faltan <b>{pr['remaining_credits']} créditos</b> y <b>{pr['terms_remaining']} periodos</b>. "
        f"Periodo estimado de grado: <b>{e(pr['estimated_graduation_term'])}</b> "
        f"({'vas al día' if pr['on_track'] else 'tienes atrasos'}).</p>"
        f"<h3>Recomendaciones</h3><ul>{recs}</ul>")
    return "Informe de avance académico · Asistente UNAB", _shell("Informe de avance académico", student["full_name"], body), []


async def build_courses(student: dict, session_id: str) -> tuple[str, str, list]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT sc.semester, sc.course_code, sc.course_name, sc.status, sc.grade, COALESCE(pc.credits, 3) AS credits "
        "FROM student_courses sc LEFT JOIN program_courses pc ON pc.course_code = sc.course_code "
        "WHERE sc.student_session = $1 ORDER BY sc.semester, sc.course_code", session_id)
    label = {"completed": "Aprobada", "in_progress": "En curso", "pending": "Pendiente"}
    parts, sem = [], None
    for r in rows:
        if r["semester"] != sem:
            sem = r["semester"]
            parts.append(f"<tr><td colspan=4 style='padding-top:12px;color:#8A00E6;font-weight:800'>Semestre {sem}</td></tr>")
        st = "Reprobada (repetir)" if r["status"] == "pending" and r["grade"] is not None else label.get(r["status"], r["status"])
        grade = "" if r["grade"] is None else f"{float(r['grade']):.1f}"
        parts.append(f"<tr><td>{e(r['course_code'])}</td><td>{e(r['course_name'])}</td><td>{st}</td>"
                     f"<td align=right>{grade}</td></tr>")
    done = sum(1 for r in rows if r["status"] == "completed")
    body = (f"<p>Tu historial: <b>{done}</b> aprobadas de <b>{len(rows)}</b> materias del plan.</p>"
            f"<table style='border-collapse:collapse;width:100%;font-size:14px'><tr style='background:#F6F7FB'>"
            f"<th align=left>Código</th><th align=left>Materia</th><th align=left>Estado</th><th align=right>Nota</th></tr>"
            + "".join(parts) + "</table>")
    return "Informe de materias · Asistente UNAB", _shell("Informe de materias", student["full_name"], body), []


# ------------------------------------------------------------------ flujo
async def _student(session_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT s.student_id, s.full_name, s.email FROM student_sessions ss JOIN students s ON s.student_id = ss.student_id "
        "WHERE ss.session_id = $1", session_id)
    return dict(row) if row else None


def _inbox_hint(email_to: str, cfg: dict) -> str:
    if cfg["is_test_inbox"]:
        return " Está en la bandeja de prueba del portal: https://portal.traumado.top/correo/"
    local, _, domain = email_to.partition("@")
    return f" Revísalo en https://yopmail.com/es/?login={local}" if domain.lower() == "yopmail.com" else ""


async def request(session_id: str, message: str) -> dict[str, Any]:
    student = await _student(session_id)
    if not student:
        raise ValueError("Estudiante no encontrado")
    kind = detect_kind(message)
    if kind is None:
        return {"status": "unsupported", "reply": ONLY_KINDS}
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("UPDATE email_requests SET status = 'cancelled' WHERE session_id = $1 AND status = 'pending'", session_id)
        await conn.execute("INSERT INTO email_requests (session_id, student_id, kind, query) VALUES ($1, $2, $3, $4)",
                           session_id, student["student_id"], kind, message[:500])
    email = student["email"] or "(sin correo registrado)"
    return {"status": "pending", "kind": kind, "email": student["email"],
            "reply": (f"Te envío {KINDS[kind]} a **{email}**. ¿Es correcto?\n\n"
                      "• Responde **sí** para enviarlo.\n• Escribe **otro correo** para actualizarlo y enviarlo ahí.\n"
                      "• Responde **no** para cancelar.")}


async def confirm(session_id: str, message: str) -> dict[str, Any]:
    pool = await get_pool()
    req = await pool.fetchrow(
        "SELECT * FROM email_requests WHERE session_id = $1 AND status = 'pending' "
        f"AND created_at > now() - interval '{PENDING_MINUTES} minutes' ORDER BY created_at DESC LIMIT 1", session_id)
    if req is None:
        return {"handled": False}
    text = _norm(message)
    new_email = EMAIL_RE.search(message or "")
    if NO_RE.search(text) and not new_email:
        await pool.execute("UPDATE email_requests SET status = 'cancelled' WHERE id = $1", req["id"])
        return {"handled": True, "reply": "Listo, cancelé el envío. ¿Te ayudo con algo más?"}
    if not new_email and not YES_RE.search(text):
        # El estudiante cambió de tema: se cancela la solicitud y el chat sigue normal
        await pool.execute("UPDATE email_requests SET status = 'cancelled' WHERE id = $1", req["id"])
        return {"handled": False}
    student = await _student(session_id)
    if new_email:
        addr = new_email.group(0).lower()
        await pool.execute("UPDATE students SET email = $1 WHERE student_id = $2", addr, student["student_id"])
        student["email"] = addr
    if not student["email"]:
        return {"handled": True, "reply": "No tienes correo registrado. Escríbeme tu correo para enviarte la información."}
    sent_last_hour = await pool.fetchval(
        "SELECT count(*) FROM email_requests WHERE session_id = $1 AND status = 'sent' AND sent_at > now() - interval '1 hour'",
        session_id)
    if sent_last_hour >= MAX_SENT_PER_HOUR:
        await pool.execute("UPDATE email_requests SET status = 'cancelled', error = 'limite' WHERE id = $1", req["id"])
        return {"handled": True, "reply": f"Ya te envié {MAX_SENT_PER_HOUR} correos en la última hora. Intenta más tarde."}

    cfg = smtp_settings()
    try:
        if req["kind"] == "noticias":
            subject, body, images = await build_news(student, req["query"])
        elif req["kind"] == "avance":
            subject, body, images = await build_progress(student, session_id)
        else:
            subject, body, images = await build_courses(student, session_id)
        msg = EmailMessage()
        name, addr = parseaddr(cfg["from"])
        msg["From"] = formataddr((name or "Asistente UNAB", addr))
        msg["To"] = student["email"]
        msg["Subject"] = subject
        msg.set_content("Abre este correo en un cliente que muestre HTML.")
        msg.add_alternative(body, subtype="html")
        for data, ctype, filename in images:
            maintype, subtype = ctype.split("/", 1)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        await asyncio.to_thread(_smtp_send, msg, cfg)
    except Exception as exc:
        log.exception("Envío de correo falló")
        await pool.execute("UPDATE email_requests SET status = 'failed', error = $2, email_to = $3 WHERE id = $1",
                           req["id"], str(exc)[:500], student["email"])
        return {"handled": True, "reply": "No pude enviar el correo en este momento. Intenta de nuevo más tarde."}
    await pool.execute("UPDATE email_requests SET status = 'sent', sent_at = now(), email_to = $2 WHERE id = $1",
                       req["id"], student["email"])
    extra = f" con {len(images)} imagen(es) adjunta(s)" if images else ""
    updated = " (actualicé tu correo)" if new_email else ""
    return {"handled": True, "sent": True,
            "reply": f"✅ Listo, envié {KINDS[req['kind']]}{extra} a **{student['email']}**{updated}."
                     + _inbox_hint(student["email"], cfg)}
