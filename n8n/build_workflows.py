"""Genera los workflows n8n importables (n8n/workflows/*.json).

    python n8n/build_workflows.py

La lógica JavaScript vive en n8n/code/lib.js (probada con tests) y se inserta en
cada nodo Code. Si modificas lib.js o este archivo, vuelve a ejecutarlo e importa
de nuevo los workflows.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "workflows"
LIB = (ROOT / "code" / "lib.js").read_text(encoding="utf-8").split("// @export")[0].strip()

# IDs fijos: coinciden con las credenciales que crea scripts/setup_n8n.py
CRED_PG = {"postgres": {"id": "unabSupabasePg01", "name": "Supabase Postgres"}}
CRED_OPENAI = {"openAiApi": {"id": "unabOpenAiApi001", "name": "OpenAI API"}}
CRED_GOOGLE = {"googleApi": {"id": "unabGoogleSa0001", "name": "Google Service Account"}}

MCP = "http://mcp-server:8000"
GUARDRAILS = "http://guardrails:8080"
# Cualquier endpoint compatible con OpenAI Chat Completions. Por defecto: Ollama local (gratis).
OPENAI_URL = "={{ $env.LLM_API_URL || 'http://ollama:11434/v1/chat/completions' }}"
# Un LLM local en CPU tarda decenas de segundos: los timeouts se ajustan con variables de entorno.
LLM_TIMEOUT_MS = 180000
CLASSIFIER_TIMEOUT_MS = 90000
GUARDRAILS_TIMEOUT_MS = 75000
EXECUTION_TIMEOUT_S = 420
# Mensajes de historial que se envían al LLM (20 = 10 intercambios, Property 16)
HIST = "(parseInt($env.LLM_HISTORY_MESSAGES, 10) >= 0 ? parseInt($env.LLM_HISTORY_MESSAGES, 10) : 20)"


def _id(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "unab-chatbot/" + seed))


class WF:
    def __init__(self, name: str, wf_id: str) -> None:
        self.name, self.wf_id = name, wf_id
        self.nodes: list[dict] = []
        self.connections: dict[str, dict] = {}

    def add(self, name, type_, version, params, pos, **extra) -> str:
        node = {"id": _id(self.name + "/" + name), "name": name, "type": type_, "typeVersion": version,
                "position": list(pos), "parameters": params}
        node.update(extra)
        self.nodes.append(node)
        return name

    def link(self, src: str, dst: str, output: int = 0) -> None:
        outs = self.connections.setdefault(src, {"main": []})["main"]
        while len(outs) <= output:
            outs.append([])
        outs[output].append({"node": dst, "type": "main", "index": 0})

    def dump(self) -> dict:
        # versionId es obligatorio al importar por CLI (n8n import:workflow); sin él falla con NOT NULL.
        return {"id": self.wf_id, "name": self.name, "versionId": _id(self.name + "/version"),
                "nodes": self.nodes, "connections": self.connections,
                "active": False, "pinData": {},
                "settings": {"executionOrder": "v1", "executionTimeout": EXECUTION_TIMEOUT_S, "timezone": "America/Bogota",
                             "saveDataErrorExecution": "all"},
                "tags": []}


# ------------------------------------------------------------------ fábricas de nodos
def webhook(wf, name, method, path, pos):
    return wf.add(name, "n8n-nodes-base.webhook", 2,
                  {"httpMethod": method, "path": path, "responseMode": "responseNode", "options": {}},
                  pos, webhookId=_id("webhook/" + path))


def code(wf, name, js, pos, **extra):
    return wf.add(name, "n8n-nodes-base.code", 2, {"jsCode": LIB + "\n\n// ---- nodo ----\n" + js.strip()}, pos, **extra)


def respond(wf, name, body_expr, status, pos):
    return wf.add(name, "n8n-nodes-base.respondToWebhook", 1.1,
                  {"respondWith": "json", "responseBody": "={{ JSON.stringify(" + body_expr + ") }}",
                   "options": {"responseCode": status}}, pos)


def postgres(wf, name, query, params_expr, pos, **extra):
    p = {"operation": "executeQuery", "query": query, "options": {}}
    if params_expr:
        p["options"]["queryReplacement"] = "={{ " + params_expr + " }}"
    return wf.add(name, "n8n-nodes-base.postgres", 2.5, p, pos, credentials=CRED_PG, **extra)


def http_json(wf, name, url, body_expr, pos, timeout_ms=5000, cred=None, cred_type=None, method="POST", **extra):
    p = {"method": method, "url": url, "sendBody": True, "specifyBody": "json",
         "jsonBody": "={{ JSON.stringify(" + body_expr + ") }}", "options": {"timeout": timeout_ms}}
    kw = dict(extra)
    if cred:
        p["authentication"] = "predefinedCredentialType"
        p["nodeCredentialType"] = cred_type
        kw["credentials"] = cred
    return wf.add(name, "n8n-nodes-base.httpRequest", 4.2, p, pos, **kw)


def if_node(wf, name, left_expr, op_type, operation, pos, right=""):
    cond = {"id": _id(wf.name + "/if/" + name), "leftValue": "={{ " + left_expr + " }}", "rightValue": right,
            "operator": {"type": op_type, "operation": operation, "singleValue": True}}
    return wf.add(name, "n8n-nodes-base.if", 2,
                  {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                                  "conditions": [cond], "combinator": "and"}, "options": {}}, pos)


def sheets_read(wf, name, pos, **extra):
    return wf.add(name, "n8n-nodes-base.googleSheets", 4.5, {
        "authentication": "serviceAccount",
        "operation": "read",
        "documentId": {"__rl": True, "value": "={{ $env.GOOGLE_SHEET_ID }}", "mode": "id"},
        "sheetName": {"__rl": True, "value": "={{ $env.GOOGLE_SHEET_NAME || 'Calendario Académico' }}", "mode": "name"},
        "options": {},
    }, pos, credentials=CRED_GOOGLE, **extra)


def llm_body(messages_expr: str, max_tokens: int, temperature: float) -> str:
    # max_tokens de la respuesta se puede bajar con LLM_MAX_TOKENS (respuestas más cortas = más rápidas en CPU)
    mt = f"Math.min({max_tokens}, parseInt($env.LLM_MAX_TOKENS, 10) || {max_tokens})"
    return ("{ model: $env.LLM_MODEL || 'qwen2.5:1.5b', messages: " + messages_expr +
            f", temperature: {temperature}, max_tokens: {mt} }}")


PREP_JS = """
const req = $input.first().json;
const body = req.body || {};
return [{ json: {
  token: bearerToken(req.headers),
  message: typeof body.message === 'string' ? body.message : '',
  fcm_token: typeof body.fcm_token === 'string' ? body.fcm_token : '',
  // Chat sin login: el ID llega en el cuerpo (POST) o en ?student_id= (GET)
  student_id: String((typeof body.student_id === 'string' && body.student_id) || (req.query || {}).student_id || '')
    .trim().toUpperCase().slice(0, 20),
} }];
"""

ERR_UNAVAILABLE = "{ error: 'El servicio no está disponible en este momento. Intenta de nuevo en unos minutos.' }"
ERR_SESSION = "{ error: 'Tu sesión expiró. Inicia sesión de nuevo.' }"
ERR_SESSION_OR_ID = "{ error: 'No encontramos ese ID de estudiante (o tu sesión expiró).' }"

SQL_TOKEN = "SELECT v.session_id FROM (SELECT 1) AS uno LEFT JOIN LATERAL validate_session($1) v ON true"
# Chat sin login: token Bearer válido o, si no hay, el student_id del cuerpo (session_by_student).
SQL_TOKEN_OR_ID = ("SELECT v.session_id FROM (SELECT 1) AS uno LEFT JOIN LATERAL ("
                   "SELECT session_id FROM validate_session($1) "
                   "UNION ALL SELECT session_id FROM session_by_student(NULLIF($2, '')) LIMIT 1) v ON true")


def auth_chain(wf, x0, y, webhook_name, method, path, allow_student_id=False):
    """Webhook → Preparar petición → Validar sesión → ¿Sesión válida?  (retorna el nombre del IF)."""
    webhook(wf, webhook_name, method, path, (x0, y))
    code(wf, "Preparar petición", PREP_JS, (x0 + 220, y))
    # LEFT JOIN: siempre una fila (session_id NULL si el token no es válido)
    postgres(wf, "Validar sesión",
             SQL_TOKEN_OR_ID if allow_student_id else SQL_TOKEN,
             "[ $json.token, $json.student_id ]" if allow_student_id else "[ $json.token ]",
             (x0 + 440, y), onError="continueErrorOutput")
    if_node(wf, "¿Sesión válida?", "$json.session_id", "string", "notEmpty", (x0 + 660, y))
    respond(wf, "Responder 401", ERR_SESSION_OR_ID if allow_student_id else ERR_SESSION, 401, (x0 + 880, y + 200))
    respond(wf, "Responder 503 (BD)", ERR_UNAVAILABLE, 503, (x0 + 660, y + 400))
    wf.link(webhook_name, "Preparar petición")
    wf.link("Preparar petición", "Validar sesión")
    wf.link("Validar sesión", "¿Sesión válida?", 0)
    wf.link("Validar sesión", "Responder 503 (BD)", 1)
    wf.link("¿Sesión válida?", "Responder 401", 1)
    return "¿Sesión válida?"


# ================================================================== 1. Chat (ruteo + 4 flujos)
def build_chat() -> dict:
    wf = WF("UNAB Chatbot - Chat (Ruteo por Intención)", "unabChatRouting1")
    auth_chain(wf, 0, 300, "Webhook chat", "POST", "chat", allow_student_id=True)
    S = "$('Validar sesión').first().json.session_id"
    M = "$('Preparar petición').first().json.message"

    postgres(wf, "Cargar historial", "SELECT get_recent_history($1, 10) AS history", f"[ {S} ]",
             (880, 300), onError="continueErrorOutput")
    http_json(wf, "Guardrails entrada", f"{GUARDRAILS}/validate-input", f"{{ session_id: {S}, message: {M} }}",
              (1100, 300), timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    if_node(wf, "¿Entrada permitida?", "$json.allowed", "boolean", "true", (1320, 300))
    respond(wf, "Responder mensaje rechazado",
            "{ error: 'No pude procesar tu mensaje. Reformula tu pregunta sobre temas académicos de la UNAB.' }",
            400, (1540, 500))
    classifier_prompt = json.dumps(
        "Clasifica el mensaje del estudiante en exactamente una de estas etiquetas: "
        "consulta-general (reglamento estudiantil, normas de evaluación, exámenes, supletorios, habilitaciones, "
        "requisitos de grado, programas, competencias, trámites y documentos institucionales), "
        "calendario (fechas académicas: matrículas, parciales, inicio o fin de clases, plazos), "
        "cursos-realizados (SOLO el historial personal del estudiante que pregunta: mis cursos aprobados, "
        "pendientes o en curso, mis notas, mi avance), "
        "noticias (noticias, eventos o novedades recientes de la universidad). "
        "Responde solo con la etiqueta.", ensure_ascii=False)
    http_json(wf, "Clasificar intención", OPENAI_URL,
              llm_body(f"[{{ role: 'system', content: {classifier_prompt} }}, {{ role: 'user', content: {M} }}]", 10, 0),
              (1540, 300), timeout_ms=CLASSIFIER_TIMEOUT_MS, cred=CRED_OPENAI, cred_type="openAiApi", onError="continueErrorOutput")
    # Ruteo por reglas primero; solo si no hay una coincidencia clara se consulta al LLM
    code(wf, "Intención por reglas", f"""
return [{{ json: {{ rule_intent: ruleIntent({M}) || '' }} }}];
""", (1430, 300))
    if_node(wf, "¿Regla clara?", "$json.rule_intent", "string", "notEmpty", (1540, 150))
    code(wf, "Normalizar intención", f"""
const inp = $input.first().json;
const intent = inp.rule_intent || normalizeIntent(llmText(inp));
return [{{ json: {{
  intent,
  route: INTENT_LABELS.indexOf(intent),
  session_id: {S},
  message: {M},
  history: $('Cargar historial').first().json.history,
}} }}];
""", (1760, 300))
    wf.add("Enrutar por intención", "n8n-nodes-base.switch", 3,
           {"mode": "expression", "numberOutputs": 4, "output": "={{ $json.route }}"}, (1980, 300))

    wf.link("¿Sesión válida?", "Cargar historial", 0)
    wf.link("Cargar historial", "Guardrails entrada", 0)
    wf.link("Cargar historial", "Responder 503 (BD)", 1)
    wf.link("Guardrails entrada", "¿Entrada permitida?", 0)
    wf.link("Guardrails entrada", "Responder 503 (BD)", 1)
    wf.link("¿Entrada permitida?", "Intención por reglas", 0)
    wf.link("Intención por reglas", "¿Regla clara?")
    wf.link("¿Regla clara?", "Normalizar intención", 0)
    wf.link("¿Regla clara?", "Clasificar intención", 1)
    wf.link("¿Entrada permitida?", "Responder mensaje rechazado", 1)
    wf.link("Clasificar intención", "Normalizar intención", 0)
    wf.link("Clasificar intención", "Normalizar intención", 1)  # error → fallback consulta-general
    wf.link("Normalizar intención", "Enrutar por intención")

    I = "$('Normalizar intención').first().json"
    respond_fixed = lambda name, text, y: respond(wf, name, f"{{ response: {json.dumps(text, ensure_ascii=False)}, intent: {I}.intent }}", 200, (2640, y))

    # --- 0. Consulta general (RAG)
    http_json(wf, "Buscar documentos (MCP)", f"{MCP}/tools/search_documents",
              f"{{ query: {I}.message, top_k: 5 }}", (2200, 0), timeout_ms=20000, onError="continueErrorOutput")
    code(wf, "Prompt consulta general", f"""
const ctx = {I};
const chunks = $input.first().json.chunks || [];
return [{{ json: {{ messages: buildMessages(ragContext(chunks), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 0))
    respond_fixed("Responder RAG no disponible",
                  "En este momento no puedo consultar los documentos institucionales. Intenta de nuevo en unos minutos.", -150)
    wf.link("Enrutar por intención", "Buscar documentos (MCP)", 0)
    wf.link("Buscar documentos (MCP)", "Prompt consulta general", 0)
    wf.link("Buscar documentos (MCP)", "Responder RAG no disponible", 1)

    # --- 1. Calendario (Google Sheets)
    sheets_read(wf, "Leer calendario (Sheets)", (2200, 200), alwaysOutputData=True, onError="continueRegularOutput")
    if_node(wf, "¿Calendario disponible?", "$json.error", "string", "empty", (2310, 200))
    code(wf, "Prompt calendario", f"""
const ctx = {I};
const events = calendarEvents($input.all().map((i) => i.json));
return [{{ json: {{ messages: buildMessages(calendarContext(events), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 200))
    respond_fixed("Responder calendario no disponible",
                  "El calendario académico está temporalmente no disponible. Intenta de nuevo más tarde.", 100)
    wf.link("Enrutar por intención", "Leer calendario (Sheets)", 1)
    wf.link("Leer calendario (Sheets)", "¿Calendario disponible?")
    wf.link("¿Calendario disponible?", "Prompt calendario", 0)
    wf.link("¿Calendario disponible?", "Responder calendario no disponible", 1)

    # --- 2. Cursos realizados (MCP → BD Estudiantes)
    http_json(wf, "Cursos del estudiante (MCP)", f"{MCP}/tools/get_student_courses",
              f"{{ session_id: {I}.session_id }}", (2200, 400), timeout_ms=4000, onError="continueErrorOutput")
    code(wf, "Prompt cursos", f"""
const ctx = {I};
return [{{ json: {{ messages: buildMessages(coursesContext($input.first().json), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 400))
    code(wf, "Registrar fallo BD Estudiantes", f"""
console.error('[cursos-realizados] BD Estudiantes inalcanzable', JSON.stringify($input.first().json).slice(0, 500));
return [{{ json: {{ logged: true }} }}];
""", (2420, 560))
    respond_fixed("Responder cursos no disponible",
                  "No pude consultar tu historial académico en este momento. Intenta de nuevo más tarde.", 560)
    wf.link("Enrutar por intención", "Cursos del estudiante (MCP)", 2)
    wf.link("Cursos del estudiante (MCP)", "Prompt cursos", 0)
    wf.link("Cursos del estudiante (MCP)", "Registrar fallo BD Estudiantes", 1)
    wf.link("Registrar fallo BD Estudiantes", "Responder cursos no disponible")

    # --- 3. Noticias
    postgres(wf, "Consultar noticias",
             "SELECT COALESCE(json_agg(n ORDER BY n.published_at DESC), '[]'::json) AS news FROM ("
             "SELECT title, published_at, summary, source_url FROM noticias ORDER BY published_at DESC LIMIT 20) n",
             None, (2200, 760), onError="continueErrorOutput")
    if_node(wf, "¿Hay noticias?", "($json.news || []).length", "number", "gt", (2420, 760), right=0)
    code(wf, "Prompt noticias", f"""
const ctx = {I};
return [{{ json: {{ messages: buildMessages(newsContext($input.first().json.news), ctx.history, ctx.message, {HIST}) }} }}];
""", (2640, 760))
    respond_fixed("Responder sin noticias", "No hay noticias recientes disponibles.", 920)
    wf.link("Enrutar por intención", "Consultar noticias", 3)
    wf.link("Consultar noticias", "¿Hay noticias?", 0)
    wf.link("Consultar noticias", "Responder 503 (BD)", 1)
    wf.link("¿Hay noticias?", "Prompt noticias", 0)
    wf.link("¿Hay noticias?", "Responder sin noticias", 1)

    # --- Común: LLM → guardrails salida → memoria → respuesta
    http_json(wf, "Generar respuesta (LLM)", OPENAI_URL, llm_body("$json.messages", 700, 0.1), (2900, 300),
              timeout_ms=LLM_TIMEOUT_MS, cred=CRED_OPENAI, cred_type="openAiApi", onError="continueErrorOutput")
    respond(wf, "Responder error LLM",
            "{ error: 'El asistente tardó demasiado en responder. Intenta de nuevo.' }", 504, (3120, 520))
    code(wf, "Extraer respuesta", "return [{ json: { llm_response: llmText($input.first().json) } }];", (3120, 300))
    http_json(wf, "Guardrails salida", f"{GUARDRAILS}/validate-output",
              f"{{ session_id: {I}.session_id, response: $json.llm_response }}", (3340, 300),
              timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    code(wf, "Respuesta final", """
const g = $input.first().json;
// Si guardrails falla o no responde, se aplica el fallback (fail-closed).
const response = typeof g.sanitized_response === 'string' && g.sanitized_response ? g.sanitized_response : FALLBACK_RESPONSE;
return [{ json: { response } }];
""", (3560, 300))
    postgres(wf, "Guardar memoria", "SELECT save_exchange($1, $2, $3)",
             f"[ {I}.session_id, {I}.message, $json.response ]", (3780, 300), onError="continueRegularOutput")
    respond(wf, "Responder OK", f"{{ response: $('Respuesta final').first().json.response, intent: {I}.intent }}",
            200, (4000, 300))
    for p in ["Prompt consulta general", "Prompt calendario", "Prompt cursos", "Prompt noticias"]:
        wf.link(p, "Generar respuesta (LLM)")
    wf.link("Generar respuesta (LLM)", "Extraer respuesta", 0)
    wf.link("Generar respuesta (LLM)", "Responder error LLM", 1)
    wf.link("Extraer respuesta", "Guardrails salida")
    wf.link("Guardrails salida", "Respuesta final", 0)
    wf.link("Guardrails salida", "Respuesta final", 1)
    wf.link("Respuesta final", "Guardar memoria")
    wf.link("Guardar memoria", "Responder OK")
    return wf.dump()


# ================================================================== 2. Login
def build_login() -> dict:
    wf = WF("UNAB Chatbot - Login", "unabChatLogin001")
    webhook(wf, "Webhook login", "POST", "login", (0, 300))
    code(wf, "Leer credenciales", """
const b = $input.first().json.body || {};
return [{ json: { student_id: String(b.student_id || '').trim().toUpperCase(), password: String(b.password || '') } }];
""", (220, 300))
    postgres(wf, "Autenticar",
             "SELECT l.* FROM (SELECT 1) AS uno LEFT JOIN LATERAL login_student($1, $2) l ON true",
             "[ $json.student_id, $json.password ]", (440, 300), onError="continueErrorOutput")
    if_node(wf, "¿Credenciales válidas?", "$json.token", "string", "notEmpty", (660, 300))
    respond(wf, "Responder token",
            "{ token: $json.token, session_id: $json.session_id, expires_at: $json.expires_at, full_name: $json.full_name }",
            200, (880, 200))
    respond(wf, "Responder 401", "{ error: 'Usuario o contraseña incorrectos.' }", 401, (880, 400))
    respond(wf, "Responder 503", ERR_UNAVAILABLE, 503, (660, 520))
    wf.link("Webhook login", "Leer credenciales")
    wf.link("Leer credenciales", "Autenticar")
    wf.link("Autenticar", "¿Credenciales válidas?", 0)
    wf.link("Autenticar", "Responder 503", 1)
    wf.link("¿Credenciales válidas?", "Responder token", 0)
    wf.link("¿Credenciales válidas?", "Responder 401", 1)
    return wf.dump()


# ================================================================== 3. Ruta académica (pantalla)
def build_academic_route() -> dict:
    wf = WF("UNAB Chatbot - Ruta Académica (GET)", "unabAcadRoute001")
    auth_chain(wf, 0, 300, "Webhook academic-route", "GET", "academic-route", allow_student_id=True)
    http_json(wf, "Cursos del estudiante (MCP)", f"{MCP}/tools/get_student_courses",
              "{ session_id: $json.session_id }", (880, 200), timeout_ms=5000, onError="continueErrorOutput")
    respond(wf, "Responder cursos",
            "{ courses: $json.courses || [], progress_percentage: $json.progress_percentage || 0 }", 200, (1100, 200))
    wf.link("¿Sesión válida?", "Cursos del estudiante (MCP)", 0)
    wf.link("Cursos del estudiante (MCP)", "Responder cursos", 0)
    wf.link("Cursos del estudiante (MCP)", "Responder 503 (BD)", 1)
    return wf.dump()


# ================================================================== 4. Calendario (pantalla)
def build_calendar() -> dict:
    wf = WF("UNAB Chatbot - Calendario (GET)", "unabCalendar0001")
    auth_chain(wf, 0, 300, "Webhook calendar", "GET", "calendar", allow_student_id=True)
    sheets_read(wf, "Leer calendario (Sheets)", (880, 200), alwaysOutputData=True, onError="continueRegularOutput")
    if_node(wf, "¿Calendario disponible?", "$json.error", "string", "empty", (990, 200))
    code(wf, "Formatear eventos", "return [{ json: { events: calendarEvents($input.all().map((i) => i.json)) } }];",
         (1100, 200))
    respond(wf, "Responder eventos", "{ events: $json.events }", 200, (1320, 200))
    wf.link("¿Sesión válida?", "Leer calendario (Sheets)", 0)
    wf.link("Leer calendario (Sheets)", "¿Calendario disponible?")
    wf.link("¿Calendario disponible?", "Formatear eventos", 0)
    wf.link("¿Calendario disponible?", "Responder 503 (BD)", 1)
    wf.link("Formatear eventos", "Responder eventos")
    return wf.dump()


# ================================================================== 5. Registro de dispositivo FCM
def build_register_device() -> dict:
    wf = WF("UNAB Chatbot - Registrar dispositivo", "unabRegDevice001")
    auth_chain(wf, 0, 300, "Webhook register-device", "POST", "register-device")
    if_node(wf, "¿Token FCM presente?", "$('Preparar petición').first().json.fcm_token", "string", "notEmpty", (880, 200))
    postgres(wf, "Guardar token FCM",
             "INSERT INTO device_tokens (session_id, fcm_token) VALUES ($1, $2) "
             "ON CONFLICT (session_id, fcm_token) DO UPDATE SET updated_at = now()",
             "[ $('Validar sesión').first().json.session_id, $('Preparar petición').first().json.fcm_token ]",
             (1100, 100), onError="continueErrorOutput")
    respond(wf, "Responder OK", "{ ok: true }", 200, (1320, 100))
    respond(wf, "Responder 400", "{ error: 'Falta el token del dispositivo.' }", 400, (1100, 300))
    wf.link("¿Sesión válida?", "¿Token FCM presente?", 0)
    wf.link("¿Token FCM presente?", "Guardar token FCM", 0)
    wf.link("¿Token FCM presente?", "Responder 400", 1)
    wf.link("Guardar token FCM", "Responder OK", 0)
    wf.link("Guardar token FCM", "Responder 503 (BD)", 1)
    return wf.dump()


# ================================================================== 6. Notificaciones push (cron)
def build_push() -> dict:
    wf = WF("UNAB Chatbot - Notificaciones Push (cada hora)", "unabPushNotif001")
    wf.add("Cada hora", "n8n-nodes-base.scheduleTrigger", 1.2,
           {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}, (0, 300))
    sheets_read(wf, "Leer calendario (Sheets)", (220, 300), alwaysOutputData=True)
    code(wf, "Eventos en ventana 48h", """
const events = eventsInWindow(calendarEvents($input.all().map((i) => i.json)), new Date(), 48);
return [{ json: { events_json: JSON.stringify(events), count: events.length } }];
""", (440, 300))
    postgres(wf, "Pendientes por notificar", "SELECT * FROM pending_notifications($1::jsonb)", "[ $json.events_json ]",
             (660, 300))
    http_json(wf, "Enviar FCM", "=https://fcm.googleapis.com/v1/projects/{{ $env.FCM_PROJECT_ID }}/messages:send",
              "{ message: { token: $json.fcm_token, "
              "data: { type: 'calendar_event', event_key: $json.event_key, event_name: $json.event_name, "
              "event_date: $json.event_date, title: 'Recordatorio académico UNAB', "
              "body: $json.event_name + ' — ' + $json.event_date }, "
              "android: { priority: 'high' } } }",
              (880, 300), timeout_ms=10000, cred=CRED_GOOGLE, cred_type="googleApi", onError="continueErrorOutput")
    postgres(wf, "Marcar como enviada",
             "INSERT INTO notifications_sent (event_key, session_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
             "[ $('Pendientes por notificar').item.json.event_key, $('Pendientes por notificar').item.json.session_id ]",
             (1100, 200))
    code(wf, "Registrar fallo FCM", """
for (const i of $input.all()) console.error('[push] Error enviando FCM', JSON.stringify(i.json).slice(0, 300));
return [{ json: { failed: $input.all().length } }];
""", (1100, 400))
    wf.link("Cada hora", "Leer calendario (Sheets)")
    wf.link("Leer calendario (Sheets)", "Eventos en ventana 48h")
    wf.link("Eventos en ventana 48h", "Pendientes por notificar")
    wf.link("Pendientes por notificar", "Enviar FCM")
    wf.link("Enviar FCM", "Marcar como enviada", 0)
    wf.link("Enviar FCM", "Registrar fallo FCM", 1)
    return wf.dump()


# ================================================================== 7. Buscar estudiante (chat sin login)
def build_student_lookup() -> dict:
    wf = WF("UNAB Chatbot - Buscar estudiante por ID", "unabChatLookup01")
    webhook(wf, "Webhook buscar estudiante", "POST", "student-lookup", (0, 300))
    code(wf, "Leer ID", """
const b = $input.first().json.body || {};
return [{ json: { student_id: String(b.student_id || '').trim().toUpperCase().slice(0, 20) } }];
""", (220, 300))
    postgres(wf, "Buscar en BD",
             "SELECT l.* FROM (SELECT 1) AS uno LEFT JOIN LATERAL session_by_student(NULLIF($1, '')) l ON true",
             "[ $json.student_id ]", (440, 300), onError="continueErrorOutput")
    if_node(wf, "¿Estudiante existe?", "$json.student_id", "string", "notEmpty", (660, 300))
    respond(wf, "Responder estudiante",
            "{ student_id: $json.student_id, full_name: $json.full_name, program: $json.program, "
            "current_semester: $json.current_semester, progress_percentage: Number($json.progress_percentage) }",
            200, (880, 200))
    respond(wf, "Responder 404", "{ error: 'No encontramos ese ID de estudiante.' }", 404, (880, 400))
    respond(wf, "Responder 503", ERR_UNAVAILABLE, 503, (660, 520))
    wf.link("Webhook buscar estudiante", "Leer ID")
    wf.link("Leer ID", "Buscar en BD")
    wf.link("Buscar en BD", "¿Estudiante existe?", 0)
    wf.link("Buscar en BD", "Responder 503", 1)
    wf.link("¿Estudiante existe?", "Responder estudiante", 0)
    wf.link("¿Estudiante existe?", "Responder 404", 1)
    return wf.dump()


BUILDERS = {
    "01_chat_ruteo.json": build_chat,
    "02_login.json": build_login,
    "03_ruta_academica.json": build_academic_route,
    "04_calendario.json": build_calendar,
    "05_registrar_dispositivo.json": build_register_device,
    "06_notificaciones_push.json": build_push,
    "07_buscar_estudiante.json": build_student_lookup,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, fn in BUILDERS.items():
        (OUT / fname).write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
        print("generado", OUT / fname)


if __name__ == "__main__":
    main()
