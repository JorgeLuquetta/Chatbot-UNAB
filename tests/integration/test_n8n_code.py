"""Prueba con Node.js la lógica JS de los nodos Code de n8n (n8n/code/lib.js).

Property 5 (clasificador siempre retorna etiqueta válida), Property 16 (ventana de
10 intercambios en el prompt) y Property 24 (paridad JS/Python de la ventana de 48h).
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "n8n" / "code" / "lib.js"
sys.path.insert(0, str(ROOT / "mcp-server"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js no instalado")
hsettings.register_profile("ci", max_examples=100, deadline=None)
hsettings.load_profile("ci")

LABELS = {"consulta-general", "calendario", "cursos-realizados", "noticias"}


def js(fn: str, *args):
    script = (f"const lib = require({json.dumps(str(LIB))});"
              "const args = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              f"const r = lib.{fn}(...args.map(a => a && a.__date__ ? new Date(a.__date__) : a));"
              "process.stdout.write(JSON.stringify(r === undefined ? null : r));")
    out = subprocess.run(["node", "-e", script], input=json.dumps(list(args)), capture_output=True,
                         text=True, check=True)
    return json.loads(out.stdout)


def jsbatch(fn: str, values: list):
    script = (f"const lib = require({json.dumps(str(LIB))});"
              "const vals = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              f"process.stdout.write(JSON.stringify(vals.map(v => lib.{fn}(v))));")
    out = subprocess.run(["node", "-e", script], input=json.dumps(values), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# Feature: chatbot-apoyo-academico, Property 5: El clasificador de intención siempre retorna una etiqueta válida
@given(raws=st.lists(st.one_of(st.text(), st.sampled_from(sorted(LABELS)).map(lambda l: f"  {l.upper()}. "),
                               st.none(), st.integers()), min_size=1, max_size=50))
def test_property_5_always_valid_label(raws):
    results = jsbatch("normalizeIntent", raws)
    assert all(r in LABELS for r in results)


def test_rule_intent_examples():
    cases = {
        "¿Cuál es mi avance en la carrera?": "cursos-realizados",
        "¿Qué cursos he aprobado?": "cursos-realizados",
        "Muéstrame mis notas": "cursos-realizados",
        "¿Cuántas materias me faltan?": "cursos-realizados",
        "¿Qué noticias hay en la universidad?": "noticias",
        "¿Hay convocatorias abiertas?": "noticias",
        "¿Cuándo son los parciales?": "calendario",
        "¿Cuál es la fecha de matrícula?": "calendario",
        "¿Cuáles son los requisitos de grado?": "consulta-general",
        "¿Cómo se calcula la nota de un examen supletorio?": "consulta-general",
        "¿Qué pasa si repruebo una materia tres veces?": "consulta-general",
        # Sin coincidencia clara → null (decide el LLM)
        "¿Qué es el bienestar universitario?": None,
        "hola": None,
        "¿Cuántos créditos me faltan para el grado?": None,  # cursos + grado → ambiguo
        # Dos intenciones a la vez → null
        "¿Qué noticias hay sobre la fecha de matrícula?": None,
    }
    assert jsbatch("ruleIntent", list(cases)) == list(cases.values())


@given(st.text())
def test_rule_intent_is_label_or_null(text):
    assert jsbatch("ruleIntent", [text])[0] in LABELS | {None}


def test_normalize_intent_examples():
    vals = ["calendario", "Calendario.", '"noticias"', "cursos realizados", "Etiqueta: cursos-realizados",
            "no sé", "", "calendario o noticias"]
    assert jsbatch("normalizeIntent", vals) == ["calendario", "calendario", "noticias", "cursos-realizados",
                                                "cursos-realizados", "consulta-general", "consulta-general",
                                                "consulta-general"]


# Feature: chatbot-apoyo-academico, Property 16: Ventana de contexto de memoria limitada a 10 exchanges
@given(n=st.integers(0, 80))
def test_property_16_prompt_history_window(n):
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(n)]
    msgs = js("buildMessages", "ctx", history, "pregunta")
    hist = msgs[1:-1]
    assert len(hist) == min(n, 20)
    assert [m["content"] for m in hist] == [f"m{i}" for i in range(max(0, n - 20), n)]
    assert msgs[0]["role"] == "system" and msgs[-1] == {"role": "user", "content": "pregunta"}


NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)


# Feature: chatbot-apoyo-academico, Property 24: Notificaciones push dentro de ventana de 48 horas (paridad JS)
@given(offsets=st.lists(st.integers(-5 * 24 * 60, 5 * 24 * 60), max_size=30), date_only=st.booleans())
def test_property_24_js_matches_python(offsets, date_only):
    from app.notifications import events_in_window

    def fmt(m):
        d = NOW + timedelta(minutes=m)
        return d.astimezone(timezone(timedelta(hours=-5))).date().isoformat() if date_only else d.isoformat()

    events = [{"event_name": f"E{i}", "event_date": fmt(m)} for i, m in enumerate(offsets)]
    py = [e["event_key"] for e in events_in_window(events, NOW)]
    jsr = [e["event_key"] for e in js("eventsInWindow", events, {"__date__": NOW.isoformat()}, 48)]
    assert py == jsr


def test_calendar_events_spanish_headers():
    rows = [{"Evento": "Parciales", "Fecha": "2026-11-20", "Descripción": "Segundo corte"},
            {"event_name": "", "event_date": "2026-01-01"}]
    assert js("calendarEvents", rows) == [{"event_name": "Parciales", "event_date": "2026-11-20",
                                           "description": "Segundo corte"}]


def test_bearer_token():
    assert js("bearerToken", {"authorization": "Bearer abc123"}) == "abc123"
    assert js("bearerToken", {"authorization": "Basic x"}) == ""
    assert js("bearerToken", None) == ""


def test_chat_response_has_a_hard_token_limit():
    workflow = json.loads((ROOT / "n8n" / "workflows" / "01_chat_ruteo.json").read_text(encoding="utf-8"))
    node = next(n for n in workflow["nodes"] if n["name"] == "Generar respuesta (LLM)")
    assert "Math.min(80, parseInt($env.LLM_MAX_TOKENS, 10) || 80)" in node["parameters"]["jsonBody"]
