-- =====================================================================
-- Módulo académico: prerrequisitos, calendario, matrícula, estado académico,
-- proyección y recomendaciones (ejecutar DESPUÉS de schema.sql, seed.sql y
-- seed_sintetico.sql). Idempotente.
--
--   course_prerequisites  materia → materia requisito
--   academic_calendar     calendario académico (reemplaza a Google Sheets)
--   noticias.category / source_name   clasificación del scraper
--   academic_plan(session_id) → JSONB con:
--       student, status (estado académico), enrollment (matrícula sugerida),
--       projection (proyección de grado) y recommendations (recomendaciones)
--
-- Reglas (documentadas también en data/ccd/reglamento_estudiantil.md):
--   * Nota aprobatoria: 3.0. Promedio ponderado por créditos.
--   * Carga máxima por semestre: 18 créditos; 21 si el promedio >= 4.0;
--     12 si el estudiante está en prueba académica (promedio < 3.3 o 3+ reprobadas).
--   * Una materia se puede matricular si todos sus prerrequisitos están aprobados
--     (o en curso: matrícula condicionada a aprobarlos).
-- =====================================================================

-- ------------------------------------------------------------ prerrequisitos
CREATE TABLE IF NOT EXISTS course_prerequisites (
    course_code  TEXT NOT NULL REFERENCES program_courses(course_code) ON DELETE CASCADE,
    prereq_code  TEXT NOT NULL REFERENCES program_courses(course_code) ON DELETE CASCADE,
    PRIMARY KEY (course_code, prereq_code),
    CHECK (course_code <> prereq_code)
);

-- Ingeniería de Sistemas: prerrequisitos explícitos
INSERT INTO course_prerequisites (course_code, prereq_code) VALUES
    ('ISC201','ISC101'), ('ISC202','ISC102'), ('ISC203','ISC103'),
    ('ISC301','ISC202'), ('ISC302','ISC201'), ('ISC303','ISC202'),
    ('ISC401','ISC301'), ('ISC401','ISC103'), ('ISC402','ISC303'), ('ISC403','ISC103'),
    ('ISC501','ISC301'), ('ISC502','ISC403'), ('ISC503','ISC403'), ('ISC503','ISC301'),
    ('ISC601','ISC302'), ('ISC601','ISC402'), ('ISC602','ISC501'), ('ISC603','ISC502'),
    ('ISC701','ISC601'), ('ISC701','ISC401'), ('ISC702','ISC502'), ('ISC702','ISC503'),
    ('ISC801','ISC602'), ('ISC801','ISC601'), ('ISC901','ISC801')
ON CONFLICT DO NOTHING;

-- Demás programas: la materia en la posición k del semestre s requiere la materia en la
-- posición k del semestre s-1 (si existe). Regla sintética, suficiente para la demo.
WITH ranked AS (
    SELECT course_code, program, semester,
           row_number() OVER (PARTITION BY program, semester ORDER BY course_code) AS pos
      FROM program_courses WHERE program <> 'Ingeniería de Sistemas'
)
INSERT INTO course_prerequisites (course_code, prereq_code)
SELECT cur.course_code, prev.course_code
  FROM ranked cur JOIN ranked prev
    ON prev.program = cur.program AND prev.semester = cur.semester - 1 AND prev.pos = cur.pos
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------ calendario académico
CREATE TABLE IF NOT EXISTS academic_calendar (
    id          SERIAL PRIMARY KEY,
    event_name  TEXT NOT NULL,
    event_date  DATE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (event_name, event_date)
);
INSERT INTO academic_calendar (event_name, event_date, description) VALUES
    ('Inicio de clases segundo semestre','2026-07-27','Inicio de actividades académicas del periodo 2026-2'),
    ('Último día para cancelar materias','2026-10-02','Cancelación sin nota a través del portal estudiantil'),
    ('Segundo corte de parciales','2026-11-17','Semana de evaluaciones del segundo corte'),
    ('Convocatoria semilleros de investigación','2026-11-24','Cierre de inscripciones a semilleros de investigación 2027-1'),
    ('Entrega de proyectos finales','2026-11-27','Fecha límite de entrega de proyectos de curso'),
    ('Exámenes finales','2026-12-01','Semana de exámenes finales'),
    ('Fin de clases','2026-12-05','Cierre del periodo académico 2026-2'),
    ('Publicación de notas definitivas','2026-12-11','Notas finales disponibles en el portal estudiantil'),
    ('Matrícula académica 2027-1 (inscripción de materias)','2027-01-12','Inscripción de materias según el plan sugerido y los prerrequisitos'),
    ('Matrícula financiera 2027-1','2027-01-15','Pago de matrícula ordinaria'),
    ('Inicio de clases 2027-1','2027-01-25','Inicio de actividades académicas del periodo 2027-1'),
    ('Ajustes de matrícula 2027-1','2027-02-05','Último día para adicionar o retirar materias sin recargo')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------ noticias: categoría y fuente
ALTER TABLE noticias ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'general';
ALTER TABLE noticias ADD COLUMN IF NOT EXISTS source_name TEXT NOT NULL DEFAULT 'UNAB';
CREATE INDEX IF NOT EXISTS idx_noticias_category ON noticias (category, published_at DESC);

-- ------------------------------------------------------------ periodo académico
-- Periodo actual 'AAAA-1' (ene-jun) o 'AAAA-2' (jul-dic) y suma de n periodos.
CREATE OR REPLACE FUNCTION academic_term(p_date DATE, p_add INT DEFAULT 0) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT ((idx / 2)::int)::text || '-' || ((idx % 2) + 1)::text
      FROM (SELECT extract(year FROM p_date)::int * 2
                   + CASE WHEN extract(month FROM p_date) <= 6 THEN 0 ELSE 1 END + p_add AS idx) t
$$;

-- ------------------------------------------------------------ plan académico completo
CREATE OR REPLACE FUNCTION academic_plan(p_session_id TEXT) RETURNS JSONB
LANGUAGE plpgsql STABLE AS $$
DECLARE
    st            RECORD;
    v_sem         INT;
    v_total_cr    INT;
    v_appr_cr     INT;
    v_prog_cr     INT;
    v_gpa         NUMERIC;
    v_failed      INT;
    v_standing    TEXT;
    v_limit       INT;
    v_remaining   INT;
    v_sems_left   INT;
    v_chain       INT;
    v_enroll      JSONB := '[]'::jsonb;
    v_blocked     JSONB := '[]'::jsonb;
    v_enroll_cr   INT := 0;
    v_recs        JSONB := '[]'::jsonb;
    v_weak        RECORD;
    v_strong      RECORD;
    c             RECORD;
BEGIN
    SELECT s.student_id, s.full_name, s.program INTO st
      FROM student_sessions ss JOIN students s ON s.student_id = ss.student_id
     WHERE ss.session_id = p_session_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Semestre actual: el de las materias en curso (o el siguiente al último aprobado)
    SELECT COALESCE(max(semester) FILTER (WHERE status = 'in_progress'),
                    max(semester) FILTER (WHERE status = 'completed') + 1, 1)
      INTO v_sem FROM student_courses WHERE student_session = p_session_id;

    SELECT COALESCE(sum(credits), 0) INTO v_prog_cr FROM program_courses WHERE program = st.program;
    SELECT COALESCE(sum(COALESCE(pc.credits, 3)), 0) INTO v_appr_cr
      FROM student_courses sc LEFT JOIN program_courses pc ON pc.course_code = sc.course_code
     WHERE sc.student_session = p_session_id AND sc.status = 'completed';
    -- Promedio ponderado por créditos de todas las materias con nota (incluye reprobadas)
    SELECT round(sum(sc.grade * COALESCE(pc.credits, 3)) / NULLIF(sum(COALESCE(pc.credits, 3)), 0), 2),
           count(*) FILTER (WHERE sc.grade < 3.0)
      INTO v_gpa, v_failed
      FROM student_courses sc LEFT JOIN program_courses pc ON pc.course_code = sc.course_code
     WHERE sc.student_session = p_session_id AND sc.grade IS NOT NULL;
    v_total_cr := GREATEST(v_prog_cr, v_appr_cr);

    v_standing := CASE
        WHEN v_gpa IS NULL THEN 'sin notas'
        WHEN v_gpa < 3.3 OR v_failed >= 3 THEN 'prueba académica'
        WHEN v_gpa >= 4.3 AND v_failed = 0 THEN 'excelencia'
        WHEN v_failed > 0 OR v_gpa < 3.6 THEN 'en observación'
        ELSE 'normal' END;
    v_limit := CASE WHEN v_standing = 'prueba académica' THEN 12
                    WHEN v_gpa >= 4.0 THEN 21 ELSE 18 END;

    -- ---------------- matrícula sugerida para el próximo periodo
    -- Candidatas: no aprobadas y no en curso. Prioridad: reprobadas, luego semestre más bajo.
    FOR c IN
        SELECT sc.course_code, sc.course_name, sc.semester, COALESCE(pc.credits, 3) AS credits,
               (sc.grade IS NOT NULL AND sc.grade < 3.0) AS repeat,
               COALESCE((SELECT jsonb_agg(jsonb_build_object('course_code', cp.prereq_code,
                                                             'course_name', p2.course_name,
                                                             'status', COALESCE(s2.status, 'pending')))
                           FROM course_prerequisites cp
                           JOIN program_courses p2 ON p2.course_code = cp.prereq_code
                           LEFT JOIN student_courses s2 ON s2.student_session = p_session_id
                                                       AND s2.course_code = cp.prereq_code
                          WHERE cp.course_code = sc.course_code
                            AND COALESCE(s2.status, 'pending') <> 'completed'), '[]'::jsonb) AS missing
          FROM student_courses sc LEFT JOIN program_courses pc ON pc.course_code = sc.course_code
         WHERE sc.student_session = p_session_id AND sc.status = 'pending'
         ORDER BY (sc.grade IS NOT NULL AND sc.grade < 3.0) DESC, sc.semester, sc.course_code
    LOOP
        -- Prerrequisito pendiente (ni aprobado ni en curso) → bloqueada
        IF EXISTS (SELECT 1 FROM jsonb_array_elements(c.missing) m WHERE m->>'status' = 'pending') THEN
            IF jsonb_array_length(v_blocked) < 5 THEN
            v_blocked := v_blocked || jsonb_build_object('course_code', c.course_code, 'course_name', c.course_name,
                         'semester', c.semester, 'missing_prerequisites', c.missing);
            END IF;
        ELSIF v_enroll_cr + c.credits <= v_limit THEN
            v_enroll := v_enroll || jsonb_build_object('course_code', c.course_code, 'course_name', c.course_name,
                        'semester', c.semester, 'credits', c.credits, 'repeat', c.repeat,
                        'conditional', jsonb_array_length(c.missing) > 0,
                        'conditional_on', c.missing);
            v_enroll_cr := v_enroll_cr + c.credits;
        END IF;
    END LOOP;

    -- ---------------- proyección
    v_remaining := GREATEST(v_total_cr - v_appr_cr, 0);
    -- Créditos en curso se asumen aprobados al final del periodo actual
    v_remaining := GREATEST(v_remaining - COALESCE((SELECT sum(COALESCE(pc.credits, 3))
                        FROM student_courses sc LEFT JOIN program_courses pc ON pc.course_code = sc.course_code
                       WHERE sc.student_session = p_session_id AND sc.status = 'in_progress'), 0), 0);
    -- Periodos restantes: lo que exija más entre créditos/carga máxima y la cadena más larga de
    -- prerrequisitos pendientes (una materia no se puede ver el mismo periodo que su requisito).
    WITH RECURSIVE pend AS (
        SELECT course_code FROM student_courses WHERE student_session = p_session_id AND status = 'pending'
    ), chain(course_code, depth) AS (
        SELECT p.course_code, 1 FROM pend p
         WHERE NOT EXISTS (SELECT 1 FROM course_prerequisites cp JOIN pend q ON q.course_code = cp.prereq_code
                            WHERE cp.course_code = p.course_code)
        UNION ALL
        SELECT cp.course_code, ch.depth + 1 FROM chain ch
          JOIN course_prerequisites cp ON cp.prereq_code = ch.course_code
          JOIN pend p ON p.course_code = cp.course_code
         WHERE ch.depth < 20
    )
    SELECT COALESCE(max(depth), 0) INTO v_chain FROM chain;
    v_sems_left := GREATEST(CEIL(v_remaining::numeric / GREATEST(v_limit, 1))::int, v_chain);

    -- ---------------- recomendaciones (educación de precisión: según SUS datos)
    SELECT course_name, grade INTO v_weak FROM student_courses
     WHERE student_session = p_session_id AND status = 'completed' AND grade IS NOT NULL
     ORDER BY grade, semester LIMIT 1;
    SELECT course_name, grade INTO v_strong FROM student_courses
     WHERE student_session = p_session_id AND status = 'completed' AND grade IS NOT NULL
     ORDER BY grade DESC, semester DESC LIMIT 1;

    IF v_failed > 0 THEN
        v_recs := v_recs || jsonb_build_object('type', 'matricula', 'text',
            'Matricula primero las materias reprobadas (' ||
            (SELECT string_agg(course_name, ', ') FROM student_courses
              WHERE student_session = p_session_id AND grade < 3.0) ||
            '): son prerrequisito de otras y afectan tu promedio. Pide tutoría en el Centro de Apoyo Estudiantil.');
    END IF;
    IF v_standing = 'prueba académica' THEN
        v_recs := v_recs || jsonb_build_object('type', 'riesgo', 'text',
            'Estás en prueba académica: tu carga máxima es de 12 créditos. Agenda una cita con tu director de programa y arma un plan de estudio semanal.');
    END IF;
    IF v_weak.course_name IS NOT NULL AND v_weak.grade < 3.8 THEN
        v_recs := v_recs || jsonb_build_object('type', 'precision', 'text',
            'Tu nota más baja es ' || v_weak.grade || ' en ' || v_weak.course_name ||
            '. Refuerza esos fundamentos antes de las materias que dependen de ella (repasa con ejercicios y monitorías).');
    END IF;
    IF v_gpa >= 4.0 THEN
        v_recs := v_recs || jsonb_build_object('type', 'investigacion', 'text',
            'Con promedio ' || v_gpa || ' puedes postularte a un semillero de investigación o a una monitoría' ||
            COALESCE(' (tu mejor desempeño es en ' || v_strong.course_name || ')', '') || '.');
    ELSE
        v_recs := v_recs || jsonb_build_object('type', 'investigacion', 'text',
            'Participa en un semillero de investigación de tu programa: desarrolla autonomía y suma para tu opción de grado.');
    END IF;
    IF v_sem <= 3 THEN
        v_recs := v_recs || jsonb_build_object('type', 'autoaprendizaje', 'text',
            'Crea hábitos de autoaprendizaje: 2 horas de estudio independiente por cada hora de clase, técnica Pomodoro y repaso espaciado.');
    ELSIF v_sem >= 6 THEN
        v_recs := v_recs || jsonb_build_object('type', 'grado', 'text',
            'Ya puedes preparar tu opción de grado (proyecto, pasantía o investigación) y revisar el requisito de segunda lengua (B1).');
    ELSE
        v_recs := v_recs || jsonb_build_object('type', 'autoaprendizaje', 'text',
            'Complementa con cursos en línea (MOOC) y certificaciones relacionadas con tus materias del semestre.');
    END IF;

    RETURN jsonb_build_object(
        'student', jsonb_build_object('student_id', st.student_id, 'full_name', st.full_name,
                                      'program', st.program, 'current_semester', v_sem),
        'status', jsonb_build_object(
            'gpa', v_gpa, 'standing', v_standing,
            'approved_credits', v_appr_cr, 'total_credits', v_total_cr,
            'progress_percentage', CASE WHEN v_total_cr > 0 THEN round(100.0 * v_appr_cr / v_total_cr, 1) ELSE 0 END,
            'failed_courses', v_failed,
            'in_progress', COALESCE((SELECT jsonb_agg(jsonb_build_object('course_code', course_code, 'course_name', course_name))
                                       FROM student_courses WHERE student_session = p_session_id AND status = 'in_progress'), '[]'::jsonb)),
        'enrollment', jsonb_build_object(
            'term', academic_term(current_date, 1), 'max_credits', v_limit, 'credits', v_enroll_cr,
            'courses', v_enroll, 'blocked', v_blocked),
        'projection', jsonb_build_object(
            'remaining_credits', v_remaining, 'credits_per_term', v_limit,
            'terms_remaining', v_sems_left, 'prerequisite_chain', v_chain,
            'estimated_graduation_term', academic_term(current_date, v_sems_left),
            'on_track', v_failed = 0 AND v_standing IN ('normal', 'excelencia', 'sin notas')),
        'recommendations', v_recs);
END;
$$;

-- ------------------------------------------------------------ imágenes de noticias
ALTER TABLE noticias ADD COLUMN IF NOT EXISTS image_url TEXT;

-- ------------------------------------------------------------ correo de los estudiantes
-- Correos TEMPORALES de prueba (yopmail.com: bandeja pública sin registro, https://yopmail.com/?unab.u00000010).
-- El estudiante puede cambiarlo desde el chat antes de un envío.
ALTER TABLE students ADD COLUMN IF NOT EXISTS email TEXT;
UPDATE students SET email = 'unab.' || lower(student_id) || '@yopmail.com' WHERE email IS NULL OR email = '';

-- Solicitudes de envío por correo. El asistente SOLO envía: noticias, informe de avance o informe de materias.
-- Flujo: el estudiante pide un envío → queda 'pending' y el asistente le muestra su correo → el estudiante
-- confirma (sí), escribe otro correo (se actualiza) o cancela → 'sent' / 'failed' / 'cancelled'.
CREATE TABLE IF NOT EXISTS email_requests (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    student_id  TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('noticias', 'avance', 'materias')),
    query       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    email_to    TEXT,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_email_requests_pending ON email_requests (session_id, created_at DESC) WHERE status = 'pending';
