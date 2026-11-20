"""Toma las capturas del README (docs/img/) con Playwright: chat web, página de QR y workflows de n8n.

En la VM, desde la carpeta del proyecto (usa la imagen oficial de Playwright, no instala nada en el host):
    docker run --rm --network host -v "$PWD:/w" -w /w --env-file .env \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        sh -c "pip install -q playwright==1.49.0 && python scripts/capturas.py"
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("docs/img")
HOST = os.getenv("CAPTURE_HOST", "localhost")
SID = os.getenv("CAPTURE_STUDENT", "U00000010")
QUESTION = "¿Qué materias debo matricular el próximo semestre?"


def chat_web(page):
    page.goto(f"http://{HOST}:9001/")
    page.wait_for_load_state("networkidle")
    page.fill("#msg", SID)
    page.click("#send")
    page.wait_for_selector("#who:not([hidden])", timeout=60000)   # el chat ya reconoció al estudiante
    page.wait_for_timeout(1500)
    page.fill("#msg", QUESTION)
    page.click("#send")
    # Espera la respuesta del LLM (CPU: hasta 3 min): el último mensaje deja de ser el indicador de "escribiendo"
    page.wait_for_function(
        "(() => { const t = document.querySelector('#log').innerText; return t.includes('Microeconom') || t.includes('Mercadeo'); })()",
        timeout=300000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "chat_web.png"), full_page=True)


def portal(page):
    page.goto(f"http://{HOST}:9003/")
    page.wait_for_timeout(2500)
    page.screenshot(path=str(OUT / "portal.png"), full_page=True)
    page.goto(f"http://{HOST}:9003/noticias")
    page.wait_for_selector(".news", timeout=30000)
    page.wait_for_timeout(4000)  # imágenes
    page.screenshot(path=str(OUT / "noticias.png"))
    page.goto(f"http://{HOST}:9003/plan?id={SID}")
    page.wait_for_selector(".cards", timeout=30000)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "plan.png"), full_page=True)


def qr(page):
    page.goto(f"http://{HOST}:9002/")
    page.wait_for_timeout(4000)
    page.screenshot(path=str(OUT / "qr.png"), full_page=True)


def n8n(page):
    page.goto(f"http://{HOST}:9000/signin")
    page.fill("input[type=email]", os.environ["N8N_OWNER_EMAIL"])
    page.fill("input[type=password]", os.environ["N8N_OWNER_PASSWORD"])
    page.keyboard.press("Enter")
    page.wait_for_url("**/home/**", timeout=30000)
    for wf_id, name in [("unabChatRouting1", "n8n_chat"), ("unabAgentMcp0001", "n8n_agente")]:
        page.goto(f"http://{HOST}:9000/workflow/{wf_id}")
        page.wait_for_selector(".vue-flow__node", timeout=30000)
        page.wait_for_timeout(2500)
        page.keyboard.press("Shift+1")  # ajustar a la vista (zoom to fit)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / f"{name}.png"))
    page.goto(f"http://{HOST}:9000/home/workflows")
    page.wait_for_timeout(3000)
    page.screenshot(path=str(OUT / "n8n_workflows.png"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        desktop = browser.new_page(viewport={"width": 1600, "height": 900}, locale="es-CO")
        portal(desktop)
        qr(desktop)
        n8n(desktop)
        phone = browser.new_page(viewport={"width": 420, "height": 860}, device_scale_factor=2, locale="es-CO")
        chat_web(phone)
        browser.close()
    print("capturas en", OUT)


if __name__ == "__main__":
    main()
