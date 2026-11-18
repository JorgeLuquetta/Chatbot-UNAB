-- =====================================================================
-- Datos sintéticos ampliados (ejecutar DESPUÉS de schema.sql y seed.sql)
--   * Catálogo de materias (program_courses) para 4 programas
--   * 40 estudiantes sintéticos U00000003 … U00000042 (contraseña Unab2026*)
--   * Historial académico de cada uno según su semestre actual
-- Es idempotente: se puede ejecutar varias veces sin duplicar datos.
-- Los datos son ficticios; no corresponden a estudiantes reales.
-- =====================================================================

CREATE TABLE IF NOT EXISTS program_courses (
    course_code  TEXT PRIMARY KEY,
    program      TEXT NOT NULL,
    course_name  TEXT NOT NULL,
    semester     INTEGER NOT NULL,
    credits      INTEGER NOT NULL DEFAULT 3
);
CREATE INDEX IF NOT EXISTS idx_program_courses_program ON program_courses (program, semester);

INSERT INTO program_courses (course_code, program, course_name, semester, credits) VALUES
    -- Ingeniería de Sistemas (mismo plan que seed.sql)
    ('ISC101','Ingeniería de Sistemas','Cálculo Diferencial',1,4),
    ('ISC102','Ingeniería de Sistemas','Introducción a la Programación',1,4),
    ('ISC103','Ingeniería de Sistemas','Lógica y Matemáticas Discretas',1,3),
    ('ISC201','Ingeniería de Sistemas','Cálculo Integral',2,4),
    ('ISC202','Ingeniería de Sistemas','Programación Orientada a Objetos',2,4),
    ('ISC203','Ingeniería de Sistemas','Álgebra Lineal',2,3),
    ('ISC301','Ingeniería de Sistemas','Estructuras de Datos',3,4),
    ('ISC302','Ingeniería de Sistemas','Probabilidad y Estadística',3,3),
    ('ISC303','Ingeniería de Sistemas','Bases de Datos I',3,3),
    ('ISC401','Ingeniería de Sistemas','Algoritmos y Complejidad',4,3),
    ('ISC402','Ingeniería de Sistemas','Bases de Datos II',4,3),
    ('ISC403','Ingeniería de Sistemas','Arquitectura de Computadores',4,3),
    ('ISC501','Ingeniería de Sistemas','Ingeniería de Software I',5,3),
    ('ISC502','Ingeniería de Sistemas','Redes de Computadores',5,3),
    ('ISC503','Ingeniería de Sistemas','Sistemas Operativos',5,3),
    ('ISC601','Ingeniería de Sistemas','Ciencia de Datos',6,3),
    ('ISC602','Ingeniería de Sistemas','Ingeniería de Software II',6,3),
    ('ISC603','Ingeniería de Sistemas','IoT y Computación en la Nube',6,3),
    ('ISC701','Ingeniería de Sistemas','Inteligencia Artificial',7,3),
    ('ISC702','Ingeniería de Sistemas','Seguridad Informática',7,3),
    ('ISC801','Ingeniería de Sistemas','Proyecto de Grado I',8,4),
    ('ISC901','Ingeniería de Sistemas','Proyecto de Grado II',9,6),
    -- Ingeniería Industrial
    ('IND101','Ingeniería Industrial','Cálculo Diferencial',1,4),
    ('IND102','Ingeniería Industrial','Introducción a la Ingeniería Industrial',1,3),
    ('IND103','Ingeniería Industrial','Química General',1,3),
    ('IND201','Ingeniería Industrial','Cálculo Integral',2,4),
    ('IND202','Ingeniería Industrial','Física Mecánica',2,4),
    ('IND203','Ingeniería Industrial','Dibujo de Ingeniería',2,2),
    ('IND301','Ingeniería Industrial','Estadística Inferencial',3,3),
    ('IND302','Ingeniería Industrial','Procesos Industriales',3,3),
    ('IND303','Ingeniería Industrial','Contabilidad de Costos',3,3),
    ('IND401','Ingeniería Industrial','Investigación de Operaciones I',4,3),
    ('IND402','Ingeniería Industrial','Ingeniería de Métodos',4,3),
    ('IND501','Ingeniería Industrial','Investigación de Operaciones II',5,3),
    ('IND502','Ingeniería Industrial','Control de Calidad',5,3),
    ('IND601','Ingeniería Industrial','Logística y Cadena de Suministro',6,3),
    ('IND602','Ingeniería Industrial','Gestión de la Producción',6,3),
    ('IND701','Ingeniería Industrial','Seguridad y Salud en el Trabajo',7,3),
    ('IND702','Ingeniería Industrial','Formulación de Proyectos',7,3),
    ('IND801','Ingeniería Industrial','Proyecto de Grado I',8,4),
    ('IND901','Ingeniería Industrial','Proyecto de Grado II',9,6),
    -- Administración de Empresas
    ('ADM101','Administración de Empresas','Fundamentos de Administración',1,3),
    ('ADM102','Administración de Empresas','Matemáticas Básicas',1,3),
    ('ADM103','Administración de Empresas','Expresión Oral y Escrita',1,2),
    ('ADM201','Administración de Empresas','Microeconomía',2,3),
    ('ADM202','Administración de Empresas','Contabilidad Financiera',2,3),
    ('ADM203','Administración de Empresas','Matemáticas Financieras',2,3),
    ('ADM301','Administración de Empresas','Macroeconomía',3,3),
    ('ADM302','Administración de Empresas','Estadística Empresarial',3,3),
    ('ADM303','Administración de Empresas','Comportamiento Organizacional',3,3),
    ('ADM401','Administración de Empresas','Mercadeo',4,3),
    ('ADM402','Administración de Empresas','Gestión del Talento Humano',4,3),
    ('ADM501','Administración de Empresas','Finanzas Corporativas',5,3),
    ('ADM502','Administración de Empresas','Derecho Comercial',5,2),
    ('ADM601','Administración de Empresas','Planeación Estratégica',6,3),
    ('ADM602','Administración de Empresas','Negocios Internacionales',6,3),
    ('ADM701','Administración de Empresas','Emprendimiento e Innovación',7,3),
    ('ADM801','Administración de Empresas','Práctica Empresarial',8,8),
    -- Psicología
    ('PSI101','Psicología','Introducción a la Psicología',1,3),
    ('PSI102','Psicología','Biología del Comportamiento',1,3),
    ('PSI103','Psicología','Lectura y Escritura Académica',1,2),
    ('PSI201','Psicología','Procesos Psicológicos Básicos',2,3),
    ('PSI202','Psicología','Historia de la Psicología',2,3),
    ('PSI203','Psicología','Estadística Descriptiva',2,3),
    ('PSI301','Psicología','Psicología del Desarrollo',3,3),
    ('PSI302','Psicología','Neuropsicología',3,3),
    ('PSI401','Psicología','Psicología Social',4,3),
    ('PSI402','Psicología','Psicometría',4,3),
    ('PSI501','Psicología','Psicopatología',5,3),
    ('PSI502','Psicología','Psicología Educativa',5,3),
    ('PSI601','Psicología','Evaluación Psicológica',6,3),
    ('PSI602','Psicología','Psicología Organizacional',6,3),
    ('PSI701','Psicología','Psicología Clínica',7,3),
    ('PSI801','Psicología','Práctica Profesional I',8,6),
    ('PSI901','Psicología','Práctica Profesional II',9,6),
    ('PSI902','Psicología','Trabajo de Grado',9,4)
ON CONFLICT (course_code) DO NOTHING;

-- Estudiantes sintéticos con historial. Semilla fija = mismos datos en cada instalación.
DO $$
DECLARE
    nombres   TEXT[] := ARRAY['Valentina','Santiago','Camila','Sebastián','Daniela','Andrés','Laura','Juan David',
                              'Mariana','Felipe','Sofía','Nicolás','Isabella','Mateo','Paula','Diego','Natalia',
                              'Alejandro','Gabriela','Julián','Manuela','Samuel','Juliana','Tomás'];
    apellidos TEXT[] := ARRAY['Gómez','Rodríguez','Martínez','Hernández','López','García','Díaz','Moreno','Suárez',
                              'Rincón','Castillo','Vargas','Ortiz','Rueda','Serrano','Pinzón','Arenas','Quintero',
                              'Mantilla','Cáceres','Duarte','Jaimes','Rojas','Prada'];
    programas TEXT[] := ARRAY['Ingeniería de Sistemas','Ingeniería Industrial','Administración de Empresas','Psicología'];
    i INT; sid TEXT; sess TEXT; prog TEXT; sem INT; max_sem INT; nombre TEXT;
    c RECORD; nota NUMERIC;
BEGIN
    PERFORM setseed(0.2026);
    FOR i IN 3..42 LOOP
        sid    := 'U' || lpad(i::text, 8, '0');
        sess   := 'sess_' || lower(sid);
        prog   := programas[1 + (i % 4)];
        nombre := nombres[1 + ((i * 5) % array_length(nombres, 1))] || ' ' ||
                  apellidos[1 + ((i * 7) % array_length(apellidos, 1))] || ' ' ||
                  apellidos[1 + ((i * 11 + 3) % array_length(apellidos, 1))];
        SELECT max(semester) INTO max_sem FROM program_courses WHERE program = prog;
        sem := 1 + floor(random() * max_sem)::int;   -- semestre actual

        INSERT INTO students (student_id, full_name, program, password_hash)
        VALUES (sid, nombre, prog, crypt('Unab2026*', gen_salt('bf')))
        ON CONFLICT (student_id) DO NOTHING;

        INSERT INTO student_sessions (session_id, student_id, token_hash, expires_at)
        VALUES (sess, sid, 'sin-token', now())
        ON CONFLICT (student_id) DO NOTHING;
        SELECT ss.session_id INTO sess FROM student_sessions ss WHERE ss.student_id = sid;

        FOR c IN SELECT * FROM program_courses WHERE program = prog ORDER BY semester, course_code LOOP
            IF c.semester < sem THEN
                nota := round((3.0 + random() * 2.0)::numeric, 1);
                IF random() < 0.07 THEN
                    -- Materia reprobada: queda pendiente de repetir, con la nota obtenida
                    INSERT INTO student_courses (student_session, course_code, course_name, semester, status, grade)
                    VALUES (sess, c.course_code, c.course_name, c.semester, 'pending', round((1.5 + random() * 1.4)::numeric, 1))
                    ON CONFLICT (student_session, course_code) DO NOTHING;
                ELSE
                    INSERT INTO student_courses (student_session, course_code, course_name, semester, status, grade)
                    VALUES (sess, c.course_code, c.course_name, c.semester, 'completed', nota)
                    ON CONFLICT (student_session, course_code) DO NOTHING;
                END IF;
            ELSIF c.semester = sem THEN
                INSERT INTO student_courses (student_session, course_code, course_name, semester, status, grade)
                VALUES (sess, c.course_code, c.course_name, c.semester, 'in_progress', NULL)
                ON CONFLICT (student_session, course_code) DO NOTHING;
            ELSE
                INSERT INTO student_courses (student_session, course_code, course_name, semester, status, grade)
                VALUES (sess, c.course_code, c.course_name, c.semester, 'pending', NULL)
                ON CONFLICT (student_session, course_code) DO NOTHING;
            END IF;
        END LOOP;
    END LOOP;
END $$;
