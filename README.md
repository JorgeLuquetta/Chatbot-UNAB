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

## Demo en línea

La VM de Azure publica todo por un túnel de Cloudflare con HTTPS. No hace falta abrir puertos.

| Dirección | Qué es | Puerto en la VM |
|---|---|---|
| **https://chat.traumado.top** | Chat web para estudiantes: saluda, pide el ID y responde | `localhost:9001` |
| **https://app.traumado.top** | Página con los QR: chat web y app en Expo Go | `localhost:9002` |
| **https://expo.traumado.top** | Servidor de la app para Expo Go (`exps://expo.traumado.top`). En un navegador redirige a app.traumado.top | `localhost:8081` |
| **https://chatbot.traumado.top** | n8n: interfaz de administración y webhooks (`/webhook/...`) | `localhost:9000` |

**Acceso a n8n:** el correo es `admin@traumado.top`. La contraseña **no está en este repositorio**, porque el repo
es público y la cuenta de n8n puede ejecutar código en el servidor. Está en `CREDENCIALES.md` dentro de la VM
(`~/Chatbot-UNAB/CREDENCIALES.md`, ignorado por git). Pídanla al administrador del grupo.

### Estudiantes de prueba

El chat **no pide contraseña**: basta con el ID. Todos los datos son sintéticos. En total hay 42 estudiantes,
de `U00000001` a `U00000042`, en 4 programas, con 76 materias en el catálogo (`db/seed_sintetico.sql`).
Para el endpoint `/webhook/login` la contraseña de todos es `Unab2026*`.

| ID | Estudiante | Programa | Semestre | Avance | Materias reprobadas |
|---|---|---|---|---|---|
| `U00000001` | Ana María Rojas | Ingeniería de Sistemas | 6.º | 68,2 % | 0 |
| `U00000002` | Carlos Pérez | Ingeniería de Sistemas | 3.º | 27,3 % | 0 |
| `U00000003` | Diego Jaimes Ortiz | Psicología | 7.º | 72,2 % | 1 |
| `U00000005` | Santiago Vargas Castillo | Ingeniería Industrial | 6.º | 63,2 % | 1 |
| `U00000006` | Laura Mantilla Jaimes | Administración de Empresas | 4.º | 47,1 % | 1 |
| `U00000007` | Nicolás Rodríguez Suárez | Psicología | 9.º | 83,3 % | 1 |
| `U00000009` | Samuel Pinzón Díaz | Ingeniería Industrial | 1.º | 0 % | 0 |
| `U00000010` | Camila Rojas Quintero | Administración de Empresas | 3.º | 23,5 % | 2 |
| `U00000020` | Daniela Duarte Moreno | Ingeniería de Sistemas | 9.º | 86,4 % | 2 |

### Cómo verificarlo

1. **Chat web:** abre https://chat.traumado.top y escribe `U00000010`. El bot saluda a Camila con su programa,
   semestre y avance. Luego pregunta, por ejemplo:
   - *¿Qué materias tengo pendientes?* (cursos del estudiante desde la BD)
   - *¿Cuáles son los requisitos de grado?* (RAG sobre el reglamento)
   - *¿Qué noticias hay en la universidad?* (noticias)
   - *Recomiéndame un casino* → se bloquea porque no es un tema académico (guardrails)
2. **App móvil:** instala Expo Go, abre https://app.traumado.top en el PC y escanea el QR de la app.
3. **API directa:**
   ```bash
   curl -X POST https://chatbot.traumado.top/webhook/student-lookup \
        -H 'content-type: application/json' -d '{"student_id":"U00000010"}'
   curl -X POST https://chatbot.traumado.top/webhook/chat \
        -H 'content-type: application/json' -d '{"student_id":"U00000010","message":"¿Cuál es mi avance?"}'
   curl "https://chatbot.traumado.top/webhook/academic-route?student_id=U00000010"
   ```
4. **n8n:** entra a https://chatbot.traumado.top con la cuenta de administrador y revisa que los 7 workflows
   estén activos y que aparezcan las ejecuciones.

> Las respuestas que usan el LLM tardan de 30 a 90 s: el modelo corre en CPU y atiende una pregunta a la vez.

### Siempre encendido

Los contenedores tienen `restart: always`, Docker y `cloudflared` arrancan con el sistema, y un vigilante
(`scripts/watchdog.sh`, timer `unab-watchdog` de systemd cada 2 min) reinicia lo que no responda.
Si la VM se **apaga desde Azure**, hay que encenderla (`az vm start -g rg-vm-programas -n vm-programas`);
al arrancar, todo se levanta solo.

## Estructura

| Carpeta | Contenido |
|---|---|
| `docker-compose.yml`, `.env.example` | Infraestructura (n8n, mcp-server, guardrails en la red `backend`) |
| `db/schema.sql`, `db/seed.sql` | Esquema PostgreSQL/pgvector + funciones SQL, y datos sintéticos de prueba |
| `mcp-server/` | Servidor FastMCP (Python): `search_documents`, `get_student_courses`, `ingest_documents`, `run_news_scraper` |
| `guardrails/` | Microservicio FastAPI: `/validate-input` (prompt injection), `/validate-output` (alcance) + auditoría |
| `n8n/workflows/*.json` | 6 workflows importables (chat con ruteo, login, ruta académica, calendario, registro FCM, push) |
| `n8n/code/lib.js`, `n8n/build_workflows.py` | Lógica JS de los nodos Code (probada) y generador de los JSON |
| `mobile/` | **App móvil Expo / React Native** (se ejecuta en Expo Go): login, chat, ruta académica, calendario offline, recordatorios |
| `android/` | App Android nativa original (Kotlin, Retrofit, Room, FCM); requiere Android Studio |
| `tests/` | Pruebas de integración (SQL real, lógica JS de n8n) y smoke test e2e |
| `scripts/` | `setup_n8n.py` (credenciales + import), `run_tests.sh`, `mock_llm.py` |
| `docs/` | Requisitos, diseño y plan de tareas (con estado), calendario de ejemplo |

## Puesta en marcha

### 1. Supabase
1. Crea un proyecto en Supabase.
2. En **SQL Editor** ejecuta `db/schema.sql`, luego `db/seed.sql` y por último `db/seed_sintetico.sql`
   (40 estudiantes más y el catálogo de materias; se puede ejecutar varias veces).
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
docker compose up -d --build                   # incluye Ollama y descarga los modelos (~1.6 GB) la primera vez
python3 scripts/setup_n8n.py --activate        # crea credenciales cifradas, importa y activa los workflows
```
- VM mínima: 2 vCPU y 4 GB de RAM (p. ej. Azure `Standard_B2als_v2` o AWS `t3.medium`).
- En el Security Group abre solo **9000/TCP** (y 22 para tu IP). 8000 y 8080 no se publican.
- Entra a `http://<ip-ec2>:9000`, crea el usuario dueño de n8n y verifica que los 6 workflows estén activos.
- Ingesta de documentos CCD: copia los PDF/DOCX a `data/ccd/` y ejecuta
  `docker compose exec mcp-server python -m app.cli ingest`.
- Noticias: ajusta selectores en `mcp-server/sources.json` y ejecuta
  `docker compose exec mcp-server python -m app.cli scrape`.
- Smoke test: `BASE=http://<ip-ec2>:9000/webhook ./tests/e2e/smoke_test.sh`

> **HTTPS:** n8n en el puerto 9000 sirve HTTP. Para producción coloca Caddy o Nginx con certificado delante de n8n.
> La App en modo *debug* permite HTTP; en *release* solo HTTPS.

### 5. App móvil (Expo Go)
La app principal está en `mobile/` (Expo / React Native) y se ejecuta en **Expo Go** sin Android Studio:
```bash
cd mobile && npm install && npx expo start     # escanea el QR con Expo Go
```
Ver `mobile/README.md`. La app Kotlin original sigue en `android/` como referencia (requiere Android Studio).

### LLM gratuito con Ollama (por defecto)
`docker compose up` levanta **Ollama** y descarga `qwen2.5:1.5b` (chat, clasificación y validación) y
`granite-embedding:278m` (embeddings multilingües, 768 dims rellenados a 1536 en la columna `vector(1536)`;
el relleno con ceros no cambia la similitud coseno). No hace falta ninguna cuenta ni API key.
- Requiere ~4 GB de RAM. En CPU una respuesta tarda de 30 a 90 s; Ollama atiende una consulta a la vez.
- Con `GUARDRAILS_LLM_URL`, los guardrails aplican reglas y clasificación LLM. La salida se entrega solo si el
  clasificador confirma su alcance; si falla o no da un veredicto, se devuelve el mensaje de fallback.
- En preguntas con términos académicos claros se omite la clasificación de tema previa; la respuesta generada
  sigue pasando por la validación final de alcance.
- Para acelerar: menos historial (`LLM_HISTORY_MESSAGES`), respuestas más cortas (`LLM_MAX_TOKENS`) o más vCPU.
- Para usar OpenAI u otro proveedor compatible: cambia `LLM_API_URL`, `LLM_MODEL`, `OPENAI_API_KEY` y
  `EMBEDDINGS_PROVIDER=openai` (y vuelve a ingerir los documentos).
- Pruebas sin LLM: `EMBEDDINGS_PROVIDER=hash` y `python3 scripts/mock_llm.py` (`LLM_API_URL=http://<host>:8099/v1/chat/completions`).

## Endpoints (n8n)

| Método | Ruta | Uso |
|---|---|---|
| POST | `/webhook/student-lookup` | `{student_id}` → `{student_id, full_name, program, current_semester, progress_percentage}` (404 si no existe) |
| POST | `/webhook/chat` | `{student_id, message}` (o Bearer del login) → `{response, intent}` |
| GET | `/webhook/academic-route` | `?student_id=` (o Bearer) → `{courses[], progress_percentage}` |
| GET | `/webhook/calendar` | `?student_id=` (o Bearer) → `{events[]}` |
| POST | `/webhook/login` | `{student_id, password}` → `{token, session_id, expires_at, full_name}` |
| POST | `/webhook/register-device` | `{fcm_token}` + Bearer → `{ok}` |

El backend **ignora el `session_id` del cuerpo** y usa el asociado al token o al ID. Así un estudiante nunca puede
leer la memoria ni los cursos de otro *si usa el login*. **Modo demo:** con solo el ID, cualquiera que conozca un
ID puede ver los datos de ese estudiante. Es aceptable porque los datos son sintéticos, pero en producción hay
que volver al login.

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
