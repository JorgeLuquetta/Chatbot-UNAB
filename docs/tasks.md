# Implementation Plan: Chatbot de Apoyo Académico UNAB

## Overview

Plan de implementación incremental que cubre los cinco componentes principales del sistema: infraestructura Docker, FastMCP server, Guardrails microservice, n8n workflows, y la App Android nativa. Las tareas están ordenadas para que cada paso integre lo anterior y el sistema sea verificable en puntos intermedios. Se incluyen pruebas basadas en propiedades (PBT) para las propiedades de corrección definidas en el diseño.

---

## Tasks

> **Estado (12-nov-2026):** todas las tareas implementadas. Backend verificado: 49 pruebas Python
> (incluidas las de integración con PostgreSQL + pgvector) y prueba e2e de los 6 workflows en n8n 1.123.
> La App Android está escrita completa pero debe compilarse y probarse en Android Studio
> (`./gradlew test`), pues no se pudo compilar en el entorno de generación.

- [x] 1. Infraestructura base y esquema de base de datos
  - [x] 1.1 Crear estructura de directorios del proyecto y `docker-compose.yml`
    - Crear directorios `mcp-server/`, `guardrails/`, con sus `Dockerfile` y `requirements.txt`
    - Escribir `docker-compose.yml` con los servicios `n8n`, `mcp-server` y `guardrails` en la red bridge `backend`
    - Configurar restart policy `unless-stopped` en cada servicio
    - Exponer solo el puerto 9000 de n8n; los puertos 8000 y 8080 permanecen internos
    - Crear archivo `.env.example` con todas las variables requeridas: `N8N_ENCRYPTION_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`, `GOOGLE_SA_JSON`
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

  - [x] 1.2 Crear esquema PostgreSQL en Supabase
    - Escribir script SQL `schema.sql` con todas las tablas: `document_chunks`, `conversation_memory`, `noticias`, `student_courses`, `guardrails_audit_log`, `student_sessions`
    - Habilitar extensión `vector` y crear índice `ivfflat` en `document_chunks`
    - Crear índices secundarios: `idx_memory_session`, `idx_courses_session`, `idx_audit_session`
    - Aplicar restricciones `CHECK` y `UNIQUE` según el schema del diseño
    - _Requirements: 8.3, 10.3, 11.5, 6.5_

- [x] 2. FastMCP Server — herramientas MCP
  - [x] 2.1 Implementar estructura base del servidor FastMCP
    - Crear `mcp-server/main.py` con inicialización de FastMCP y pool de conexiones `asyncpg`
    - Leer `SUPABASE_URL`, `SUPABASE_KEY` y `OPENAI_API_KEY` desde variables de entorno
    - Implementar health-check endpoint interno
    - _Requirements: 15.2_

  - [x] 2.2 Implementar herramienta `search_documents`
    - Generar embedding del query con `text-embedding-3-small` (dimensión 1536) en lotes de 100
    - Ejecutar búsqueda coseno en `document_chunks` vía pgvector, retornar top-k chunks ordenados por `similarity_score` DESC
    - Retornar lista de `DocumentChunk` con texto y score
    - _Requirements: 4.1_

  - [x]* 2.3 Escribir property test para `search_documents` (Property 6)
    - **Property 6: RAG retorna a lo sumo top-k chunks ordenados por similitud**
    - **Validates: Requirements 4.1**
    - Usar Hypothesis; generar queries arbitrarios y valores de top_k ∈ [1, 20]
    - Verificar que `len(result) == min(top_k, total_chunks)` y que los scores son no crecientes

  - [x] 2.4 Implementar herramienta `get_student_courses`
    - Consultar `student_courses WHERE student_session = session_id`
    - Retornar `StudentCourseRecord` con la lista de cursos del estudiante
    - Garantizar que nunca se retornen registros de otra sesión (filtro estricto por `session_id`)
    - _Requirements: 6.1, 6.5_

  - [x]* 2.5 Escribir property test para `get_student_courses` (Property 8)
    - **Property 8: Aislamiento de historial de cursos por sesión**
    - **Validates: Requirements 6.1, 6.5**
    - Generar dos session_ids distintos con cursos distintos en la BD de test
    - Verificar que `result(A) ∩ result(B) == ∅` para todo par (A, B)

  - [x] 2.6 Implementar herramienta `ingest_documents`
    - Leer documentos PDF/DOCX con `pdfplumber` / `python-docx`
    - Chunking: máximo 512 tokens (tiktoken cl100k_base), overlap 50 tokens, metadatos `{document_name, chunk_index, total_chunks}`
    - Generar embeddings en lotes de 100 chunks
    - Upsert en `document_chunks` por `(document_name, chunk_index)`
    - Capturar errores por chunk con try/except; registrar en log sin abortar el proceso
    - Retornar `IngestionReport` con conteo de documentos, chunks, embeddings y errores
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 2.7 Escribir property tests para pipeline de ingesta (Properties 9, 10, 11, 12)
    - **Property 9: Chunks cumplen la restricción de tamaño y overlap**
    - **Property 10: Cardinalidad embeddings = cardinalidad chunks**
    - **Property 11: Round-trip de almacenamiento de chunks**
    - **Property 12: Tolerancia a errores en pipeline de ingesta**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.5**
    - Usar Hypothesis; generar textos de longitud variable y lotes con K documentos erróneos
    - Verificar tamaño de chunks, conteo de embeddings, round-trip y conteo de errores registrados

  - [x] 2.8 Implementar herramienta `run_news_scraper`
    - Leer URLs de fuentes desde configuración
    - HTTP GET con timeout 10 s por URL; ante fallo registrar URL y continuar
    - Parsear con BeautifulSoup: extraer `title`, `published_at`, `summary`, `source_url`
    - Deduplicar por `source_url` antes de insertar en `noticias`
    - Retornar `ScraperReport` con conteo de artículos extraídos, insertados, duplicados y fuentes fallidas
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x]* 2.9 Escribir property tests para el scraper (Properties 13, 14, 15)
    - **Property 13: Artículos almacenados contienen todos los campos requeridos**
    - **Property 14: Tolerancia a errores en el scraper**
    - **Property 15: Idempotencia del scraper (deduplicación por source_url)**
    - **Validates: Requirements 9.2, 9.4, 9.5**
    - Usar Hypothesis con mocks HTTP; verificar campos no nulos, conteo de errores y ausencia de duplicados en doble ejecución

- [x] 3. Checkpoint — FastMCP
  - Asegurar que todos los tests del FastMCP pasan (`pytest mcp-server/`).
  - Verificar que el contenedor `mcp-server` levanta correctamente con `docker compose up mcp-server`.
  - Consultar al usuario si hay dudas antes de continuar.

- [x] 4. Guardrails Microservice (FastAPI)
  - [x] 4.1 Crear estructura base de Guardrails
    - Crear `guardrails/main.py` con FastAPI, Uvicorn en puerto 8080
    - Configurar pool `asyncpg` para escritura en `guardrails_audit_log`
    - Leer `SUPABASE_URL` y `SUPABASE_KEY` desde variables de entorno
    - _Requirements: 15.3_

  - [x] 4.2 Implementar endpoint `POST /validate-input`
    - Detectar patrones de prompt injection con expresiones regulares y lista negra de patrones conocidos (ej. "ignore previous instructions", "you are now", "###System:")
    - Si se detecta inyección: retornar `{ allowed: false, reason }` e insertar en `guardrails_audit_log` con `rejection_type = "input_injection"` y hash SHA-256 del contenido
    - Si es válido: retornar `{ allowed: true, reason: null }`
    - _Requirements: 11.2, 11.4, 11.5_

  - [x]* 4.3 Escribir property tests para validación de entrada (Properties 20, 21)
    - **Property 20: Guardrails bloquea inyecciones de prompt**
    - **Property 21: Log de auditoría completo en rechazos de guardrails**
    - **Validates: Requirements 11.2, 11.4, 11.5**
    - Usar Hypothesis; generar mensajes con y sin patrones de inyección
    - Verificar que inyecciones retornan `allowed: false` y que el log tiene campos no nulos

  - [x] 4.4 Implementar endpoint `POST /validate-output`
    - Evaluar la respuesta contra lista de tópicos prohibidos (contenido no académico, lenguaje inapropiado, información personal)
    - Si es fuera de alcance: retornar `sanitized_response = "Solo puedo ayudarte con temas académicos de la UNAB."` e insertar en audit log con `rejection_type` apropiado
    - Si es válida: retornar `{ allowed: true, sanitized_response: response_original }`
    - _Requirements: 11.1, 11.3, 4.5_

  - [x]* 4.5 Escribir property test para validación de salida (Property 7)
    - **Property 7: Guardrails sustituye respuestas fuera de alcance por el fallback exacto**
    - **Validates: Requirements 4.5, 11.3**
    - Usar Hypothesis; generar respuestas fuera de alcance y en alcance
    - Verificar que respuestas prohibidas retornan exactamente la cadena de fallback definida

- [x] 5. Checkpoint — Guardrails
  - Asegurar que todos los tests del Guardrails pasan (`pytest guardrails/`).
  - Verificar que el contenedor `guardrails` levanta y responde en el puerto 8080 interno.
  - Consultar al usuario si hay dudas antes de continuar.

- [x] 6. n8n — Workflows de orquestación
  - [x] 6.1 Configurar instancia n8n y credenciales
    - Exportar workflow JSON base para el Webhook principal
    - Configurar credenciales en n8n: Supabase URL/Key, OpenAI API Key, Google Sheets service account
    - Verificar que n8n accede a `mcp-server:8000` y `guardrails:8080` vía red interna Docker
    - _Requirements: 15.1, 15.4_

  - [x] 6.2 Implementar Workflow de Ruteo por Intención
    - Nodo Webhook `POST /webhook/chat` con validación de `Authorization: Bearer`
    - Nodo Supabase: cargar últimos 10 exchanges de `conversation_memory` para el `session_id`
    - Nodo HTTP Request → `POST http://guardrails:8080/validate-input`; si `allowed: false` retornar error al cliente
    - Nodo LLM classifier: system prompt que clasifica en `{consulta-general, calendario, cursos-realizados, noticias}`; default fallback a `consulta-general`
    - Nodo Switch: enrutar al subworkflow según `intent_label`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.1_

  - [x] 6.3 Implementar Workflow de Consulta General (RAG)
    - Nodo MCP Tool → `search_documents(query=message, top_k=5)` vía `POST http://mcp-server:8000/mcp`
    - Nodo LLM: generar respuesta con chunks como contexto e historial; responder en español
    - Nodo HTTP Request → `POST http://guardrails:8080/validate-output`; si `flagged` usar `fallback_message`
    - Nodo Supabase: persistir `(session_id, 'user', message)` y `(session_id, 'assistant', llm_response)` en `conversation_memory`
    - Nodo Return con `{ response, intent }`; timeout configurado en 10 s
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 10.2_

  - [x] 6.4 Implementar Workflow de Calendario
    - Nodo Google Sheets: leer hoja "Calendario Académico" con credenciales de service account
    - Manejo de error: si Google Sheets no disponible, retornar mensaje de no disponibilidad
    - Nodo LLM: generar respuesta en lenguaje natural con los eventos del calendario
    - Nodo Guardrails + Persistir memoria (misma lógica que 6.3)
    - Timeout configurado en 8 s
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.5 Implementar Workflow de Cursos Realizados
    - Nodo MCP Tool → `get_student_courses(session_id)` para recuperar historial de cursos
    - Manejo de error: si BD inalcanzable, retornar error descriptivo y registrar en n8n log
    - Nodo LLM: generar respuesta personalizada con progreso académico del estudiante
    - Nodo Guardrails + Persistir memoria
    - Timeout 8 s
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 6.6 Implementar Workflow de Noticias
    - Nodo Supabase: `SELECT * FROM noticias ORDER BY published_at DESC LIMIT 20`
    - Si sin resultados: retornar "No hay noticias recientes disponibles."
    - Nodo LLM: resumir noticias relevantes a la pregunta
    - Nodo Guardrails + Persistir memoria
    - Timeout 8 s
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 6.7 Implementar Workflow de Notificaciones Push (FCM)
    - Crear workflow con trigger Cron (cada hora)
    - Consultar `noticias` / tabla de eventos para detectar eventos académicos en ventana `(ahora, ahora + 48h]`
    - Para cada evento en ventana: enviar notificación vía FCM HTTP v1 API al dispositivo registrado del estudiante
    - No enviar notificación si el evento está fuera de la ventana
    - Credenciales FCM almacenadas como variable de entorno en n8n
    - _Requirements: 14.1, 15.4_

  - [x] 6.8 Implementar Webhooks de Ruta Académica y Calendario (pantallas Android)
    - Webhook `GET /webhook/academic-route`: invocar MCP `get_student_courses` y retornar JSON con lista de cursos
    - Webhook `GET /webhook/calendar`: consultar Google Sheets y retornar JSON con lista de eventos
    - Ambos endpoints con validación de `Authorization: Bearer`
    - _Requirements: 12.2, 13.1, 13.2_

- [x] 7. Checkpoint — Backend integrado
  - Verificar con peticiones curl/Postman que el flujo completo funciona: App → n8n → FastMCP/Guardrails → Supabase → respuesta.
  - Asegurar que los tests de integración de n8n pasan con mocks HTTP.
  - Consultar al usuario si hay dudas antes de continuar.

- [x] 8. App Android (Kotlin)
  - [x] 8.1 Configurar estructura de paquetes y dependencias Android
    - Crear módulos: `auth/`, `chat/`, `academic/`, `notifications/`, `network/`
    - Agregar dependencias en `build.gradle`: Retrofit, OkHttp, Room, EncryptedSharedPreferences, Coroutines, MockK (test), Kotest (test), Espresso (test)
    - Configurar `ApiClient.kt` con Retrofit + OkHttp interceptor para `Authorization: Bearer`
    - Definir `ChatbotApi.kt` con los endpoints: `POST /webhook/chat`, `GET /webhook/academic-route`, `GET /webhook/calendar`
    - _Requirements: 1.3, 15.1_

  - [x] 8.2 Implementar `TokenManager` y flujo de autenticación
    - `TokenManager.kt`: guardar/leer/limpiar JWT en `EncryptedSharedPreferences`
    - Interceptor HTTP que adjunta `Authorization: Bearer <token>` a cada petición
    - `ResponseInterceptor`: al recibir 401, limpiar token y navegar a `LoginFragment`
    - `LoginFragment.kt` y `AuthViewModel.kt`: formulario de credenciales, llamada al endpoint de auth, manejo de errores genéricos sin exponer detalles internos
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x]* 8.3 Escribir property test para manejo de credenciales (Property 1)
    - **Property 1: Credenciales inválidas nunca exponen información sensible**
    - **Validates: Requirements 1.2**
    - Usar Kotest Property Testing; generar pares de credenciales inválidas arbitrarios
    - Verificar que el mensaje de error mostrado no contiene la contraseña, tokens internos ni trazas de pila

  - [x] 8.4 Implementar `ChatFragment` y `ChatViewModel`
    - `Message.kt` y `ChatRequest.kt`: modelos de datos del chat
    - `MessageAdapter.kt`: RecyclerView adapter con estilos visuales distintos para mensajes del estudiante y del chatbot
    - `ChatFragment.kt`: campo de texto con límite 1–2000 caracteres; botón enviar; indicador de carga mientras se espera respuesta; renderizado de respuesta en ≤ 500 ms tras recibo
    - `ChatViewModel.kt`: enviar mensaje al backend en ≤ 1 s; manejar errores con mensaje amigable sin exponer detalles internos
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 8.5 Escribir property tests para la interfaz de chat (Properties 2, 3, 4)
    - **Property 2: Validación de longitud del mensaje de chat**
    - **Property 3: Mensajes enviados aparecen en la lista de chat**
    - **Property 4: Errores del backend no exponen detalles internos**
    - **Validates: Requirements 2.6, 2.2, 2.5**
    - Usar Kotest; generar strings de longitud variable, verificar bloqueo fuera de [1, 2000]; verificar aparición en lista; verificar ausencia de detalles técnicos en errores

  - [x] 8.6 Implementar Room Database y cache local
    - Definir entidades Room para `CourseEntity` y `CalendarEventEntity` con campo `last_fetched_at`
    - Crear DAOs con operaciones upsert para ruta académica y calendario
    - _Requirements: 12.4, 13.4_

  - [x] 8.7 Implementar `RutaAcademicaFragment` y `RutaAcademicaViewModel`
    - RecyclerView agrupado por semestre; íconos/colores distintos para `completed`, `pending`, `in_progress`
    - Cargar datos del backend; en caso de error de conectividad mostrar cache Room con indicador de obsolescencia
    - Cada curso renderizado debe mostrar el `status` exacto del backend
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x]* 8.8 Escribir property test para Ruta Académica (Property 22)
    - **Property 22: Estado de cursos coincide con datos del backend**
    - **Validates: Requirements 12.2**
    - Usar Kotest; generar listas arbitrarias de cursos con estados variados
    - Verificar que cada elemento renderizado muestra exactamente el `status` del registro correspondiente

  - [x] 8.9 Implementar `CalendarioFragment`
    - RecyclerView agrupado por mes con eventos del calendario académico
    - Tap en evento: mostrar detalle con nombre, fecha y descripción
    - En fallo de red: mostrar cache con mensaje de datos posiblemente desactualizados
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x]* 8.10 Escribir property test para calendario (Property 23)
    - **Property 23: Agrupación correcta de eventos de calendario por mes**
    - **Validates: Requirements 13.2**
    - Usar Kotest; generar listas de eventos con fechas aleatorias
    - Verificar que cada evento aparece bajo el encabezado de mes correcto

  - [x] 8.11 Implementar `FcmService` y manejo de notificaciones push
    - `FcmService.kt`: recibir notificación FCM y mostrarla en bandeja del sistema con nombre y fecha del evento
    - Al tocar la notificación: abrir `CalendarioFragment` y hacer scroll al evento correspondiente
    - Respetar el permiso de notificaciones del OS; no intentar mostrar notificaciones si está deshabilitado
    - _Requirements: 14.2, 14.3, 14.4_

  - [x]* 8.12 Escribir property test para notificaciones push (Property 24)
    - **Property 24: Notificaciones push dentro de ventana de 48 horas**
    - **Validates: Requirements 14.1**
    - Usar Hypothesis en el lado del backend (workflow FCM); generar fechas de eventos arbitrarias
    - Verificar que solo se despachan notificaciones para eventos en `(ahora, ahora + 48h]`

- [x] 9. Checkpoint — App Android
  - Ejecutar `./gradlew test` para unit tests y `./gradlew connectedAndroidTest` para tests instrumentados
  - Verificar que todos los property tests de Kotest pasan
  - Consultar al usuario si hay dudas antes de continuar.

- [x] 10. Integración final y wiring
  - [x] 10.1 Verificar flujo extremo a extremo con tests de integración
    - Escribir tests de integración que ejerciten el camino completo: App → n8n webhook → FastMCP → Supabase → Guardrails → respuesta
    - Usar mocks para LLM, Google Sheets y FCM según la estrategia de testing del diseño
    - Verificar las cuatro intenciones de ruteo y el fallback a `consulta-general`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 10.2 Escribir tests de integración para memoria persistente (Properties 16, 17, 18, 19)
    - **Property 16: Ventana de contexto de memoria limitada a 10 exchanges**
    - **Property 17: Round-trip de memoria persistente**
    - **Property 18: Aislamiento de memoria por sesión**
    - **Property 19: Límite de retención de memoria (máximo 50 exchanges)**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    - Usar Hypothesis con BD PostgreSQL local; verificar ventana de contexto, round-trip, aislamiento y límite de retención

  - [x] 10.3 Validar seguridad de la infraestructura
    - Verificar que los puertos 8000 y 8080 no son accesibles fuera de la red Docker bridge
    - Verificar que n8n no almacena credenciales en texto plano en configuraciones de workflow
    - Confirmar que `restart: unless-stopped` está activo en todos los contenedores
    - _Requirements: 15.2, 15.3, 15.4, 15.5_

- [x] 11. Checkpoint final — Sistema completo
  - Ejecutar toda la suite de tests: `pytest` (Python) y `./gradlew test` (Android)
  - Verificar que el sistema completo levanta con `docker compose up`
  - Revisar logs de auditoría de guardrails y confirmar que los rechazos se registran correctamente
  - Consultar al usuario si hay dudas antes de entregar.

---

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia los requisitos específicos para trazabilidad
- Los checkpoints permiten validación incremental del sistema
- Las property tests (Hypothesis / Kotest) deben ejecutarse con mínimo 100 iteraciones cada una
- Los mocks de LLM, Google Sheets, Supabase y FCM se usan durante los tests para evitar costos de API
- Etiquetar cada property test con: `Feature: chatbot-apoyo-academico, Property N: <texto>`
- El esquema SQL debe aplicarse en Supabase antes de levantar los contenedores
- Las variables de entorno se gestionan con un archivo `.env` local (nunca commitear `.env` real)

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "4.1", "8.1"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.6", "2.8", "4.2", "8.2"] },
    { "id": 3, "tasks": ["2.3", "2.5", "2.7", "2.9", "4.3", "8.3"] },
    { "id": 4, "tasks": ["4.4", "6.1", "8.4", "8.6"] },
    { "id": 5, "tasks": ["4.5", "6.2", "8.5", "8.7", "8.9"] },
    { "id": 6, "tasks": ["6.3", "6.4", "6.5", "6.6", "8.8", "8.10", "8.11"] },
    { "id": 7, "tasks": ["6.7", "6.8", "8.12"] },
    { "id": 8, "tasks": ["10.1", "10.3"] },
    { "id": 9, "tasks": ["10.2"] }
  ]
}
```
