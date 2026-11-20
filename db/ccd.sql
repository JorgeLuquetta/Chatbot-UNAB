-- =====================================================================
-- Centro de Competencias Digitales (CCD), requisitos de grado individuales,
-- alertas y vistas analíticas para agentes. Ejecutar DESPUÉS de academico.sql.
-- Idempotente. Datos sintéticos (semilla fija); reglas en data/ccd/centro_competencias_digitales.md
-- =====================================================================

-- ------------------------------------------------------------ catálogo CCD
CREATE TABLE IF NOT EXISTS ccd_courses (
    course_code  TEXT PRIMARY KEY,
    course_name  TEXT NOT NULL,
    level        TEXT NOT NULL CHECK (level IN ('básico', 'intermedio', 'avanzado')),
    hours        INTEGER NOT NULL,
    modality     TEXT NOT NULL,
    required     BOOLEAN NOT NULL,          -- obligatorio para la insignia
    sort_order   INTEGER NOT NULL
);
INSERT INTO ccd_courses VALUES
    ('CCD01', 'Ciudadanía y bienestar digital',                 'básico',     32, 'Virtual',             true,  1),
    ('CCD02', 'Herramientas ofimáticas y productividad',        'básico',     32, 'Virtual',             true,  2),
    ('CCD03', 'Gestión de información y búsqueda académica',    'intermedio', 32, 'Virtual',             true,  3),
    ('CCD04', 'Análisis de datos con hojas de cálculo',         'intermedio', 32, 'Presencial asistido', true,  4),
    ('CCD05', 'Herramientas colaborativas en la nube',          'intermedio', 24, 'Virtual',             false, 5),
    ('CCD06', 'Inteligencia artificial generativa responsable', 'avanzado',   24, 'Virtual',             false, 6),
    ('CCD07', 'Pensamiento computacional y programación básica','avanzado',   32, 'Presencial asistido', false, 7)
ON CONFLICT (course_code) DO NOTHING;

-- Historial CCD por estudiante y prueba diagnóstica
CREATE TABLE IF NOT EXISTS student_ccd_courses (
    student_id   TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_code  TEXT NOT NULL REFERENCES ccd_courses(course_code),
    status       TEXT NOT NULL CHECK (status IN ('completed', 'in_progress', 'homologated', 'failed')),
    grade        NUMERIC(3,1),
    term         TEXT NOT NULL,
    PRIMARY KEY (student_id, course_code)
);
CREATE TABLE IF NOT EXISTS ccd_diagnostics (
    student_id   TEXT PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE,
    score        INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    level        TEXT NOT NULL,
    taken_on     DATE NOT NULL
);

-- Requisitos de grado individuales (sintéticos)
ALTER TABLE students ADD COLUMN IF NOT EXISTS english_level TEXT;      -- A1, A2, B1, B2
ALTER TABLE students ADD COLUMN IF NOT EXISTS saber_pro_done BOOLEAN;
ALTER TABLE students ADD COLUMN IF NOT EXISTS grade_option TEXT;       -- proyecto, investigación, práctica, posgrado

-- Semestre actual de un estudiante (materias en curso, o siguiente al último aprobado)
CREATE OR REPLACE FUNCTION student_semester(p_session_id TEXT) RETURNS INT
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(max(semester) FILTER (WHERE status = 'in_progress'),
                    max(semester) FILTER (WHERE status = 'completed') + 1, 1)
      FROM student_courses WHERE student_session = p_session_id
$$;

-- Datos sintéticos (solo para quien aún no los tiene)
DO $$
DECLARE
    s RECORD; sem INT; n_done INT; sc INT; lvl TEXT; c RECORD; k INT;
    electives TEXT[] := ARRAY['CCD06', 'CCD05', 'CCD07'];
BEGIN
    PERFORM setseed(0.4242);
    FOR s IN SELECT st.student_id, ss.session_id, st.program
               FROM students st JOIN student_sessions ss ON ss.student_id = st.student_id
              ORDER BY st.student_id LOOP
        sem := student_semester(s.session_id);

        -- Prueba diagnóstica (todos, en su primer semestre)
        sc := 25 + floor(random() * 70)::int;
        lvl := CASE WHEN sc >= 80 THEN 'avanzado' WHEN sc >= 50 THEN 'intermedio' ELSE 'básico' END;
        INSERT INTO ccd_diagnostics VALUES (s.student_id, sc, lvl, DATE '2022-02-15' + (9 - LEAST(sem, 9)) * 182)
        ON CONFLICT (student_id) DO NOTHING;

        -- Cursos CCD: ~1 por semestre en el orden recomendado
        IF NOT EXISTS (SELECT 1 FROM student_ccd_courses WHERE student_id = s.student_id) THEN
            n_done := LEAST(sem - 1, 5) - (CASE WHEN random() < 0.25 THEN 1 ELSE 0 END);
            k := 0;
            FOR c IN SELECT * FROM ccd_courses WHERE required ORDER BY sort_order LOOP
                k := k + 1;
                IF c.course_code = 'CCD02' AND lvl = 'avanzado' THEN
                    INSERT INTO student_ccd_courses VALUES (s.student_id, c.course_code, 'homologated', NULL, 'diagnóstico');
                ELSIF k <= n_done THEN
                    INSERT INTO student_ccd_courses VALUES (s.student_id, c.course_code,
                        CASE WHEN random() < 0.06 THEN 'failed' ELSE 'completed' END,
                        round((3.2 + random() * 1.8)::numeric, 1), academic_term(current_date, -(n_done - k + 1)));
                ELSIF k = n_done + 1 AND sem > 1 AND random() < 0.5 THEN
                    INSERT INTO student_ccd_courses VALUES (s.student_id, c.course_code, 'in_progress', NULL, academic_term(current_date, 0));
                END IF;
            END LOOP;
            IF n_done >= 5 THEN
                INSERT INTO student_ccd_courses VALUES (s.student_id,
                    CASE WHEN s.program = 'Ingeniería de Sistemas' THEN 'CCD06' ELSE electives[1 + floor(random() * 3)::int] END,
                    'completed', round((3.5 + random() * 1.5)::numeric, 1), academic_term(current_date, -1))
                ON CONFLICT DO NOTHING;
            END IF;
        END IF;

        -- Requisitos de grado individuales
        UPDATE students SET
            english_level  = COALESCE(english_level, (ARRAY['A1','A2','A2','B1','B1','B2'])[LEAST(1 + sem / 2 + floor(random() * 2)::int, 6)]),
            saber_pro_done = COALESCE(saber_pro_done, sem >= 8 AND random() < 0.7),
            grade_option   = COALESCE(grade_option, CASE WHEN sem >= 7 AND random() < 0.6
                                 THEN (ARRAY['proyecto','investigación','práctica'])[1 + floor(random() * 3)::int] END)
         WHERE student_id = s.student_id;
    END LOOP;
END $$;

-- ------------------------------------------------------------ avance hacia la insignia
CREATE OR REPLACE FUNCTION ccd_progress(p_session_id TEXT) RETURNS JSONB
LANGUAGE sql STABLE AS $$
    WITH st AS (
        SELECT s.student_id, s.full_name FROM student_sessions ss JOIN students s ON s.student_id = ss.student_id
         WHERE ss.session_id = p_session_id
    ), hist AS (
        SELECT c.*, h.status, h.grade, h.term
          FROM ccd_courses c CROSS JOIN st
          LEFT JOIN student_ccd_courses h ON h.course_code = c.course_code AND h.student_id = st.student_id
    ), agg AS (
        SELECT count(*) FILTER (WHERE required AND status IN ('completed', 'homologated')) AS req_done,
               count(*) FILTER (WHERE required) AS req_total,
               count(*) FILTER (WHERE NOT required AND status = 'completed') AS elec_done
          FROM hist
    )
    SELECT jsonb_build_object(
        'student_id', (SELECT student_id FROM st),
        'diagnostic', (SELECT jsonb_build_object('score', d.score, 'level', d.level, 'taken_on', d.taken_on)
                         FROM ccd_diagnostics d JOIN st ON st.student_id = d.student_id),
        'courses', (SELECT jsonb_agg(jsonb_build_object(
                        'course_code', course_code, 'course_name', course_name, 'level', level, 'hours', hours,
                        'modality', modality, 'required', required, 'status', COALESCE(status, 'pending'),
                        'grade', grade, 'term', term) ORDER BY sort_order) FROM hist),
        'badge', (SELECT jsonb_build_object(
                        'required_done', req_done, 'required_total', req_total, 'electives_done', elec_done,
                        'earned', req_done = req_total AND elec_done >= 1,
                        'missing', (SELECT COALESCE(jsonb_agg(course_name ORDER BY sort_order), '[]'::jsonb) FROM hist
                                     WHERE required AND COALESCE(status, 'pending') NOT IN ('completed', 'homologated')),
                        'next', (SELECT course_code || ' ' || course_name FROM hist
                                  WHERE COALESCE(status, 'pending') IN ('pending', 'failed')
                                    AND (required OR (SELECT req_done FROM agg) = (SELECT req_total FROM agg))
                                  ORDER BY sort_order LIMIT 1)) FROM agg),
        'enrollment_info', 'Cursos intensivos 2026-2: inscripción y pago del 20 al 26 de noviembre en Cosmos UNAB '
                           '(Inscribirse a Clases → 2026-2do SEM CURSOS INTENSIVOS → NRC). $362.550 por curso. '
                           'Clases del 30 de noviembre al 17 de diciembre. ccdigital@unab.edu.co')
    WHERE EXISTS (SELECT 1 FROM st)
$$;

-- ------------------------------------------------------------ alertas de requisitos pendientes
CREATE OR REPLACE FUNCTION student_alerts(p_session_id TEXT) RETURNS JSONB
LANGUAGE plpgsql STABLE AS $$
DECLARE
    st RECORD; sem INT; plan JSONB; ccd JSONB; a JSONB := '[]'::jsonb; failed INT; blocked INT;
BEGIN
    SELECT s.* INTO st FROM student_sessions ss JOIN students s ON s.student_id = ss.student_id WHERE ss.session_id = p_session_id;
    IF NOT FOUND THEN RETURN '[]'::jsonb; END IF;
    sem := student_semester(p_session_id);
    plan := academic_plan(p_session_id);
    ccd := ccd_progress(p_session_id);
    failed := (plan->'status'->>'failed_courses')::int;
    blocked := jsonb_array_length(plan->'enrollment'->'blocked');

    IF plan->'status'->>'standing' = 'prueba académica' THEN
        a := a || jsonb_build_object('level', 'alta', 'type', 'situacion', 'text',
             'Estás en prueba académica: tu carga máxima es de 12 créditos y debes ir al programa de acompañamiento.');
    END IF;
    IF failed > 0 THEN
        a := a || jsonb_build_object('level', 'alta', 'type', 'reprobadas', 'text',
             format('Tienes %s materia(s) reprobada(s) por repetir; matricúlalas primero.', failed));
    END IF;
    IF blocked > 0 THEN
        a := a || jsonb_build_object('level', 'media', 'type', 'prerrequisitos', 'text',
             format('%s materia(s) bloqueada(s) por prerrequisitos pendientes.', blocked));
    END IF;
    IF NOT (ccd->'badge'->>'earned')::boolean THEN
        a := a || jsonb_build_object('level', CASE WHEN sem >= 7 THEN 'alta' ELSE 'media' END, 'type', 'insignia_ccd', 'text',
             format('Insignia de competencias digitales (requisito de grado): %s de %s cursos obligatorios del CCD aprobados%s.',
                    ccd->'badge'->>'required_done', ccd->'badge'->>'required_total',
                    COALESCE('; siguiente: ' || (ccd->'badge'->>'next'), '')));
    END IF;
    IF st.english_level IN ('A1', 'A2') AND sem >= 5 THEN
        a := a || jsonb_build_object('level', CASE WHEN sem >= 7 THEN 'alta' ELSE 'media' END, 'type', 'ingles', 'text',
             format('Inglés: tu nivel es %s y el requisito de grado es B1.', st.english_level));
    END IF;
    IF sem >= 7 AND NOT COALESCE(st.saber_pro_done, false) THEN
        a := a || jsonb_build_object('level', 'media', 'type', 'saber_pro', 'text',
             'No has presentado el examen Saber Pro (requisito de grado). Inscríbete en la próxima convocatoria del ICFES.');
    END IF;
    IF sem >= 7 AND st.grade_option IS NULL THEN
        a := a || jsonb_build_object('level', 'media', 'type', 'opcion_grado', 'text',
             'Aún no has elegido tu opción de grado (proyecto, investigación, práctica o posgrado).');
    END IF;
    RETURN a;
END;
$$;

-- ------------------------------------------------------------ vistas analíticas para agentes
-- Una fila por estudiante con lo que un agente suele preguntar (sin recorrer el historial)
CREATE OR REPLACE VIEW v_estado_estudiante AS
SELECT s.student_id, s.full_name, s.program, ss.session_id,
       student_semester(ss.session_id)                         AS semestre_actual,
       (p->'status'->>'gpa')::numeric                          AS promedio_ponderado,
       p->'status'->>'standing'                                AS situacion,
       (p->'status'->>'approved_credits')::int                 AS creditos_aprobados,
       (p->'status'->>'total_credits')::int                    AS creditos_totales,
       (p->'status'->>'progress_percentage')::numeric          AS avance_pct,
       (p->'status'->>'failed_courses')::int                   AS reprobadas,
       p->'projection'->>'estimated_graduation_term'           AS grado_estimado,
       (p->'projection'->>'terms_remaining')::int              AS periodos_restantes,
       s.english_level AS nivel_ingles, s.saber_pro_done AS saber_pro, s.grade_option AS opcion_grado
  FROM students s
  JOIN student_sessions ss ON ss.student_id = s.student_id
  CROSS JOIN LATERAL academic_plan(ss.session_id) p;

CREATE OR REPLACE VIEW v_ccd_progreso AS
SELECT s.student_id, s.full_name, s.program,
       d.score AS puntaje_diagnostico, d.level AS nivel_diagnostico,
       count(*) FILTER (WHERE c.required AND h.status IN ('completed', 'homologated')) AS obligatorios_aprobados,
       count(*) FILTER (WHERE NOT c.required AND h.status = 'completed')              AS electivos_aprobados,
       count(*) FILTER (WHERE c.required AND h.status IN ('completed', 'homologated')) = 4
         AND count(*) FILTER (WHERE NOT c.required AND h.status = 'completed') >= 1    AS tiene_insignia
  FROM students s
  LEFT JOIN ccd_diagnostics d ON d.student_id = s.student_id
  LEFT JOIN student_ccd_courses h ON h.student_id = s.student_id
  LEFT JOIN ccd_courses c ON c.course_code = h.course_code
 GROUP BY s.student_id, s.full_name, s.program, d.score, d.level;

-- Indicadores por programa (para preguntas agregadas o para el profesor)
CREATE OR REPLACE VIEW v_avance_programa AS
SELECT program AS programa, count(*) AS estudiantes,
       round(avg(promedio_ponderado), 2) AS promedio_programa,
       round(avg(avance_pct), 1) AS avance_promedio_pct,
       count(*) FILTER (WHERE situacion = 'prueba académica') AS en_prueba_academica,
       count(*) FILTER (WHERE situacion = 'excelencia') AS en_excelencia,
       count(*) FILTER (WHERE reprobadas > 0) AS con_reprobadas
  FROM v_estado_estudiante GROUP BY program;

CREATE OR REPLACE VIEW v_noticias_recientes AS
SELECT title AS titulo, category AS categoria, source_name AS fuente,
       (published_at AT TIME ZONE 'America/Bogota')::date AS fecha, image_url AS imagen, source_url AS enlace
  FROM noticias ORDER BY published_at DESC LIMIT 50;

-- ------------------------------------------------------------ calendario del CCD
INSERT INTO academic_calendar (event_name, event_date, description) VALUES
    ('Inscripciones cursos intensivos CCD (inicio)', '2026-11-20', 'Cursos vacacionales de Competencias Digitales: inscripción en Cosmos UNAB (2026-2do SEM CURSOS INTENSIVOS)'),
    ('Pago cursos intensivos CCD (cierre)', '2026-11-26', 'Fecha máxima de pago de los cursos intensivos de Competencias Digitales ($362.550 por curso)'),
    ('Inicio de cursos intensivos CCD', '2026-11-30', 'Inicio de clases de los cursos vacacionales de Competencias Digitales'),
    ('Fin de cursos intensivos CCD', '2026-12-17', 'Fin de clases de los cursos vacacionales de Competencias Digitales'),
    ('Notas de cursos intensivos CCD', '2026-12-21', 'Nota final de los cursos de Competencias Digitales en la historia académica'),
    ('Prueba diagnóstica de competencias digitales 2027-1', '2027-01-29', 'Prueba diagnóstica virtual para estudiantes nuevos (define el nivel de entrada en el CCD)'),
    ('Inscripciones cursos CCD 2027-1', '2027-01-18', 'Inscripción a los cursos regulares del Centro de Competencias Digitales en Cosmos UNAB')
ON CONFLICT DO NOTHING;
