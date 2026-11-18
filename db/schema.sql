-- =====================================================================
-- Chatbot de Apoyo Académico UNAB — Esquema PostgreSQL (Supabase)
-- Ejecutar completo en Supabase > SQL Editor antes de levantar los
-- contenedores. Es idempotente (se puede ejecutar varias veces).
--
-- Las líneas "-- @section" las usan los tests de integración para
-- aplicar el esquema en un PostgreSQL local sin pgvector.
-- =====================================================================

-- @section extensions-vector requires:vector
CREATE EXTENSION IF NOT EXISTS vector;

-- @section extensions-crypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- @section rag requires:vector
-- Chunks de documentos CCD (RAG)
CREATE TABLE IF NOT EXISTS document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_name   TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    total_chunks    INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_name, chunk_index)
);
-- HNSW en lugar de ivfflat: ivfflat con lists=100 sobre pocas filas
-- devuelve menos de top_k resultados (probes=1). HNSW no tiene ese problema.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- @section memory
-- Historial de conversación (Memoria Persistente)
CREATE TABLE IF NOT EXISTS conversation_memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq         BIGSERIAL NOT NULL,           -- orden estable (user antes que assistant)
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_memory_session
    ON conversation_memory (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_session_seq
    ON conversation_memory (session_id, seq DESC);

-- Requirement 10.4: conservar solo los 50 intercambios (100 mensajes) más recientes.
CREATE OR REPLACE FUNCTION trim_conversation_memory() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM conversation_memory
     WHERE session_id = NEW.session_id
       AND seq < (
            SELECT min(seq) FROM (
                SELECT seq FROM conversation_memory
                 WHERE session_id = NEW.session_id
                 ORDER BY seq DESC
                 LIMIT 100
            ) recent
       );
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_trim_conversation_memory ON conversation_memory;
CREATE TRIGGER trg_trim_conversation_memory
    AFTER INSERT ON conversation_memory
    FOR EACH ROW EXECUTE FUNCTION trim_conversation_memory();

-- Requirement 10.1: últimos 10 intercambios (20 mensajes) en orden cronológico, como JSON.
CREATE OR REPLACE FUNCTION get_recent_history(p_session_id TEXT, p_exchanges INT DEFAULT 10)
RETURNS JSONB LANGUAGE sql STABLE AS $$
    SELECT COALESCE(jsonb_agg(jsonb_build_object('role', role, 'content', content) ORDER BY seq), '[]'::jsonb)
      FROM (
        SELECT role, content, seq FROM conversation_memory
         WHERE session_id = p_session_id
         ORDER BY seq DESC
         LIMIT p_exchanges * 2
      ) h;
$$;

-- Requirement 10.2: guarda pregunta y respuesta en una sola llamada.
CREATE OR REPLACE FUNCTION save_exchange(p_session_id TEXT, p_user TEXT, p_assistant TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO conversation_memory (session_id, role, content) VALUES (p_session_id, 'user', p_user);
    INSERT INTO conversation_memory (session_id, role, content) VALUES (p_session_id, 'assistant', p_assistant);
END;
$$;

-- @section news
-- Noticias institucionales
CREATE TABLE IF NOT EXISTS noticias (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    published_at    TIMESTAMPTZ NOT NULL,
    summary         TEXT NOT NULL,
    source_url      TEXT NOT NULL UNIQUE,
    scraped_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_noticias_published ON noticias (published_at DESC);

-- @section students
-- Estudiantes (BD sintética) — credenciales institucionales de prueba
CREATE TABLE IF NOT EXISTS students (
    student_id      TEXT PRIMARY KEY,           -- p. ej. código U00123456
    full_name       TEXT NOT NULL,
    program         TEXT NOT NULL DEFAULT 'Ingeniería de Sistemas',
    password_hash   TEXT NOT NULL               -- crypt(password, gen_salt('bf'))
);

-- Tokens de sesión. session_id es ESTABLE por estudiante (student_id UNIQUE):
-- cada login rota el token pero conserva session_id, así la memoria y los
-- cursos persisten entre sesiones (Requirement 10).
CREATE TABLE IF NOT EXISTS student_sessions (
    session_id      TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL UNIQUE REFERENCES students(student_id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL
);

-- Cursos de estudiantes (BD sintética)
CREATE TABLE IF NOT EXISTS student_courses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_session TEXT NOT NULL,
    course_code     TEXT NOT NULL,
    course_name     TEXT NOT NULL,
    semester        INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('completed', 'pending', 'in_progress')),
    grade           NUMERIC(4,2),
    UNIQUE (student_session, course_code)
);
CREATE INDEX IF NOT EXISTS idx_courses_session ON student_courses (student_session);

-- Login: devuelve una fila con el token en claro (solo esta vez) o ninguna fila.
CREATE OR REPLACE FUNCTION login_student(p_student_id TEXT, p_password TEXT, p_hours INT DEFAULT 8)
RETURNS TABLE (session_id TEXT, token TEXT, expires_at TIMESTAMPTZ, full_name TEXT)
LANGUAGE plpgsql AS $$
DECLARE
    v_student students%ROWTYPE;
    v_token   TEXT;
    v_session TEXT;
    v_expires TIMESTAMPTZ := now() + make_interval(hours => p_hours);
BEGIN
    SELECT * INTO v_student FROM students s WHERE s.student_id = p_student_id;
    IF NOT FOUND OR v_student.password_hash <> crypt(p_password, v_student.password_hash) THEN
        RETURN;  -- sin filas = credenciales inválidas (no se revela cuál campo falló)
    END IF;

    v_token := encode(gen_random_bytes(32), 'hex');

    INSERT INTO student_sessions AS ss (session_id, student_id, token_hash, expires_at)
    VALUES ('sess_' || encode(gen_random_bytes(12), 'hex'), p_student_id,
            encode(digest(v_token, 'sha256'), 'hex'), v_expires)
    ON CONFLICT (student_id) DO UPDATE
        SET token_hash = EXCLUDED.token_hash, expires_at = EXCLUDED.expires_at
    RETURNING ss.session_id INTO v_session;

    RETURN QUERY SELECT v_session, v_token, v_expires, v_student.full_name;
END;
$$;

-- Valida un token Bearer. Devuelve session_id o ninguna fila si es inválido/expirado.
CREATE OR REPLACE FUNCTION validate_session(p_token TEXT)
RETURNS TABLE (session_id TEXT, student_id TEXT)
LANGUAGE sql STABLE AS $$
    SELECT ss.session_id, ss.student_id
      FROM student_sessions ss
     WHERE ss.token_hash = encode(digest(COALESCE(p_token, ''), 'sha256'), 'hex')
       AND ss.expires_at > now();
$$;

-- Chat sin login (demo): busca al estudiante solo por su ID y devuelve su sesión
-- estable y un resumen (programa, semestre actual, avance). Si nunca inició sesión,
-- crea su fila de sesión con un token inutilizable (ya expirado).
DROP FUNCTION IF EXISTS session_by_student(TEXT);
CREATE OR REPLACE FUNCTION session_by_student(p_student_id TEXT)
RETURNS TABLE (session_id TEXT, student_id TEXT, full_name TEXT, program TEXT,
               current_semester INT, progress_percentage NUMERIC)
LANGUAGE plpgsql AS $$
DECLARE
    v_id TEXT := upper(btrim(COALESCE(p_student_id, '')));
BEGIN
    IF NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = v_id) THEN
        RETURN;  -- sin filas = ID no encontrado
    END IF;
    INSERT INTO student_sessions (session_id, student_id, token_hash, expires_at)
    VALUES ('sess_' || encode(gen_random_bytes(12), 'hex'), v_id,
            encode(gen_random_bytes(32), 'hex'), now())
    ON CONFLICT ON CONSTRAINT student_sessions_student_id_key DO NOTHING;
    RETURN QUERY
        SELECT ss.session_id, s.student_id, s.full_name, s.program,
               (SELECT max(c.semester) FROM student_courses c
                 WHERE c.student_session = ss.session_id AND c.status = 'in_progress')::INT,
               (SELECT COALESCE(round(100.0 * count(*) FILTER (WHERE c.status = 'completed') / NULLIF(count(*), 0), 1), 0)
                  FROM student_courses c WHERE c.student_session = ss.session_id)
          FROM students s JOIN student_sessions ss ON ss.student_id = s.student_id
         WHERE s.student_id = v_id;
END;
$$;

-- @section audit
-- Log de auditoría de guardrails
CREATE TABLE IF NOT EXISTS guardrails_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id          TEXT NOT NULL,
    rejection_type      TEXT NOT NULL,
    rejection_reason    TEXT NOT NULL,
    raw_content_hash    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON guardrails_audit_log (session_id, timestamp DESC);

-- @section notifications
-- Tokens FCM de los dispositivos Android
CREATE TABLE IF NOT EXISTS device_tokens (
    session_id  TEXT NOT NULL REFERENCES student_sessions(session_id) ON DELETE CASCADE,
    fcm_token   TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (session_id, fcm_token)
);

-- Registro de notificaciones enviadas: garantiza "exactamente una" (Property 24)
CREATE TABLE IF NOT EXISTS notifications_sent (
    event_key   TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (event_key, session_id)
);

-- Recibe los eventos ya filtrados a la ventana de 48h y devuelve a quién falta notificar.
CREATE OR REPLACE FUNCTION pending_notifications(p_events JSONB)
RETURNS TABLE (event_key TEXT, event_name TEXT, event_date TEXT, session_id TEXT, fcm_token TEXT)
LANGUAGE sql STABLE AS $$
    SELECT e->>'event_key', e->>'event_name', e->>'event_date', dt.session_id, dt.fcm_token
      FROM jsonb_array_elements(COALESCE(p_events, '[]'::jsonb)) e
      CROSS JOIN device_tokens dt
     WHERE NOT EXISTS (
        SELECT 1 FROM notifications_sent ns
         WHERE ns.event_key = e->>'event_key' AND ns.session_id = dt.session_id
     );
$$;

-- @section security
-- Bloquea el acceso por la API pública de Supabase (anon/authenticated).
-- El backend usa la conexión directa (rol propietario), que no se ve afectada.
ALTER TABLE conversation_memory  ENABLE ROW LEVEL SECURITY;
ALTER TABLE noticias             ENABLE ROW LEVEL SECURITY;
ALTER TABLE students             ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_sessions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_courses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardrails_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_tokens        ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_sent   ENABLE ROW LEVEL SECURITY;

-- @section security-vector requires:vector
ALTER TABLE document_chunks      ENABLE ROW LEVEL SECURITY;
