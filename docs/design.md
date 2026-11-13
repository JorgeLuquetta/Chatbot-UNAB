# Design Document

## Overview

El sistema es un chatbot de apoyo académico para la UNAB que combina una arquitectura híbrida RAG + Agentes MCP. Los estudiantes interactúan mediante una App Android nativa; las consultas viajan a n8n (orquestador de workflows) desplegado en AWS EC2, que clasifica la intención y delega al workflow correcto. Las respuestas del LLM pasan por un microservicio FastAPI de guardrails antes de retornar al usuario. La memoria persistente y la base de datos vectorial residen en Supabase (PostgreSQL + pgvector).

---

## Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                                  MV                             │
│                                                                 │
│  ┌──────────────┐   HTTP (MCP)   ┌──────────────────────────┐  │
│  │   n8n :9000  │◄──────────────►│  FastMCP Server (Python) │  │
│  │  (Workflows) │                │  puerto interno           │  │
│  └──────┬───────┘                └──────────────────────────┘  │
│         │ HTTP                                                  │
│  ┌──────▼───────┐                                              │
│  │  Guardrails  │                                              │
│  │  FastAPI     │                                              │
│  │  puerto int. │                                              │
│  └──────────────┘                                              │
│                                                                 │
│  Todos los contenedores en Docker Compose (bridge network)     │
└─────────────────────────────────────────────────────────────────┘
         │ HTTPS                           │ HTTPS
         ▼                                 ▼
┌─────────────────┐              ┌──────────────────┐
│   App Android   │              │  Supabase Cloud  │
│   (Kotlin)      │              │  PostgreSQL +    │
│                 │              │  pgvector        │
└─────────────────┘              └──────────────────┘
         │                                │
         │ HTTPS REST / WebSocket         │ SQL (pg driver)
         ▼                                ▼
    n8n :9000                     FastMCP / n8n nodes
```

### Request Flow (Consulta de Estudiante)

```
App Android
  │  POST /webhook/chat  {session_id, message}
  ▼
n8n — Ruteo por Intención (LLM classifier node)
  │
  ├─ consulta-general ──► Workflow RAG ──► FastMCP (pgvector top-5)
  │                                           │
  ├─ calendario ────────► Workflow Calendario ──► Google Sheets API
  │
  ├─ cursos-realizados ─► Workflow Cursos ──► FastMCP (BD Estudiantes)
  │
  └─ noticias ──────────► Workflow Noticias ──► tabla noticias (Supabase)
                │
                ▼  (todos los workflows)
         Memoria Persistente (PostgreSQL)
                │
                ▼
         LLM (Claude / OpenAI)
                │
                ▼
         Guardrails FastAPI
                │
                ▼
         Respuesta → App Android
```

---

## Component Design

### 1. App Android (Kotlin)

**Responsabilidades:** autenticación, interfaz de chat, pantalla de ruta académica, pantalla de calendario, recepción de notificaciones push FCM.

**Estructura de paquetes:**

```
com.unab.chatbot/
├── auth/
│   ├── AuthViewModel.kt
│   ├── LoginFragment.kt
│   └── TokenManager.kt          # EncryptedSharedPreferences
├── chat/
│   ├── ChatViewModel.kt
│   ├── ChatFragment.kt
│   ├── MessageAdapter.kt
│   └── model/
│       ├── Message.kt
│       └── ChatRequest.kt
├── academic/
│   ├── RutaAcademicaFragment.kt
│   ├── RutaAcademicaViewModel.kt
│   └── CalendarioFragment.kt
├── notifications/
│   └── FcmService.kt
└── network/
    ├── ApiClient.kt              # Retrofit + OkHttp
    └── ChatbotApi.kt
```

**Gestión de sesión:** JWT almacenado en `EncryptedSharedPreferences`. El `TokenManager` intercepta cada petición HTTP para adjuntar el token en `Authorization: Bearer <token>`. Al detectar respuesta 401, limpia el token y navega a `LoginFragment`.

**Pantallas principales:**

| Pantalla | Descripción |
|---|---|
| LoginFragment | Formulario de credenciales institucionales |
| ChatFragment | Lista de mensajes (RecyclerView), campo de texto (máx 2000 chars), botón enviar |
| RutaAcademicaFragment | RecyclerView agrupado por semestre con estado completado/pendiente |
| CalendarioFragment | RecyclerView agrupado por mes con eventos del calendario académico |

**Comunicación con backend:** REST sobre HTTPS hacia el webhook de n8n. Las respuestas de error se interceptan en un `ResponseInterceptor` que mapea códigos HTTP a mensajes amigables sin exponer detalles internos.

**Cache local:** Room Database para ruta académica y calendario (soporte offline). Cada entidad tiene un campo `last_fetched_at` para mostrar el indicador de obsolescencia.

---

### 2. n8n — Orquestador de Workflows

**Despliegue:** contenedor Docker `n8nio/n8n`, puerto `9000`, accesible externamente. Todos los workflows comparten la misma instancia n8n.

#### 2.1 Workflow de Ruteo por Intención

```
Webhook (POST /webhook/chat)
  │
  ├─ Nodo: Cargar historial (Supabase node → tabla conversation_memory)
  │        SELECT last 10 exchanges WHERE session_id = $session_id
  │
  ├─ Nodo: Guardrails — validación de entrada
  │        HTTP Request → POST http://guardrails:8080/validate-input
  │        Body: { session_id, message }
  │        SI rejected → Return node (error response)
  │
  ├─ Nodo: Clasificar intención (LLM node)
  │        System: "Clasifica el mensaje en uno de: consulta-general,
  │                 calendario, cursos-realizados, noticias. Responde
  │                 solo con la etiqueta."
  │        Output: intent_label
  │
  └─ Switch node → enruta a subworkflow según intent_label
                   default → consulta-general
```

#### 2.2 Workflow de Consulta General (RAG)

```
Input: { session_id, message, history[] }
  │
  ├─ MCP Tool node → herramienta search_documents(query=message, top_k=5)
  │   Llama a FastMCP server vía HTTP MCP protocol
  │   Retorna: chunks[] { text, similarity_score }
  │
  ├─ LLM node (Claude / OpenAI)
  │   System: contexto institucional UNAB + chunks recuperados
  │   Human: message + history
  │   Output: llm_response
  │
  ├─ Guardrails node → POST http://guardrails:8080/validate-output
  │   Body: { session_id, response: llm_response }
  │   SI flagged → llm_response = fallback_message
  │
  ├─ Persistir memoria → INSERT INTO conversation_memory
  │   (session_id, role='user', content=message)
  │   (session_id, role='assistant', content=llm_response)
  │
  └─ Return: { response: llm_response }
```

#### 2.3 Workflow de Calendario

```
Input: { session_id, message, history[] }
  │
  ├─ Google Sheets node → lee hoja "Calendario Académico"
  │   Credenciales: service account desde env var GOOGLE_SA_JSON
  │   ON ERROR → Return error message (calendar unavailable)
  │
  ├─ LLM node → genera respuesta con datos del calendario
  │
  ├─ Guardrails node (misma lógica que Consulta General)
  │
  ├─ Persistir memoria
  │
  └─ Return: { response }
```

#### 2.4 Workflow de Cursos Realizados

```
Input: { session_id, message, history[] }
  │
  ├─ MCP Tool node → herramienta get_student_courses(session_id)
  │   FastMCP consulta BD Estudiantes WHERE student_session = session_id
  │   ON ERROR → Return error + log
  │
  ├─ LLM node → respuesta personalizada con progreso académico
  │
  ├─ Guardrails node
  │
  ├─ Persistir memoria
  │
  └─ Return: { response }
```

#### 2.5 Workflow de Noticias

```
Input: { session_id, message, history[] }
  │
  ├─ Supabase node → SELECT * FROM noticias ORDER BY published_at DESC LIMIT 20
  │   SI sin resultados → Return "No hay noticias recientes disponibles."
  │
  ├─ LLM node → resume noticias relevantes a la pregunta
  │
  ├─ Guardrails node
  │
  ├─ Persistir memoria
  │
  └─ Return: { response }
```

---

### 3. FastMCP Server (Python)

**Framework:** FastMCP sobre Python 3.11. Expuesto en la red interna Docker (`mcp-server:8000`), no accesible desde el exterior.

**Herramientas expuestas:**

```python
@mcp.tool()
async def search_documents(query: str, top_k: int = 5) -> list[DocumentChunk]:
    """
    Genera embedding del query y realiza búsqueda vectorial coseno en pgvector.
    Retorna los top_k chunks más similares con texto y score.
    """

@mcp.tool()
async def get_student_courses(session_id: str) -> StudentCourseRecord:
    """
    Recupera el historial de cursos del estudiante asociado a session_id.
    Solo retorna registros donde student_session = session_id (aislamiento estricto).
    """

@mcp.tool()
async def ingest_documents(file_paths: list[str]) -> IngestionReport:
    """
    Pipeline de ingesta: chunking (512 tokens, overlap 50) → embedding → pgvector.
    Procesa todos los documentos y continúa ante errores individuales.
    Retorna conteo de documentos, chunks y embeddings procesados.
    """

@mcp.tool()
async def run_news_scraper(sources: list[str]) -> ScraperReport:
    """
    Scraping one-shot de fuentes UNAB. Deduplica por source_url antes de insertar.
    Continúa ante URLs inalcanzables. Retorna conteo de artículos.
    """
```

**Conexión a Supabase:** `asyncpg` con pool de conexiones. Las credenciales se leen de variables de entorno `SUPABASE_URL` y `SUPABASE_KEY`.

---

### 4. Guardrails Microservice (FastAPI)

**Framework:** FastAPI sobre Python 3.11, Uvicorn. Puerto interno `8080`.

**Endpoints:**

```python
POST /validate-input
  Body: { session_id: str, message: str }
  Response: { allowed: bool, reason: str | None }

POST /validate-output
  Body: { session_id: str, response: str }
  Response: { allowed: bool, sanitized_response: str }
```

**Lógica de validación de entrada:**
- Detecta patrones de prompt injection mediante expresiones regulares y una lista negra de patrones conocidos (p. ej., "ignore previous instructions", "you are now", "###System:").
- Si se detecta una inyección, retorna `allowed: false` y registra el evento en la tabla `guardrails_audit_log`.

**Lógica de validación de salida:**
- Evalúa la respuesta contra una lista de categorías de tópicos prohibidos (contenido no académico, lenguaje inapropiado, información personal).
- Si la respuesta es fuera de contexto, retorna `sanitized_response = "Solo puedo ayudarte con temas académicos de la UNAB."`.

**Modelo de auditoría:**

```python
class AuditLogEntry:
    id: UUID
    timestamp: datetime          # UTC
    session_id: str
    rejection_type: str          # "input_injection" | "output_scope" | "output_prohibited"
    rejection_reason: str
    raw_content_hash: str        # SHA-256 del contenido (no el contenido en claro)
```

---

### 5. Pipeline de Ingesta de Documentos

Ejecutado manualmente desde el FastMCP `ingest_documents` tool o desde un workflow n8n dedicado.

```
Documentos CCD (PDF / DOCX)
  │
  ▼
1. Extracción de texto (pdfplumber / python-docx)
  │
  ▼
2. Chunking
   - Tamaño máximo: 512 tokens (tiktoken cl100k_base)
   - Overlap: 50 tokens entre chunks consecutivos
   - Metadatos: { document_name, chunk_index, total_chunks }
  │
  ▼
3. Generación de Embeddings
   - Modelo: text-embedding-3-small (OpenAI) o equivalent
   - Dimensión: 1536
   - Procesamiento en lotes de 100 chunks
  │
  ▼
4. Inserción en pgvector (Supabase)
   - Tabla: document_chunks
   - Upsert por (document_name, chunk_index) para re-ingestas
  │
  ▼
5. Log de ingesta
   - { total_documents, total_chunks, total_embeddings, errors[] }
```

**Tolerancia a errores:** cada chunk se procesa en bloque try/except. Un error en el chunk N no interrumpe el proceso; se registra `{ document_name, chunk_index, error_message }` y se continúa.

---

### 6. Scraper de Noticias

Script Python one-shot ejecutado manualmente.

```
1. Leer lista de fuentes desde config (UNAB sitio web, portal noticias)
2. Para cada fuente:
   a. HTTP GET con timeout 10s
   b. SI falla → log unreachable_url, continuar
   c. BeautifulSoup parsing → extraer { title, published_at, summary, source_url }
3. Deduplicación:
   SELECT source_url FROM noticias WHERE source_url IN (batch_urls)
   → filtrar artículos ya existentes
4. INSERT INTO noticias (artículos nuevos únicamente)
5. Log: { total_extracted, total_inserted, skipped_duplicates, failed_sources }
```

---

## Data Models

### Supabase PostgreSQL Schema

```sql
-- Extensión vectorial
CREATE EXTENSION IF NOT EXISTS vector;

-- Chunks de documentos CCD (RAG)
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_name   TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    total_chunks    INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_name, chunk_index)
);
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Historial de conversación (Memoria Persistente)
CREATE TABLE conversation_memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_memory_session ON conversation_memory (session_id, created_at DESC);

-- Noticias institucionales
CREATE TABLE noticias (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    published_at    TIMESTAMPTZ NOT NULL,
    summary         TEXT NOT NULL,
    source_url      TEXT NOT NULL UNIQUE,
    scraped_at      TIMESTAMPTZ DEFAULT now()
);

-- Cursos de estudiantes (BD sintética)
CREATE TABLE student_courses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_session TEXT NOT NULL,
    course_code     TEXT NOT NULL,
    course_name     TEXT NOT NULL,
    semester        INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('completed', 'pending', 'in_progress')),
    grade           NUMERIC(4,2),
    UNIQUE (student_session, course_code)
);
CREATE INDEX idx_courses_session ON student_courses (student_session);

-- Log de auditoría de guardrails
CREATE TABLE guardrails_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp           TIMESTAMPTZ DEFAULT now(),
    session_id          TEXT NOT NULL,
    rejection_type      TEXT NOT NULL,
    rejection_reason    TEXT NOT NULL,
    raw_content_hash    TEXT NOT NULL
);
CREATE INDEX idx_audit_session ON guardrails_audit_log (session_id, timestamp DESC);

-- Tokens de sesión de estudiantes
CREATE TABLE student_sessions (
    session_id      TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL UNIQUE,
    token_hash      TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL
);
```

---

## Components and Interfaces

### Component List

| Componente | Tecnología | Rol |
|---|---|---|
| App Android | Kotlin, Retrofit, Room | Interfaz de usuario: chat, ruta académica, calendario, notificaciones |
| n8n | Docker, n8nio/n8n | Orquestador de workflows, ruteo por intención, integración con LLM |
| FastMCP Server | Python 3.11, FastMCP | Servidor MCP: búsqueda vectorial, consulta de cursos, ingesta, scraping |
| Guardrails | Python 3.11, FastAPI | Validación de entradas/salidas, auditoría de rechazos |
| Supabase | PostgreSQL + pgvector | Base de datos vectorial, memoria persistente, noticias, cursos, sesiones |
| Google Sheets | Google Sheets API v4 | Fuente de datos del calendario académico institucional |
| FCM | Firebase Cloud Messaging | Entrega de notificaciones push al dispositivo Android |
| LLM | Claude / OpenAI GPT | Generación de respuestas en lenguaje natural |

### Inter-Component Interfaces

```
App Android          ──HTTPS REST──►        n8n (puerto 9000)
n8n                  ──HTTP MCP──►           FastMCP Server (interno :8000)
n8n                  ──HTTP REST──►          Guardrails FastAPI (interno :8080)
n8n                  ──Google Sheets API──►  Google Sheets (externo)
n8n                  ──FCM HTTP v1──►        Firebase Cloud Messaging (externo)
FastMCP Server       ──asyncpg──►            Supabase PostgreSQL
Guardrails           ──asyncpg──►            Supabase PostgreSQL (audit log)
n8n                  ──Supabase node──►      Supabase PostgreSQL (memoria, noticias)
```

Todos los componentes del backend comparten la red Docker bridge `backend`. Solo n8n expone el puerto 9000 en el Security Group de AWS; FastMCP y Guardrails son exclusivamente internos.

---

## Interface Contracts

### App Android → n8n (Webhook)

```
POST https://<ec2-host>:9000/webhook/chat
Authorization: Bearer <session_token>
Content-Type: application/json

Request:
{
  "session_id": "string",
  "message": "string"       // 1–2000 chars
}

Response 200:
{
  "response": "string",     // respuesta del chatbot
  "intent": "string"        // intent clasificado
}

Response 4xx / 5xx:
{
  "error": "string"         // mensaje amigable, sin detalles internos
}
```

### App Android → n8n (Ruta Académica)

```
GET https://<ec2-host>:9000/webhook/academic-route
Authorization: Bearer <session_token>

Response 200:
{
  "courses": [
    {
      "course_code": "string",
      "course_name": "string",
      "semester": number,
      "status": "completed" | "pending" | "in_progress",
      "grade": number | null
    }
  ]
}
```

### App Android → n8n (Calendario)

```
GET https://<ec2-host>:9000/webhook/calendar
Authorization: Bearer <session_token>

Response 200:
{
  "events": [
    {
      "event_name": "string",
      "event_date": "ISO-8601",
      "description": "string"
    }
  ]
}
```

### n8n → Guardrails

```
POST http://guardrails:8080/validate-input
{ "session_id": "string", "message": "string" }
→ { "allowed": bool, "reason": "string | null" }

POST http://guardrails:8080/validate-output
{ "session_id": "string", "response": "string" }
→ { "allowed": bool, "sanitized_response": "string" }
```

### n8n → FastMCP (MCP Protocol sobre HTTP)

```
POST http://mcp-server:8000/mcp
{
  "method": "tools/call",
  "params": {
    "name": "search_documents" | "get_student_courses" | ...,
    "arguments": { ... }
  }
}
```

---

## Infrastructure

### Docker Compose

```yaml
# docker-compose.yml (AWS EC2 Ubuntu)
version: "3.9"
services:
  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    ports:
      - "9000:5678"
    environment:
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GOOGLE_SA_JSON=${GOOGLE_SA_JSON}
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - backend

  mcp-server:
    build: ./mcp-server
    restart: unless-stopped
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    networks:
      - backend

  guardrails:
    build: ./guardrails
    restart: unless-stopped
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    networks:
      - backend

networks:
  backend:
    driver: bridge

volumes:
  n8n_data:
```

### AWS Security Group

| Puerto | Protocolo | Origen | Propósito |
|---|---|---|---|
| 9000 | TCP | 0.0.0.0/0 | n8n webhook (acceso público App Android) |
| 22 | TCP | IP admin | SSH administración |
| 8000 | TCP | backend network only | FastMCP (interno) |
| 8080 | TCP | backend network only | Guardrails (interno) |

> Los puertos 8000 y 8080 **no** se exponen en Security Groups de AWS; solo son alcanzables dentro de la red Docker bridge `backend`.

### Notificaciones Push (FCM)

El workflow n8n incluye un nodo HTTP que llama a la Firebase Cloud Messaging (FCM) v1 API con credenciales de cuenta de servicio almacenadas en variables de entorno. La lógica de detección de eventos en 48h se implementa como un workflow n8n con trigger tipo `Cron` (cada hora) que consulta el calendario y compara fechas.

---

## Error Handling

| Escenario | Componente | Comportamiento |
|---|---|---|
| Credenciales inválidas | App Android | Mensaje de error genérico; no expone detalles del backend |
| Token expirado | App Android | Redirige a login; limpia token local |
| Backend inalcanzable | App Android | Mensaje de conectividad + botón de reintento |
| Guardrails rechaza input | n8n | Retorna error al App sin llamar al LLM; registra en audit log |
| Guardrails rechaza output | n8n | Sustituye respuesta por mensaje fallback estándar |
| Google Sheets unavailable | Workflow Calendario | Retorna mensaje "calendario temporalmente no disponible" |
| BD Estudiantes inalcanzable | Workflow Cursos | Retorna error descriptivo + log en n8n |
| Sin noticias en DB | Workflow Noticias | Retorna "No hay noticias recientes disponibles." |
| Error en chunk/embedding | Pipeline Ingesta | Log del error, continúa con siguiente chunk |
| URL inalcanzable en scraper | Scraper | Log de URL fallida, continúa con siguiente fuente |
| LLM timeout | Todos los workflows | n8n timeout node retorna mensaje de error amigable |
| Contenedor caído | Docker | Restart policy `unless-stopped` reinicia automáticamente |

---

## Correctness Properties

*Una propiedad es una característica o comportamiento que debe mantenerse verdadero en todas las ejecuciones válidas del sistema — esencialmente, un enunciado formal sobre lo que el sistema debe hacer. Las propiedades sirven como puente entre las especificaciones legibles por humanos y las garantías de corrección verificables automáticamente.*

### Property 1: Credenciales inválidas nunca exponen información sensible

*Para cualquier* par de credenciales inválidas enviadas al endpoint de autenticación, el mensaje de error retornado a la app no debe contener el valor de la contraseña, tokens internos, ni trazas de pila del servidor.

**Validates: Requirements 1.2**

---

### Property 2: Validación de longitud del mensaje de chat

*Para cualquier* cadena de texto, si su longitud está fuera del rango [1, 2000] caracteres, la acción de envío debe ser bloqueada en la App Android; si su longitud está dentro de [1, 2000] caracteres, debe ser permitida.

**Validates: Requirements 2.6**

---

### Property 3: Mensajes enviados aparecen en la lista de chat

*Para cualquier* mensaje válido (longitud 1–2000 caracteres) enviado por el estudiante, el mensaje debe aparecer en la lista de mensajes del chat inmediatamente después de ser enviado.

**Validates: Requirements 2.2**

---

### Property 4: Errores del backend no exponen detalles internos

*Para cualquier* payload de respuesta de error proveniente del backend, la cadena de texto mostrada al estudiante no debe contener códigos de estado HTTP, trazas de pila, nombres de tablas de base de datos, ni identificadores internos del sistema.

**Validates: Requirements 2.5**

---

### Property 5: El clasificador de intención siempre retorna una etiqueta válida

*Para cualquier* mensaje de entrada (incluidos mensajes vacíos, con caracteres especiales o en idiomas distintos al español), el nodo de clasificación de intención debe retornar exactamente una etiqueta del conjunto `{consulta-general, calendario, cursos-realizados, noticias}`.

**Validates: Requirements 3.1, 3.6**

---

### Property 6: RAG retorna a lo sumo top-k chunks ordenados por similitud

*Para cualquier* query de texto enviado a la herramienta `search_documents`, el resultado debe contener exactamente `min(top_k, N)` chunks donde N es el total de chunks en la base de datos, y los chunks deben estar ordenados por `similarity_score` descendente.

**Validates: Requirements 4.1**

---

### Property 7: Guardrails sustituye respuestas fuera de alcance por el fallback exacto

*Para cualquier* respuesta del LLM que sea clasificada como fuera de alcance o inapropiada por el microservicio de guardrails, la respuesta final retornada al estudiante debe ser exactamente la cadena `"Solo puedo ayudarte con temas académicos de la UNAB."`.

**Validates: Requirements 4.5, 11.3**

---

### Property 8: Aislamiento de historial de cursos por sesión

*Para cualesquiera* dos identificadores de sesión distintos `A` y `B`, el conjunto de registros de cursos retornados para la sesión `A` debe ser completamente disjunto del conjunto de registros de la sesión `B`; ningún registro de un estudiante es accesible mediante el identificador de sesión de otro estudiante.

**Validates: Requirements 6.1, 6.5**

---

### Property 9: Chunks cumplen la restricción de tamaño y overlap

*Para cualquier* documento de texto de longitud arbitraria procesado por el pipeline de ingesta, todos los chunks resultantes deben tener una longitud máxima de 512 tokens, y cada par de chunks consecutivos debe compartir exactamente los últimos 50 tokens del chunk anterior como prefijo del siguiente.

**Validates: Requirements 8.1**

---

### Property 10: Cardinalidad embeddings = cardinalidad chunks

*Para cualquier* lote de N chunks generados durante la ingesta, el pipeline debe producir exactamente N vectores de embedding, uno por cada chunk.

**Validates: Requirements 8.2**

---

### Property 11: Round-trip de almacenamiento de chunks

*Para cualquier* chunk insertado en la tabla `document_chunks` de pgvector, una consulta posterior a esa tabla usando el `(document_name, chunk_index)` del chunk debe retornar un registro con el mismo texto de contenido.

**Validates: Requirements 8.3**

---

### Property 12: Tolerancia a errores en pipeline de ingesta

*Para cualquier* lote de N documentos donde exactamente K documentos producen errores durante la generación de embeddings o el almacenamiento, el pipeline debe procesar exitosamente N−K documentos y registrar exactamente K entradas de error en el log, sin abortar el proceso completo.

**Validates: Requirements 8.5**

---

### Property 13: Artículos almacenados contienen todos los campos requeridos

*Para cualquier* artículo de noticias extraído y almacenado por el scraper, el registro en la tabla `noticias` debe tener valores no nulos en los campos `title`, `published_at`, `summary` y `source_url`.

**Validates: Requirements 9.2**

---

### Property 14: Tolerancia a errores en el scraper

*Para cualquier* lote de N fuentes configuradas donde exactamente K URLs son inalcanzables, el scraper debe procesar exitosamente N−K fuentes y registrar exactamente K URLs fallidas en el log.

**Validates: Requirements 9.4**

---

### Property 15: Idempotencia del scraper (deduplicación por source_url)

*Para cualquier* conjunto de artículos con URLs únicas, ejecutar el scraper dos veces sobre las mismas fuentes debe resultar en el mismo número de registros en la tabla `noticias` que ejecutarlo una sola vez; no se crean duplicados en ejecuciones repetidas.

**Validates: Requirements 9.5**

---

### Property 16: Ventana de contexto de memoria limitada a 10 exchanges

*Para cualquier* sesión con historial de N intercambios donde N > 10, el contexto pasado al LLM en la siguiente invocación debe contener exactamente los 10 intercambios más recientes, no más.

**Validates: Requirements 10.1**

---

### Property 17: Round-trip de memoria persistente

*Para cualquier* par (mensaje_estudiante, respuesta_LLM) generado durante una sesión, ambos elementos deben aparecer en el historial de conversación de la sesión inmediatamente después del intercambio.

**Validates: Requirements 10.2**

---

### Property 18: Aislamiento de memoria por sesión

*Para cualesquiera* dos identificadores de sesión distintos, sus historiales de conversación deben ser completamente disjuntos; ningún mensaje de la sesión A aparece en el historial consultado con el identificador de la sesión B.

**Validates: Requirements 10.3**

---

### Property 19: Límite de retención de memoria (máximo 50 exchanges)

*Para cualquier* sesión en la que se almacenen más de 50 intercambios, el tamaño del historial persistente debe ser exactamente 50, conteniendo los intercambios más recientes.

**Validates: Requirements 10.4**

---

### Property 20: Guardrails bloquea inyecciones de prompt

*Para cualquier* mensaje de entrada que contenga patrones de inyección de prompt conocidos, el microservicio de guardrails debe retornar `allowed: false` y el mensaje no debe ser reenviado al LLM.

**Validates: Requirements 11.2, 11.4**

---

### Property 21: Log de auditoría completo en rechazos de guardrails

*Para cualquier* evento de rechazo generado por el microservicio de guardrails, la entrada registrada en `guardrails_audit_log` debe contener valores no nulos en los campos `timestamp`, `session_id` y `rejection_reason`.

**Validates: Requirements 11.5**

---

### Property 22: Estado de cursos coincide con datos del backend

*Para cualquier* lista de cursos retornada por el backend, cada elemento renderizado en la pantalla de Ruta Académica debe mostrar el estado (`completed` / `pending` / `in_progress`) que coincide exactamente con el campo `status` del registro correspondiente en la respuesta del backend.

**Validates: Requirements 12.2**

---

### Property 23: Agrupación correcta de eventos de calendario por mes

*Para cualquier* lista de eventos de calendario con fechas variadas, todos los eventos renderizados bajo un encabezado de mes determinado deben tener una fecha cuyo componente de mes y año coincida con ese encabezado.

**Validates: Requirements 13.2**

---

### Property 24: Notificaciones push dentro de ventana de 48 horas

*Para cualquier* evento académico cuya fecha esté en el intervalo `(ahora, ahora + 48 horas]`, el sistema debe despachar exactamente una notificación push al dispositivo registrado del estudiante. Para cualquier evento fuera de ese intervalo, no se debe despachar notificación.

**Validates: Requirements 14.1**


---

## Testing Strategy

### Enfoque dual: pruebas de ejemplo + pruebas basadas en propiedades

El sistema combina pruebas de ejemplo (unitarias e integración) con pruebas basadas en propiedades (PBT) para lograr cobertura exhaustiva.

**Pruebas de ejemplo** se usan para:
- Flujos de autenticación específicos (credenciales válidas, expiración de token)
- Comportamiento de la UI (indicador de carga, pantalla de ruta académica, detalle de evento)
- Integración con servicios externos (Google Sheets, FCM)
- Verificación de smoke (configuración de contenedores, variables de entorno)

**Pruebas basadas en propiedades** (mínimo 100 iteraciones cada una) se usan para:
- Validación de longitud y contenido de mensajes (Properties 2, 3, 4)
- Clasificador de intención (Property 5)
- Pipeline RAG: recuperación vectorial, chunking, embeddings (Properties 6, 9, 10, 11)
- Guardrails: prompt injection, fallback, auditoría (Properties 7, 20, 21)
- Memoria persistente: ventana de contexto, aislamiento, límite de retención (Properties 16–19)
- Scraper: tolerancia a errores, deduplicación (Properties 14, 15)
- Calendario Android: agrupación por mes (Property 23)
- Notificaciones push: ventana de 48h (Property 24)

### Herramientas por capa

| Capa | Framework de pruebas | Framework PBT |
|---|---|---|
| App Android (Kotlin) | JUnit 5 + MockK + Espresso | Kotest Property Testing |
| FastMCP / Guardrails (Python) | pytest | Hypothesis |
| n8n Workflows | n8n test runner + mocks HTTP | No aplica (integración) |
| BD / SQL | pgTAP (opcional) | No aplica |

### Mocking de servicios externos

Para ejecutar las PBT sin incurrir en costos de API reales:
- **LLM**: mock que retorna respuestas predefinidas según el prompt.
- **Google Sheets**: mock HTTP que retorna JSON de calendario.
- **Supabase**: base de datos PostgreSQL local en Docker para tests.
- **FCM**: mock HTTP que registra las notificaciones enviadas.

### Convención de etiquetado de propiedades

Cada test de propiedad debe etiquetarse con:

```
Feature: chatbot-apoyo-academico, Property N: <texto de la propiedad>
```

Esto permite trazabilidad directa entre el test fallido y la propiedad de corrección correspondiente en este documento.
