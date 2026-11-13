"""Properties 7, 20 y 21 + tests de ejemplo de los endpoints."""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit import AuditLogEntry, MemoryAuditSink  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rules import (FALLBACK_RESPONSE, KNOWN_INJECTIONS, OUT_OF_SCOPE_TERMS, PROFANITY,  # noqa: E402
                       check_input, check_output)

hsettings.register_profile("ci", max_examples=100, deadline=None)
hsettings.load_profile("ci")

ACADEMIC_WORDS = ["el", "la", "de", "los", "créditos", "semestre", "matrícula", "curso", "ingeniería",
                  "sistemas", "requisito", "prerrequisito", "electiva", "horario", "UNAB", "facultad",
                  "programa", "competencias", "calendario", "inscripción", "notas", "promedio", "cuándo",
                  "cómo", "qué", "puedo", "necesito", "para", "grado", "práctica", "laboratorio", "?", "."]
academic_text = st.lists(st.sampled_from(ACADEMIC_WORDS), min_size=1, max_size=40).map(" ".join)


def _variants(phrase: str):
    """Variaciones de mayúsculas/espacios que un atacante usaría para evadir."""
    return st.sampled_from([phrase, phrase.upper(), phrase.title(), phrase.replace(" ", "  "),
                            phrase.replace(" ", "​ ")])


injection_st = st.sampled_from(KNOWN_INJECTIONS).flatmap(_variants)


@pytest.fixture
def sink():
    return MemoryAuditSink()


@pytest.fixture
def client(sink):
    with TestClient(create_app(sink)) as c:
        yield c


# Feature: chatbot-apoyo-academico, Property 20: Guardrails bloquea inyecciones de prompt
@given(prefix=academic_text, inj=injection_st, suffix=academic_text)
def test_property_20_injections_blocked(prefix, inj, suffix):
    v = check_input(f"{prefix} {inj} {suffix}"[:2000])
    assert v.allowed is False and v.rejection_type == "input_injection"


@given(msg=academic_text)
def test_property_20_benign_allowed(msg):
    assert check_input(msg).allowed is True


@given(msg=st.text(min_size=2001, max_size=2500) | st.just(""))
def test_length_out_of_range_rejected(msg):
    assert check_input(msg).allowed is False


# Feature: chatbot-apoyo-academico, Property 7: Guardrails sustituye respuestas fuera de alcance por el fallback exacto
@given(prefix=academic_text, bad=st.sampled_from(OUT_OF_SCOPE_TERMS + PROFANITY), suffix=academic_text)
def test_property_7_fallback_exact(prefix, bad, suffix):
    sink = MemoryAuditSink()
    with TestClient(create_app(sink)) as c:
        r = c.post("/validate-output", json={"session_id": "s1", "response": f"{prefix} {bad} {suffix}"}).json()
    assert r == {"allowed": False, "sanitized_response": FALLBACK_RESPONSE}
    assert len(sink.entries) == 1


@given(text=academic_text)
def test_property_7_in_scope_unchanged(text):
    assert check_output(text).allowed is True


# Feature: chatbot-apoyo-academico, Property 21: Log de auditoría completo en rechazos de guardrails
@given(session=st.text(max_size=30), inj=injection_st, out=st.sampled_from(OUT_OF_SCOPE_TERMS))
def test_property_21_audit_fields(session, inj, out):
    sink = MemoryAuditSink()
    with TestClient(create_app(sink)) as c:
        assert c.post("/validate-input", json={"session_id": session, "message": inj}).json()["allowed"] is False
        assert c.post("/validate-output", json={"session_id": session, "response": out}).json()["allowed"] is False
    assert len(sink.entries) == 2
    for e in sink.entries:
        assert e.timestamp is not None and e.session_id and e.rejection_reason
        assert len(e.raw_content_hash) == 64
        assert inj not in e.raw_content_hash  # nunca el contenido en claro
    assert [e.rejection_type for e in sink.entries] == ["input_injection", "output_scope"]


def test_endpoints_happy_path(client, sink):
    r = client.post("/validate-input", json={"session_id": "s", "message": "¿Cuántos créditos tiene el semestre?"})
    assert r.json() == {"allowed": True, "reason": None}
    r = client.post("/validate-output", json={"session_id": "s", "response": "El programa tiene 160 créditos."})
    assert r.json() == {"allowed": True, "sanitized_response": "El programa tiene 160 créditos."}
    assert sink.entries == []


def test_personal_info_and_institutional_email(client):
    ok = check_output("Escribe a admisiones@unab.edu.co para más información.")
    assert ok.allowed
    assert not check_output("El correo de Juan es juan.perez@gmail.com").allowed
    assert not check_output("Llámalo al 315 555 1234").allowed
    assert not check_output("Su cédula es 1098765432").allowed


def test_benign_spanish_phrases_not_flagged():
    for msg in ["Actúa como mi tutor de cálculo y explícame derivadas",
                "¿Qué instrucciones hay para la matrícula?",
                "Olvidé mi contraseña del portal, ¿qué hago?"]:
        assert check_input(msg).allowed, msg


def test_audit_entry_create_defaults():
    e = AuditLogEntry.create("", "input_injection", "", "x")
    assert e.session_id == "desconocida" and e.rejection_reason == "sin motivo"


def test_pg_audit_sink_writes(tmp_path):
    import os

    dsn = os.getenv("TEST_DB_URL")
    if not dsn:
        pytest.skip("TEST_DB_URL no definida")
    import asyncpg

    from app.audit import PostgresAuditSink

    async def go():
        sink = PostgresAuditSink(dsn, None)
        await sink.write(AuditLogEntry.create("__test_audit", "input_injection", "test", "contenido"))
        await sink.close()
        conn = await asyncpg.connect(dsn)
        row = await conn.fetchrow("SELECT * FROM guardrails_audit_log WHERE session_id='__test_audit'")
        await conn.execute("DELETE FROM guardrails_audit_log WHERE session_id='__test_audit'")
        await conn.close()
        return row

    row = asyncio.run(go())
    assert row["timestamp"] and row["rejection_reason"] == "test"
