# Evidencias de prueba

Generado el 2026-11-20 00:08 UTC con `tests/e2e/evidencias.sh` contra `http://localhost:9000/webhook`.
Estudiante de prueba: `U00000010` (datos sintéticos).

| # | Prueba | Petición | HTTP | Tiempo | Archivo |
|---|---|---|---|---|---|
| 1 | Buscar estudiante por ID | `POST /student-lookup` | 200 | 0.3 s | [01_lookup.json](01_lookup.json) |
| 2 | Ruta académica (cursos) | `GET /academic-route?student_id=U00000010` | 200 | 0.2 s | [02_ruta.json](02_ruta.json) |
| 3 | Plan académico (matrícula, estado, proyección, recomendaciones) | `GET /academic-plan?student_id=U00000010` | 200 | 0.2 s | [03_plan.json](03_plan.json) |
| 4 | Calendario académico (PostgreSQL) | `GET /calendar?student_id=U00000010` | 200 | 0.2 s | [04_calendario.json](04_calendario.json) |
| 5 | Noticias de ingeniería de sistemas | `GET /news?category=ingenieria-sistemas&limit=5` | 200 | 0.1 s | [05_noticias.json](05_noticias.json) |
| 6 | Chat: matrícula | `POST /chat` | 200 | 63.7 s | [06_chat_matricula.json](06_chat_matricula.json) |
| 7 | Chat: estado académico | `POST /chat` | 200 | 102.9 s | [07_chat_estado.json](07_chat_estado.json) |
| 8 | Chat: proyección de grado | `POST /chat` | 200 | 210.2 s | [08_chat_proyeccion.json](08_chat_proyeccion.json) |
| 9 | Chat: recomendaciones | `POST /chat` | 200 | 243.5 s | [09_chat_recomendaciones.json](09_chat_recomendaciones.json) |
| 10 | Chat: RAG reglamento (habilitación) | `POST /chat` | 200 | 218.4 s | [10_chat_rag.json](10_chat_rag.json) |
| 11 | Chat: RAG requisitos de grado | `POST /chat` | 200 | 235.8 s | [11_chat_requisitos.json](11_chat_requisitos.json) |
| 12 | Chat: noticias de tecnología | `POST /chat` | 504 | 241.4 s | [12_chat_noticias.json](12_chat_noticias.json) |
| 13 | Chat: fechas de matrícula | `POST /chat` | 200 | 214.2 s | [13_chat_calendario.json](13_chat_calendario.json) |
| 14 | Correo: pedir informe de avance (muestra el correo registrado) | `POST /chat` | 200 | 60.7 s | [14_correo_pedir.json](14_correo_pedir.json) |
| 15 | Correo: confirmar con sí (envía) | `POST /chat` | 200 | 1.0 s | [15_correo_confirmar.json](15_correo_confirmar.json) |
| 16 | Correo: noticias de tecnología con imágenes | `POST /chat` | 200 | 3.0 s | [16_correo_noticias.json](16_correo_noticias.json) |
| 17 | Correo: actualizar el correo y enviar | `POST /chat` | 200 | 3.8 s | [17_correo_cambiar.json](17_correo_cambiar.json) |
| 18 | Correo: contenido no permitido | `POST /chat` | 400 | 0.2 s | [18_correo_no_permitido.json](18_correo_no_permitido.json) |
| 19 | Guardrails: operación matemática | `POST /chat` | 400 | 0.2 s | [19_guardrail_suma.json](19_guardrail_suma.json) |
| 20 | Guardrails: hacer una tarea | `POST /chat` | 400 | 0.2 s | [20_guardrail_tarea.json](20_guardrail_tarea.json) |
| 21 | Guardrails: tema no académico | `POST /chat` | 400 | 0.2 s | [21_guardrail_tema.json](21_guardrail_tema.json) |
| 22 | Guardrails: prompt injection | `POST /chat` | 400 | 0.2 s | [22_guardrail_inyeccion.json](22_guardrail_inyeccion.json) |
| 23 | Agente IA (AI Agent + MCP + memoria) | `POST /agent` | 000 | 300.0 s | [23_agente.json](23_agente.json) |

## Servidor MCP

### tools/list (protocolo MCP, streamable HTTP)
```json
[
  {
    "name": "search_documents",
    "description": "Genera el embedding del query y busca por similitud coseno en pgvector."
  },
  {
    "name": "get_student_courses",
    "description": "Historial de cursos del estudiante asociado a session_id (aislamiento estricto)."
  },
  {
    "name": "ingest_documents",
    "description": "Ingesta de documentos CCD: chunking (CHUNK_MAX_TOKENS / CHUNK_OVERLAP; 220 / 30 en docker-compose)"
  },
  {
    "name": "run_news_scraper",
    "description": "Scraping one-shot de fuentes UNAB con deduplicación por source_url."
  },
  {
    "name": "get_academic_plan",
    "description": "Plan académico personalizado del estudiante (ID tipo U00000010, o session_id):"
  },
  {
    "name": "get_academic_calendar",
    "description": "Calendario académico UNAB (matrículas, parciales, finales, inicio y fin de clases)."
  },
  {
    "name": "get_news",
    "description": "Noticias recientes con fuente y fecha. category: educacion | tecnologia |"
  }
]
[
  {
    "document": "reglamento_estudiantil.md",
    "chunk": 3,
    "score": 0.739,
    "text": "ación por causa justificada (incapacidad médica, calamidad doméstica o representación institucional) puede solicitar un supletorio dentro de los cinco días hábi…"
  },
  {
    "document": "plan_estudios_ingenieria_sistemas.md",
    "chunk": 6,
    "score": 0.656,
    "text": " de la cadena (por ejemplo Estructuras de Datos) retrasa todas las materias que dependen de ella, por eso se recomienda matricular primero las materias reprobad…"
  },
  {
    "document": "reglamento_estudiantil.md",
    "chunk": 2,
    "score": 0.652,
    "text": " que materias nuevas de semestres superiores.\n\nArtículo 5. Ajustes de matrícula. El estudiante puede adicionar o retirar materias hasta la fecha de ajustes de m…"
  }
]
```

### RAG: chunks en pgvector
```
            document_name             | chunks | caracteres_promedio 
--------------------------------------+--------+---------------------
 guia_exito_academico.md              |      5 |                 813
 plan_estudios_ingenieria_sistemas.md |      7 |                 665
 reglamento_estudiantil.md            |      8 |                 764
 requisitos_de_grado.md               |      4 |                 719
(4 rows)

```

### Base de datos: tablas y filas
```
        tabla         | filas 
----------------------+-------
 academic_calendar    |    12
 conversation_memory  |    14
 course_prerequisites |    69
 device_tokens        |     0
 document_chunks      |    24
 email_requests       |     7
 guardrails_audit_log |    20
 n8n_chat_histories   |     0
 noticias             |    48
 notifications_sent   |     0
 program_courses      |    76
 student_courses      |   804
 student_sessions     |    42
 students             |    42
(14 rows)

```
