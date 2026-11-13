# Chatbot de Apoyo Académico UNAB

Trabajo final de **Ciencia de Datos** (Ingeniería de Sistemas, UNAB). Chatbot híbrido **RAG + herramientas MCP**:
una App Android nativa (Kotlin) habla con **n8n**, que clasifica la intención del estudiante y la resuelve con
un **servidor FastMCP** (búsqueda vectorial en pgvector, cursos del estudiante), Google Sheets (calendario) o la
tabla de noticias. Toda respuesta del LLM pasa por un microservicio de **Guardrails** (FastAPI) y la conversación
se guarda en **Supabase** (PostgreSQL + pgvector).

```
App Android ──HTTPS──► n8n :9000 ──► Guardrails (entrada) ──► Clasificador LLM ──► Switch
                                         │                                        ├─ consulta-general → MCP search_documents (pgvector top-5)
                                         │                                        ├─ calendario       → Google Sheets
                                         │                                        ├─ cursos-realizados→ MCP get_student_courses
                                         │                                        └─ noticias         → tabla noticias
                                         └──────────── LLM ──► Guardrails (salida) ──► memoria ──► respuesta
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `docker-compose.yml`, `.env.example` | Infraestructura (n8n, mcp-server, guardrails en la red `backend`) |
| `db/schema.sql`, `db/seed.sql` | Esquema PostgreSQL/pgvector + funciones SQL, y datos sintéticos de prueba |
| `mcp-server/` | Servidor FastMCP (Python): `search_documents`, `get_student_courses`, `ingest_documents`, `run_news_scraper` |
| `guardrails/` | Microservicio FastAPI: `/validate-input` (prompt injection), `/validate-output` (alcance) + auditoría |
| `n8n/workflows/*.json` | 6 workflows importables (chat con ruteo, login, ruta académica, calendario, registro FCM, push) |
| `n8n/code/lib.js`, `n8n/build_workflows.py` | Lógica JS de los nodos Code (probada) y generador de los JSON |
| `android/` | App Android (Kotlin, Retrofit, Room, EncryptedSharedPreferences, FCM) |
| `tests/` | Pruebas de integración (SQL real, lógica JS de n8n) y smoke test e2e |
| `scripts/` | `setup_n8n.py` (credenciales + import), `run_tests.sh`, `mock_llm.py` |
| `docs/` | Requisitos, diseño y plan de tareas (con estado), calendario de ejemplo |

## Puesta en marcha

### 1. Supabase
1. Crea un proyecto en Supabase.
2. En **SQL Editor** ejecuta `db/schema.sql` y luego `db/seed.sql`.
3. Copia la cadena de conexión (**Project Settings → Database → Connection string**, modo *Session*, puerto 5432).

Usuarios de prueba del seed: `U00000001` / `Unab2026*` (6.º semestre) y `U00000002` / `Unab2026*` (3.er semestre).

### 2. Google Sheets (calendario)
1. Crea una hoja llamada **Calendario Académico** con las columnas `event_name, event_date, description`
   (fechas `AAAA-MM-DD`). Puedes importar `docs/calendario_ejemplo.csv`. También acepta `Evento, Fecha, Descripción`.
2. Crea una cuenta de servicio en Google Cloud, habilita la *Google Sheets API* y comparte la hoja con el correo de
   la cuenta de servicio (lector). El JSON de la cuenta va en `GOOGLE_SA_JSON` (una sola línea).

### 3. Firebase (notificaciones push)
1. Crea un proyecto Firebase, agrega la app Android `com.unab.chatbot` y descarga `google-services.json` a
   `android/app/` (no se sube a git; sin ese archivo la app funciona pero sin push).
2. Habilita la *Firebase Cloud Messaging API (V1)*. La misma cuenta de servicio de Google debe tener el rol
   *Firebase Cloud Messaging API Admin* en ese proyecto. Pon el ID del proyecto en `FCM_PROJECT_ID`.

### 4. Backend en AWS EC2 (Ubuntu)
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 python3
git clone <tu-repo> chatbot && cd chatbot
cp .env.example .env && nano .env              # completa los valores
docker compose up -d --build
python3 scripts/setup_n8n.py --activate        # crea credenciales cifradas e importa/activa los workflows
```
- En el Security Group abre solo **9000/TCP** (y 22 para tu IP). 8000 y 8080 no se publican.
- Entra a `http://<ip-ec2>:9000`, crea el usuario dueño de n8n y verifica que los 6 workflows estén activos.
- Ingesta de documentos CCD: copia los PDF/DOCX a `data/ccd/` y ejecuta
  `docker compose exec mcp-server python -m app.cli ingest`.
- Noticias: ajusta selectores en `mcp-server/sources.json` y ejecuta
  `docker compose exec mcp-server python -m app.cli scrape`.
- Smoke test: `BASE=http://<ip-ec2>:9000/webhook ./tests/e2e/smoke_test.sh`

> **HTTPS:** n8n en el puerto 9000 sirve HTTP. Para producción coloca Caddy o Nginx con certificado delante de n8n.
> La App en modo *debug* permite HTTP; en *release* solo HTTPS.

### 5. App Android
1. Abre la carpeta `android/` en Android Studio (Ladybug o superior, JDK 17).
2. En `android/gradle.properties` cambia `chatbot.baseUrl` (emulador + backend local: `http://10.0.2.2:9000/`;
   EC2: `http://<ip-ec2>:9000/`).
3. Ejecuta la app. Pruebas: `./gradlew test` (unitarias + Kotest) y `./gradlew connectedAndroidTest` (Espresso).

### Desarrollo local sin costos de API
- `EMBEDDINGS_PROVIDER=hash` en el mcp-server usa embeddings deterministas sin OpenAI (no semánticos).
- `python3 scripts/mock_llm.py` levanta un LLM simulado compatible con OpenAI en el puerto 8099; apúntale con
  `LLM_API_URL=http://<host>:8099/v1/chat/completions`.
- Para usar otro proveedor compatible con OpenAI (o un proxy hacia Claude) cambia `LLM_API_URL` y `LLM_MODEL`.

## Endpoints (n8n)

| Método | Ruta | Uso |
|---|---|---|
| POST | `/webhook/login` | `{student_id, password}` → `{token, session_id, expires_at, full_name}` |
| POST | `/webhook/chat` | `{session_id, message}` + Bearer → `{response, intent}` |
| GET | `/webhook/academic-route` | Bearer → `{courses[], progress_percentage}` |
| GET | `/webhook/calendar` | Bearer → `{events[]}` |
| POST | `/webhook/register-device` | `{fcm_token}` + Bearer → `{ok}` |

El backend **ignora el `session_id` del cuerpo** y usa el asociado al token, así un estudiante nunca puede leer
la memoria o los cursos de otro.

## Pruebas

```bash
./scripts/run_tests.sh                     # todas las pruebas Python
TEST_DB_URL=postgresql://postgres@localhost:5432/chatbot_test ./scripts/run_tests.sh   # + integración con BD
```
Las 24 propiedades de corrección del diseño tienen su test, etiquetado
`Feature: chatbot-apoyo-academico, Property N` (Hypothesis en Python, Kotest en Android, ≥100 iteraciones).

| Propiedades | Dónde |
|---|---|
| 1, 2, 3, 4, 22, 23 | `android/app/src/test/...` (Kotest) |
| 5, 16, 24 (paridad JS) | `tests/integration/test_n8n_code.py` (Node.js) |
| 6, 8, 9–15, 24 | `mcp-server/tests/` |
| 7, 20, 21 | `guardrails/tests/` |
| 11 (pgvector real), 16–19 | `mcp-server/tests/test_pg_stores.py`, `tests/integration/test_database.py` |

## Decisiones respecto al diseño original
- **`SUPABASE_DB_URL`**: asyncpg necesita la cadena PostgreSQL; `SUPABASE_URL/KEY` (REST) no sirven para conectarse.
- **Índice HNSW** en lugar de ivfflat: ivfflat con `lists=100` y pocas filas devuelve menos de top-k resultados.
- **`session_id` estable por estudiante**: el login rota el token pero conserva el `session_id`; así la memoria y
  los cursos persisten entre sesiones (Requirement 10). Se agregaron las tablas `students`, `device_tokens` y
  `notifications_sent`, y funciones SQL (`login_student`, `validate_session`, `get_recent_history`,
  `save_exchange`, `pending_notifications`). La retención de 50 intercambios la hace un trigger.
- **Un workflow de chat con ramas** en vez de sub-workflows: importa sin reconfigurar IDs.
- **n8n llama al servidor MCP por un puente REST** (`/tools/*`) con la misma lógica que las herramientas MCP
  (`/mcp` sigue disponible para clientes MCP). Las respuestas son deterministas y fáciles de manejar en n8n.
- **Tolerancia a errores de ingesta por documento** (Requirement 8.5 / Property 12).
- **Guardrails fail-closed**: si el servicio no responde, se devuelve el mensaje de fallback.
