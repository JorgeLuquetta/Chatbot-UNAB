"""Tests de integración sobre las funciones SQL de db/schema.sql (PostgreSQL real).

    TEST_DB_URL=postgresql://postgres@localhost:5432/chatbot_test pytest tests/integration
La base debe tener aplicados db/schema.sql y db/seed.sql.
Properties 16, 17, 18 y 19 (memoria persistente) + autenticación + notificaciones.
"""
import asyncio
import json
import os
import uuid

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

DSN = os.getenv("TEST_DB_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DB_URL no definida")
hsettings.register_profile("db", max_examples=100, deadline=None)
hsettings.load_profile("db")


def run(fn):
    import asyncpg

    async def go():
        conn = await asyncpg.connect(DSN, statement_cache_size=0)
        try:
            return await fn(conn)
        finally:
            await conn.execute("DELETE FROM conversation_memory WHERE session_id LIKE '__t_%'")
            await conn.close()

    return asyncio.run(go())


def sid():
    return "__t_" + uuid.uuid4().hex[:10]


async def history(conn, s, k=10):
    return json.loads(await conn.fetchval("SELECT get_recent_history($1, $2)", s, k))


msg = st.text(min_size=1, max_size=50).filter(lambda t: "\x00" not in t)


# Feature: chatbot-apoyo-academico, Property 16: Ventana de contexto de memoria limitada a 10 exchanges
@given(n=st.integers(0, 30))
def test_property_16_last_10_exchanges(n):
    async def body(conn):
        s = sid()
        for i in range(n):
            await conn.execute("SELECT save_exchange($1, $2, $3)", s, f"q{i}", f"a{i}")
        h = await history(conn, s)
        assert len(h) == 2 * min(n, 10)
        expected = []
        for i in range(max(0, n - 10), n):
            expected += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
        assert h == expected

    run(body)


# Feature: chatbot-apoyo-academico, Property 17: Round-trip de memoria persistente
@given(q=msg, a=msg)
def test_property_17_roundtrip(q, a):
    async def body(conn):
        s = sid()
        await conn.execute("SELECT save_exchange($1, $2, $3)", s, q, a)
        assert (await history(conn, s))[-2:] == [{"role": "user", "content": q}, {"role": "assistant", "content": a}]

    run(body)


# Feature: chatbot-apoyo-academico, Property 18: Aislamiento de memoria por sesión
@given(qa=st.lists(msg, min_size=1, max_size=5), qb=st.lists(msg, min_size=1, max_size=5))
def test_property_18_isolation(qa, qb):
    async def body(conn):
        a, b = sid(), sid()
        for i, q in enumerate(qa):
            await conn.execute("SELECT save_exchange($1, $2, $3)", a, f"A{i}:{q}", "resp")
        for i, q in enumerate(qb):
            await conn.execute("SELECT save_exchange($1, $2, $3)", b, f"B{i}:{q}", "resp")
        ha = [m["content"] for m in await history(conn, a, 50) if m["role"] == "user"]
        hb = [m["content"] for m in await history(conn, b, 50) if m["role"] == "user"]
        assert all(c.startswith("A") for c in ha) and all(c.startswith("B") for c in hb)
        assert len(ha) == len(qa) and len(hb) == len(qb)

    run(body)


# Feature: chatbot-apoyo-academico, Property 19: Límite de retención de memoria (máximo 50 exchanges)
@hsettings(max_examples=15)  # cada ejemplo inserta hasta 140 filas
@given(n=st.integers(45, 70))
def test_property_19_retention(n):
    async def body(conn):
        s = sid()
        for i in range(n):
            await conn.execute("SELECT save_exchange($1, $2, $3)", s, f"q{i}", f"a{i}")
        rows = await conn.fetch("SELECT role, content FROM conversation_memory WHERE session_id=$1 ORDER BY seq", s)
        assert len(rows) == 2 * min(n, 50)
        first = max(0, n - 50)
        assert rows[0]["content"] == f"q{first}" and rows[-1]["content"] == f"a{n - 1}"

    run(body)


def test_login_and_session_validation():
    async def body(conn):
        bad = await conn.fetch("SELECT * FROM login_student('U00000001', 'incorrecta')")
        assert bad == []
        assert await conn.fetch("SELECT * FROM login_student('NO_EXISTE', 'x')") == []
        r1 = await conn.fetchrow("SELECT * FROM login_student('U00000001', 'Unab2026*')")
        r2 = await conn.fetchrow("SELECT * FROM login_student('U00000001', 'Unab2026*')")
        assert r1["session_id"] == r2["session_id"]  # session_id estable entre logins
        assert r1["token"] != r2["token"]
        assert await conn.fetchval("SELECT session_id FROM validate_session($1)", r2["token"]) == r2["session_id"]
        assert await conn.fetchval("SELECT session_id FROM validate_session($1)", r1["token"]) is None  # rotado
        assert await conn.fetchval("SELECT session_id FROM validate_session($1)", "basura") is None
        assert await conn.fetchval("SELECT session_id FROM validate_session(NULL)") is None

    run(body)


def test_pending_notifications_exactly_once():
    async def body(conn):
        s = (await conn.fetchrow("SELECT * FROM login_student('U00000002', 'Unab2026*')"))["session_id"]
        await conn.execute("INSERT INTO device_tokens (session_id, fcm_token) VALUES ($1, '__t_tok') "
                           "ON CONFLICT DO NOTHING", s)
        key = "__t_evento|" + uuid.uuid4().hex
        events = json.dumps([{"event_key": key, "event_name": "Parciales", "event_date": "2026-11-13"}])
        try:
            first = await conn.fetch("SELECT * FROM pending_notifications($1::jsonb) WHERE fcm_token='__t_tok'", events)
            assert len(first) == 1
            await conn.execute("INSERT INTO notifications_sent (event_key, session_id) VALUES ($1, $2) "
                               "ON CONFLICT DO NOTHING", key, s)
            again = await conn.fetch("SELECT * FROM pending_notifications($1::jsonb) WHERE fcm_token='__t_tok'", events)
            assert again == []
        finally:
            await conn.execute("DELETE FROM device_tokens WHERE fcm_token='__t_tok'")
            await conn.execute("DELETE FROM notifications_sent WHERE event_key=$1", key)

    run(body)
