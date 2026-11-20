"""Graba el video de demostración del Chatbot UNAB con Playwright (subtítulos en pantalla).

En la VM, desde la carpeta del proyecto:
    docker run --rm --network host -u $(id -u):$(id -g) -e HOME=/tmp -v "$PWD:/w" -w /w --env-file .env \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        sh -c "pip install -q --user playwright==1.49.0 && python scripts/video_demo.py"
    # luego: scripts/video_editar.sh  (acelera las esperas del LLM y exporta MP4)

Guarda docs/video/crudo.webm y docs/video/tramos.json (tramos de espera que se aceleran al editar).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("docs/video")
BASE = os.getenv("DEMO_BASE", "traumado.top")          # dominio del túnel
SID = os.getenv("DEMO_STUDENT", "U00000010")
U = lambda sub: f"https://{sub}.{BASE}"                 # noqa: E731

CAPTION_JS = """
window.__cap = (t, sub) => {
  let d = document.getElementById('__cap');
  if (!d) {
    d = document.createElement('div'); d.id = '__cap';
    d.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;' +
      'max-width:86%;padding:14px 26px;border-radius:16px;background:rgba(28,22,52,.88);color:#fff;' +
      'font:700 22px/1.35 Nunito,Segoe UI,sans-serif;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.35);' +
      'pointer-events:none;transition:opacity .3s';
    document.documentElement.appendChild(d);
  }
  d.innerHTML = t + (sub ? '<div style="font-weight:600;font-size:16px;opacity:.85;margin-top:4px">' + sub + '</div>' : '');
  d.style.opacity = t ? '1' : '0';
};
"""

T0 = time.monotonic()
FAST: list[list[float]] = []        # tramos [inicio, fin] (s) que se aceleran al editar


def now() -> float:
    return time.monotonic() - T0


def cap(page, text: str, sub: str = "", wait: float = 0) -> None:
    page.evaluate("([t, s]) => window.__cap && window.__cap(t, s)", [text, sub])
    if wait:
        page.wait_for_timeout(int(wait * 1000))


def goto(page, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    page.evaluate(CAPTION_JS)


def slow_scroll(page, total: int = 1400, step: int = 120, pause: int = 260) -> None:
    for _ in range(total // step):
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause)


def ask(page, question: str, expect_js: str, sub: str = "", timeout_s: int = 300) -> None:
    """Escribe una pregunta en el chat web y espera la respuesta (la espera se acelera al editar)."""
    cap(page, f"💬 «{question}»", sub)
    page.click("#msg")
    page.keyboard.type(question, delay=45)
    page.wait_for_timeout(500)
    page.click("#send")
    start = now()
    cap(page, f"💬 «{question}»", "⏳ El modelo de IA corre en la CPU de la VM… (video acelerado)")
    page.wait_for_function(expect_js, timeout=timeout_s * 1000)
    FAST.append([start + 2, now() - 0.5])
    page.wait_for_timeout(600)
    page.evaluate("document.getElementById('log').scrollTop = 1e9")
    cap(page, f"💬 «{question}»", sub or "Respuesta del asistente", wait=6)


def bot_count_js(n: int) -> str:
    # El chat agrega la respuesta como un nuevo .msg.bot; espera a que haya más de n
    return f"document.querySelectorAll('#log .msg.bot:not(.typing)').length > {n}"


def bots(page) -> int:
    return page.evaluate("document.querySelectorAll('#log .msg.bot:not(.typing)').length")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, locale="es-CO",
                                  record_video_dir=str(OUT / "tmp"), record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()

        # 1. Portal
        goto(page, U("portal"))
        cap(page, "Chatbot de apoyo académico UNAB", "Ciencia de Datos · Ingeniería de Sistemas · n8n + RAG + MCP", wait=4)
        cap(page, "Portal: todas las herramientas en un solo lugar", "portal.traumado.top", wait=4)
        slow_scroll(page, 900)
        cap(page, "API: webhooks de n8n y estudiantes de prueba (datos sintéticos)", wait=3)

        # 2. Plan académico
        goto(page, U("portal") + f"/plan?id={SID}")
        page.wait_for_selector(".cards", timeout=30000)
        cap(page, "Plan académico de Camila (U00000010)", "Estado académico, proyección y matrícula calculados en PostgreSQL", wait=5)
        slow_scroll(page, 700)
        cap(page, "Alertas de requisitos y avance en Competencias Digitales (CCD)", "Insignia de competencias digitales: requisito de grado", wait=5)
        slow_scroll(page, 900)
        cap(page, "Recomendaciones personalizadas (educación de precisión)", wait=4)

        # 3. Noticias
        goto(page, U("portal") + "/noticias")
        page.wait_for_selector(".news", timeout=30000)
        page.wait_for_timeout(2500)
        cap(page, "Noticias de la UNAB con imagen, fuente y fecha", "Scraper automático cada 6 horas (workflow de n8n)", wait=4)
        page.click("text=Tecnología")
        page.wait_for_timeout(2500)
        cap(page, "Filtro por categoría: tecnología, ingeniería de sistemas, educación", wait=3)

        # 4. Chat web
        goto(page, U("chatbotia"))
        cap(page, "Chat web del asistente", "chatbotia.traumado.top", wait=3)
        page.click("#msg")
        page.keyboard.type(SID, delay=80)
        page.click("#send")
        page.wait_for_function(bot_count_js(1), timeout=60000)
        cap(page, "El estudiante entra con su ID", "El sistema lo reconoce desde la base de datos", wait=4)
        ask(page, "¿Qué materias debo matricular el próximo semestre?", bot_count_js(bots(page)),
            "Matrícula sugerida: prerrequisitos, materias por repetir y carga máxima")
        ask(page, "¿Qué es la insignia de competencias digitales?", bot_count_js(bots(page)),
            "RAG: búsqueda vectorial en los documentos del CCD (pgvector)")
        ask(page, "¿Qué cursos de competencias digitales he tomado?", bot_count_js(bots(page)),
            "Historial personalizado del CCD (base de datos sintética)")
        ask(page, "¿Cuánto es 25+17?", bot_count_js(bots(page)),
            "Guardrails: solo consultas universitarias informativas")
        ask(page, "Envíame mi informe de avance al correo", bot_count_js(bots(page)),
            "Envío por correo: primero confirma el correo registrado")
        ask(page, "sí", bot_count_js(bots(page)), "Confirmado: el informe se envía")

        # 5. Bandeja de correo
        goto(page, U("portal") + "/correo/")
        page.wait_for_timeout(3000)
        cap(page, "El informe llegó a la bandeja de prueba", "unab.u00000010@yopmail.com", wait=3)
        try:
            page.locator("a.message, .message-list a, a[href*='view']").first.click(timeout=5000)
            page.wait_for_timeout(3000)
            cap(page, "Informe de avance: estado, matrícula, proyección, recomendaciones y alertas", wait=5)
        except Exception:
            page.wait_for_timeout(3000)

        # 6. n8n
        goto(page, U("n8n") + "/signin")
        page.fill("input[type=email]", os.environ["N8N_OWNER_EMAIL"])
        page.fill("input[type=password]", os.environ["N8N_OWNER_PASSWORD"])
        page.keyboard.press("Enter")
        page.wait_for_url("**/home/**", timeout=30000)
        page.evaluate(CAPTION_JS)
        page.wait_for_timeout(2500)
        cap(page, "n8n: 12 workflows activos", "Chat, agente IA, plan académico, noticias, scraper, ingesta…", wait=4)
        for wf_id, text, sub in [
            ("unabChatRouting1", "Workflow de chat: ruteo por intención", "Guardrails → intención → MCP / RAG / BD → LLM → guardrails → memoria"),
            ("unabAgentMcp0001", "Agente IA con herramientas MCP", "AI Agent + Ollama + memoria PostgreSQL + MCP Client Tool"),
            ("unabIngestDocs01", "Ingesta del RAG en n8n", "Chunking de 220 tokens, overlap 30, embeddings granite → pgvector"),
        ]:
            page.goto(U("n8n") + f"/workflow/{wf_id}")
            page.wait_for_selector(".vue-flow__node", timeout=30000)
            page.evaluate(CAPTION_JS)
            page.wait_for_timeout(1500)
            page.keyboard.press("Shift+1")
            cap(page, text, sub, wait=5)
        page.goto(U("n8n") + "/home/executions")
        page.evaluate(CAPTION_JS)
        page.wait_for_timeout(2500)
        cap(page, "Ejecuciones registradas de cada conversación", wait=4)

        # 7. App móvil
        goto(page, U("qrapp"))
        page.wait_for_timeout(2500)
        cap(page, "App móvil Android (Expo Go)", "Escanea el QR: chat, Mi plan, Mi ruta, Noticias y Calendario", wait=5)
        cap(page, "Repositorio y documentación: github.com/JorgeLuquetta/Chatbot-UNAB", "Gracias", wait=4)

        video_path = page.video.path()
        ctx.close()
        browser.close()
    shutil.move(video_path, OUT / "crudo.webm")
    shutil.rmtree(OUT / "tmp", ignore_errors=True)
    (OUT / "tramos.json").write_text(json.dumps({"fast": FAST, "total": now()}, indent=2), encoding="utf-8")
    print("video crudo:", OUT / "crudo.webm", "tramos acelerados:", len(FAST))


if __name__ == "__main__":
    main()
