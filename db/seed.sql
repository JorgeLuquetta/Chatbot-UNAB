-- =====================================================================
-- Datos sintéticos de prueba (ejecutar DESPUÉS de schema.sql)
-- Usuarios de prueba:
--   U00000001 / Unab2026*   (Ana María Rojas, 6.º semestre)
--   U00000002 / Unab2026*   (Carlos Pérez, 3.er semestre)
-- =====================================================================

INSERT INTO students (student_id, full_name, password_hash) VALUES
    ('U00000001', 'Ana María Rojas', crypt('Unab2026*', gen_salt('bf'))),
    ('U00000002', 'Carlos Pérez',    crypt('Unab2026*', gen_salt('bf')))
ON CONFLICT (student_id) DO NOTHING;

-- Sesiones con session_id fijo para poder asociar cursos.
-- El token real se genera en el primer login (login_student rota el hash).
INSERT INTO student_sessions (session_id, student_id, token_hash, expires_at) VALUES
    ('sess_demo_ana',    'U00000001', 'sin-token', now()),
    ('sess_demo_carlos', 'U00000002', 'sin-token', now())
ON CONFLICT (student_id) DO NOTHING;

-- Plan de estudios de ejemplo (Ingeniería de Sistemas)
WITH plan(course_code, course_name, semester) AS (VALUES
    ('ISC101', 'Cálculo Diferencial', 1),
    ('ISC102', 'Introducción a la Programación', 1),
    ('ISC103', 'Lógica y Matemáticas Discretas', 1),
    ('ISC201', 'Cálculo Integral', 2),
    ('ISC202', 'Programación Orientada a Objetos', 2),
    ('ISC203', 'Álgebra Lineal', 2),
    ('ISC301', 'Estructuras de Datos', 3),
    ('ISC302', 'Probabilidad y Estadística', 3),
    ('ISC303', 'Bases de Datos I', 3),
    ('ISC401', 'Algoritmos y Complejidad', 4),
    ('ISC402', 'Bases de Datos II', 4),
    ('ISC403', 'Arquitectura de Computadores', 4),
    ('ISC501', 'Ingeniería de Software I', 5),
    ('ISC502', 'Redes de Computadores', 5),
    ('ISC503', 'Sistemas Operativos', 5),
    ('ISC601', 'Ciencia de Datos', 6),
    ('ISC602', 'Ingeniería de Software II', 6),
    ('ISC603', 'IoT y Computación en la Nube', 6),
    ('ISC701', 'Inteligencia Artificial', 7),
    ('ISC702', 'Seguridad Informática', 7),
    ('ISC801', 'Proyecto de Grado I', 8),
    ('ISC901', 'Proyecto de Grado II', 9)
)
INSERT INTO student_courses (student_session, course_code, course_name, semester, status, grade)
SELECT 'sess_demo_ana', course_code, course_name, semester,
       CASE WHEN semester <= 5 THEN 'completed' WHEN semester = 6 THEN 'in_progress' ELSE 'pending' END,
       CASE WHEN semester <= 5 THEN round((3.5 + random() * 1.5)::numeric, 2) END
  FROM plan
UNION ALL
SELECT 'sess_demo_carlos', course_code, course_name, semester,
       CASE WHEN semester <= 2 THEN 'completed' WHEN semester = 3 THEN 'in_progress' ELSE 'pending' END,
       CASE WHEN semester <= 2 THEN round((3.0 + random() * 2.0)::numeric, 2) END
  FROM plan
ON CONFLICT (student_session, course_code) DO NOTHING;

-- Noticias de ejemplo (el scraper agregará las reales)
INSERT INTO noticias (title, published_at, summary, source_url) VALUES
    ('Abiertas inscripciones para semilleros de investigación', now() - interval '2 days',
     'La Facultad de Ingeniería invita a los estudiantes a inscribirse en los semilleros de investigación del semestre.',
     'https://www.unab.edu.co/ejemplo/semilleros-investigacion'),
    ('Semana de la Ingeniería 2026', now() - interval '5 days',
     'Charlas, talleres y concursos de programación durante la Semana de la Ingeniería en el campus El Jardín.',
     'https://www.unab.edu.co/ejemplo/semana-ingenieria')
ON CONFLICT (source_url) DO NOTHING;
