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
CRED_OLLAMA = {"ollamaApi": {"id": "unabOllamaApi001", "name": "Ollama local"}}

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
    def __init__(self, name: str, wf_id: str, x_scale: float = 1.0) -> None:
        self.name, self.wf_id = name, wf_id
        self.x_scale = x_scale  # separa los nodos en el lienzo de n8n
        self.nodes: list[dict] = []
        self.connections: dict[str, dict] = {}

    def add(self, name, type_, version, params, pos, **extra) -> str:
        node = {"id": _id(self.name + "/" + name), "name": name, "type": type_, "typeVersion": version,
                "position": [round(pos[0] * self.x_scale), pos[1]], "parameters": params}
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


SQL_CALENDAR = ("SELECT event_name, to_char(event_date, 'YYYY-MM-DD') AS event_date, description "
                "FROM academic_calendar ORDER BY event_date")


def calendar_read(wf, name, pos, **extra):
    """Calendario académico desde PostgreSQL (tabla academic_calendar, db/academico.sql)."""
    return postgres(wf, name, SQL_CALENDAR, None, pos, **extra)


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

# Mensaje al estudiante cuando los guardrails rechazan la entrada (según el motivo)
REJECT_EXPR = ("{ error: String($json.reason || '').startsWith('Tarea') ? "
               "'Solo respondo consultas informativas de la universidad: matrícula, estado académico, proyección, "
               "reglamento, calendario, materias y noticias. No resuelvo operaciones, ejercicios ni tareas.' : "
               "'Solo puedo ayudarte con consultas informativas de la UNAB (matrícula, materias, reglamento, "
               "calendario, noticias). Reformula tu pregunta.' }")
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
    wf = WF("UNAB Chatbot - Chat (Ruteo por Intención)", "unabChatRouting1", x_scale=1.6)
    auth_chain(wf, 0, 300, "Webhook chat", "POST", "chat", allow_student_id=True)
    S = "$('Validar sesión').first().json.session_id"
    M = "$('Preparar petición').first().json.message"

    # ¿El mensaje responde a una solicitud de envío por correo pendiente ("sí", un correo nuevo o "no")?
    http_json(wf, "Correo pendiente (MCP)", f"{MCP}/tools/confirm_email", f"{{ session_id: {S}, message: {M} }}",
              (770, 140), timeout_ms=60000, onError="continueRegularOutput")
    if_node(wf, "¿Respuesta de correo?", "$json.handled", "boolean", "true", (880, 140))
    respond(wf, "Responder correo", "{ response: $json.reply, intent: 'correo' }", 200, (1100, 0))
    postgres(wf, "Cargar historial", "SELECT get_recent_history($1, 10) AS history", f"[ {S} ]",
             (880, 300), onError="continueErrorOutput")
    http_json(wf, "Guardrails entrada", f"{GUARDRAILS}/validate-input", f"{{ session_id: {S}, message: {M} }}",
              (1100, 300), timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    if_node(wf, "¿Entrada permitida?", "$json.allowed", "boolean", "true", (1320, 300))
    respond(wf, "Responder mensaje rechazado",
            REJECT_EXPR,
            400, (1540, 500))
    classifier_prompt = json.dumps(
        "Clasifica el mensaje del estudiante en exactamente una de estas etiquetas: "
        "consulta-general (reglamento estudiantil, normas de evaluación, exámenes, supletorios, habilitaciones, "
        "requisitos de grado, programas, competencias, trámites y documentos institucionales), "
        "calendario (fechas académicas: matrículas, parciales, inicio o fin de clases, plazos), "
        "cursos-realizados (SOLO el historial personal del estudiante que pregunta: mis cursos aprobados, "
        "pendientes o en curso, mis notas, mi avance), "
        "noticias (noticias, eventos o novedades recientes de la universidad, educación o tecnología), "
        "plan-academico (qué materias matricular el próximo semestre, estado académico y promedio, "
        "proyección o fecha estimada de grado, recomendaciones personalizadas para tener éxito), "
        "correo (pide que le ENVÍEN por correo noticias, su informe de avance o su informe de materias), "
        "competencias-digitales (SUS cursos del Centro de Competencias Digitales, su prueba diagnóstica o su avance "
        "hacia la insignia; si pregunta qué ES la insignia o el CCD, es consulta-general). "
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
  news_category: newsCategory({M}),
}} }}];
""", (1760, 300))
    wf.add("Enrutar por intención", "n8n-nodes-base.switch", 3,
           {"mode": "expression", "numberOutputs": 7, "output": "={{ $json.route }}"}, (1980, 300))

    wf.link("¿Sesión válida?", "Correo pendiente (MCP)", 0)
    wf.link("Correo pendiente (MCP)", "¿Respuesta de correo?")
    wf.link("¿Respuesta de correo?", "Responder correo", 0)
    wf.link("¿Respuesta de correo?", "Cargar historial", 1)
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
              f"{{ query: {I}.message, top_k: Math.min(5, parseInt($env.RAG_TOP_K, 10) || 3) }}", (2200, 0), timeout_ms=20000, onError="continueErrorOutput")
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

    # --- 1. Calendario (PostgreSQL: academic_calendar)
    calendar_read(wf, "Leer calendario (BD)", (2200, 200), alwaysOutputData=True, onError="continueRegularOutput")
    if_node(wf, "¿Calendario disponible?", "$json.error", "string", "empty", (2310, 200))
    code(wf, "Prompt calendario", f"""
const ctx = {I};
const events = calendarEvents($input.all().map((i) => i.json));
return [{{ json: {{ messages: buildMessages(calendarContext(events), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 200))
    respond_fixed("Responder calendario no disponible",
                  "El calendario académico está temporalmente no disponible. Intenta de nuevo más tarde.", 100)
    wf.link("Enrutar por intención", "Leer calendario (BD)", 1)
    wf.link("Leer calendario (BD)", "¿Calendario disponible?")
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
             "SELECT title, published_at, summary, source_url, category, source_name FROM noticias "
             "WHERE $1 = '' OR category = $1 ORDER BY published_at DESC LIMIT 20) n",
             f"[ {I}.news_category ]", (2200, 760), onError="continueErrorOutput")
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

    # --- 4. Plan académico: matrícula, estado académico, proyección y recomendaciones (MCP → SQL)
    http_json(wf, "Plan académico (MCP)", f"{MCP}/tools/get_academic_plan",
              f"{{ session_id: {I}.session_id }}", (2200, 1000), timeout_ms=8000, onError="continueErrorOutput")
    code(wf, "Prompt plan académico", f"""
const ctx = {I};
return [{{ json: {{ messages: buildMessages(planContext($input.first().json), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 1000))
    respond_fixed("Responder plan no disponible",
                  "No pude calcular tu plan académico en este momento. Intenta de nuevo más tarde.", 1160)
    wf.link("Enrutar por intención", "Plan académico (MCP)", 4)
    wf.link("Plan académico (MCP)", "Prompt plan académico", 0)
    wf.link("Plan académico (MCP)", "Responder plan no disponible", 1)

    # --- 5. Correo: solo noticias, informe de avance o informe de materias (respuesta sin LLM)
    http_json(wf, "Solicitar envío (MCP)", f"{MCP}/tools/request_email",
              f"{{ session_id: {I}.session_id, message: {I}.message }}", (2200, 1300), timeout_ms=10000,
              onError="continueErrorOutput")
    respond(wf, "Responder solicitud de correo", f"{{ response: $json.reply, intent: 'correo' }}", 200, (2420, 1300))
    respond_fixed("Responder correo no disponible",
                  "El envío de correos no está disponible en este momento. Intenta más tarde.", 1460)
    wf.link("Enrutar por intención", "Solicitar envío (MCP)", 5)
    wf.link("Solicitar envío (MCP)", "Responder solicitud de correo", 0)
    wf.link("Solicitar envío (MCP)", "Responder correo no disponible", 1)

    # --- 6. Competencias digitales: cursos del CCD del estudiante y avance hacia la insignia (MCP → SQL)
    http_json(wf, "Cursos CCD (MCP)", f"{MCP}/tools/get_ccd_progress",
              f"{{ session_id: {I}.session_id }}", (2200, 1600), timeout_ms=8000, onError="continueErrorOutput")
    code(wf, "Prompt competencias digitales", f"""
const ctx = {I};
return [{{ json: {{ messages: buildMessages(ccdContext($input.first().json), ctx.history, ctx.message, {HIST}) }} }}];
""", (2420, 1600))
    respond_fixed("Responder CCD no disponible",
                  "No pude consultar tus cursos de competencias digitales en este momento. Intenta más tarde.", 1760)
    wf.link("Enrutar por intención", "Cursos CCD (MCP)", 6)
    wf.link("Cursos CCD (MCP)", "Prompt competencias digitales", 0)
    wf.link("Cursos CCD (MCP)", "Responder CCD no disponible", 1)

    # --- Común: LLM → guardrails salida → memoria → respuesta
    http_json(wf, "Generar respuesta (LLM)", OPENAI_URL, llm_body("$json.messages", 700, 0.1), (2900, 300),
              timeout_ms=LLM_TIMEOUT_MS, cred=CRED_OPENAI, cred_type="openAiApi", onError="continueErrorOutput")
    respond(wf, "Responder error LLM",
            "{ error: 'El asistente tardó demasiado en responder. Intenta de nuevo.' }", 504, (3120, 520))
    code(wf, "Extraer respuesta", "return [{ json: { llm_response: llmText($input.first().json) } }];", (3120, 300))
    http_json(wf, "Guardrails salida", f"{GUARDRAILS}/validate-output",
              f"{{ session_id: {I}.session_id, response: $json.llm_response, "
              f"trusted_context: {I}.intent === 'noticias' }}", (3340, 300),
              timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    code(wf, "Respuesta final", """
const g = $input.first().json;
// Si guardrails falla o no responde, se aplica el fallback (fail-closed).
let response = typeof g.sanitized_response === 'string' && g.sanitized_response ? g.sanitized_response : FALLBACK_RESPONSE;
const ctx = $('Normalizar intención').first().json;
if (ctx.intent === 'plan-academico' && response !== FALLBACK_RESPONSE) {
  try { response = ensureEnrollment(response, $('Plan académico (MCP)').first().json, ctx.message); } catch (e) {}
}
return [{ json: { response } }];
""", (3560, 300))
    postgres(wf, "Guardar memoria", "SELECT save_exchange($1, $2, $3)",
             f"[ {I}.session_id, {I}.message, $json.response ]", (3780, 300), onError="continueRegularOutput")
    respond(wf, "Responder OK", f"{{ response: $('Respuesta final').first().json.response, intent: {I}.intent }}",
            200, (4000, 300))
    for p in ["Prompt consulta general", "Prompt calendario", "Prompt cursos", "Prompt noticias", "Prompt plan académico",
              "Prompt competencias digitales"]:
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
    calendar_read(wf, "Leer calendario (BD)", (880, 200), alwaysOutputData=True, onError="continueRegularOutput")
    if_node(wf, "¿Calendario disponible?", "$json.error", "string", "empty", (990, 200))
    code(wf, "Formatear eventos", "return [{ json: { events: calendarEvents($input.all().map((i) => i.json)) } }];",
         (1100, 200))
    respond(wf, "Responder eventos", "{ events: $json.events }", 200, (1320, 200))
    wf.link("¿Sesión válida?", "Leer calendario (BD)", 0)
    wf.link("Leer calendario (BD)", "¿Calendario disponible?")
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
    calendar_read(wf, "Leer calendario (BD)", (220, 300), alwaysOutputData=True)
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
    wf.link("Cada hora", "Leer calendario (BD)")
    wf.link("Leer calendario (BD)", "Eventos en ventana 48h")
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


# ================================================================== 8. Plan académico (pantalla)
def build_academic_plan() -> dict:
    wf = WF("UNAB Chatbot - Plan Académico (GET)", "unabAcadPlan0001")
    auth_chain(wf, 0, 300, "Webhook academic-plan", "GET", "academic-plan", allow_student_id=True)
    http_json(wf, "Plan académico (MCP)", f"{MCP}/tools/get_academic_plan",
              "{ session_id: $json.session_id }", (880, 200), timeout_ms=8000, onError="continueErrorOutput")
    respond(wf, "Responder plan", "$json", 200, (1100, 200))
    wf.link("¿Sesión válida?", "Plan académico (MCP)", 0)
    wf.link("Plan académico (MCP)", "Responder plan", 0)
    wf.link("Plan académico (MCP)", "Responder 503 (BD)", 1)
    return wf.dump()


# ================================================================== 9. Noticias (pantalla)
def build_news() -> dict:
    wf = WF("UNAB Chatbot - Noticias (GET)", "unabNewsList0001")
    webhook(wf, "Webhook news", "GET", "news", (0, 300))
    code(wf, "Leer filtros", """
const q = $input.first().json.query || {};
const cat = String(q.category || '').toLowerCase();
return [{ json: {
  category: ['educacion', 'tecnologia', 'ingenieria-sistemas', 'general'].includes(cat) ? cat : '',
  limit: Math.min(50, Math.max(1, parseInt(q.limit, 10) || 20)),
  today_only: q.today === '1' || q.today === 'true',
} }];
""", (220, 300))
    http_json(wf, "Noticias (MCP)", f"{MCP}/tools/get_news", "$json", (440, 300), timeout_ms=8000,
              onError="continueErrorOutput")
    respond(wf, "Responder noticias", "{ news: $json.news || [] }", 200, (660, 200))
    respond(wf, "Responder 503", ERR_UNAVAILABLE, 503, (660, 400))
    wf.link("Webhook news", "Leer filtros")
    wf.link("Leer filtros", "Noticias (MCP)")
    wf.link("Noticias (MCP)", "Responder noticias", 0)
    wf.link("Noticias (MCP)", "Responder 503", 1)
    return wf.dump()


# ================================================================== 10. Scraper automático (cron)
def build_scraper() -> dict:
    wf = WF("UNAB Chatbot - Scraper de noticias (cada 6 h)", "unabNewsScrape01")
    wf.add("Cada 6 horas", "n8n-nodes-base.scheduleTrigger", 1.2,
           {"rule": {"interval": [{"field": "hours", "hoursInterval": 6}]}}, (0, 300))
    http_json(wf, "Ejecutar scraper (MCP)", f"{MCP}/tools/run_news_scraper", "{}", (220, 300), timeout_ms=120000)
    code(wf, "Resumen", """
const r = $input.first().json;
console.log('[scraper]', JSON.stringify(r));
return [{ json: r }];
""", (440, 300))
    wf.link("Cada 6 horas", "Ejecutar scraper (MCP)")
    wf.link("Ejecutar scraper (MCP)", "Resumen")
    return wf.dump()


# ================================================================== 11. Agente IA (AI Agent + MCP + memoria)
AGENT_SYSTEM = (
    "Eres el agente académico de la Universidad Autónoma de Bucaramanga (UNAB). El estudiante tiene el ID "
    "{{ $('Validar sesión').first().json.student_id }}.\n"
    "REGLA OBLIGATORIA: antes de responder SIEMPRE llamas una herramienta; nunca pidas datos al estudiante.\n"
    "- Matrícula, materias a inscribir, estado académico, promedio, proyección o fecha de grado, recomendaciones: "
    "llama get_academic_plan con student_id=\"{{ $('Validar sesión').first().json.student_id }}\".\n"
    "- Reglamento, plan de estudios, prerrequisitos, requisitos de grado: llama search_documents con la pregunta.\n"
    "- Sus cursos de competencias digitales (CCD), prueba diagnóstica o insignia: get_ccd_progress con student_id.\n"
    "- Fechas: get_academic_calendar. Noticias: get_news (category: educacion, tecnologia o ingenieria-sistemas).\n"
    "Luego responde en español, breve, en viñetas, con las cifras exactas de la herramienta. Aplica educación de "
    "precisión (consejos basados en los datos del estudiante) y fomenta el autoaprendizaje y la investigación. "
    "Solo atiendes temas académicos de la UNAB.")


def build_agent() -> dict:
    wf = WF("UNAB Chatbot - Agente IA (MCP)", "unabAgentMcp0001")
    webhook(wf, "Webhook agent", "POST", "agent", (0, 300))
    code(wf, "Preparar petición", PREP_JS, (220, 300))
    postgres(wf, "Validar sesión",
             "SELECT v.session_id, v.student_id FROM (SELECT 1) AS uno LEFT JOIN LATERAL "
             "session_by_student(NULLIF($1, '')) v ON true",
             "[ $json.student_id ]", (440, 300), onError="continueErrorOutput")
    if_node(wf, "¿Estudiante válido?", "$json.session_id", "string", "notEmpty", (660, 300))
    respond(wf, "Responder 401", ERR_SESSION_OR_ID, 401, (880, 520))
    respond(wf, "Responder 503", ERR_UNAVAILABLE, 503, (660, 700))
    M = "$('Preparar petición').first().json.message"
    S = "$('Validar sesión').first().json.session_id"
    http_json(wf, "Guardrails entrada", f"{GUARDRAILS}/validate-input", f"{{ session_id: {S}, message: {M} }}",
              (880, 300), timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    if_node(wf, "¿Entrada permitida?", "$json.allowed", "boolean", "true", (1100, 300))
    respond(wf, "Responder mensaje rechazado",
            REJECT_EXPR,
            400, (1320, 780))
    # Ítem limpio para el agente: el nodo MCP Client Tool envía los campos del ítem como argumentos
    code(wf, "Entrada del agente", f"return [{{ json: {{ chatInput: {M} }} }}];", (1320, 300))
    wf.add("Agente académico", "@n8n/n8n-nodes-langchain.agent", 3, {
        "promptType": "define",
        "text": "={{ $json.chatInput }}",
        "options": {"systemMessage": "=" + AGENT_SYSTEM, "maxIterations": 4},
    }, (1600, 300), onError="continueErrorOutput")
    wf.add("Modelo LLM (Ollama)", "@n8n/n8n-nodes-langchain.lmChatOllama", 1, {
        "model": "={{ $env.AGENT_LLM_MODEL || $env.LLM_MODEL || 'unab-llm' }}",
        "options": {"temperature": 0.1, "numCtx": 8192, "numPredict": 350},
    }, (1460, 560), credentials=CRED_OLLAMA)
    wf.add("Memoria (PostgreSQL)", "@n8n/n8n-nodes-langchain.memoryPostgresChat", 1.3, {
        "sessionIdType": "customKey",
        "sessionKey": "={{ " + S + " }}",
        "tableName": "n8n_chat_histories",
        "contextWindowLength": 4,
    }, (1640, 560), credentials=CRED_PG)
    wf.add("Herramientas MCP", "@n8n/n8n-nodes-langchain.mcpClientTool", 1.2, {
        "endpointUrl": f"{MCP}/mcp",
        "serverTransport": "httpStreamable",
        "include": "selected",
        "includeTools": ["get_academic_plan", "search_documents", "get_academic_calendar", "get_news", "get_ccd_progress"],
        "options": {"timeout": 60000},
    }, (1820, 560))
    http_json(wf, "Guardrails salida", f"{GUARDRAILS}/validate-output",
              f"{{ session_id: {S}, response: $json.output || '' }}", (2000, 300),
              timeout_ms=GUARDRAILS_TIMEOUT_MS, onError="continueErrorOutput")
    code(wf, "Respuesta final", """
const g = $input.first().json;
const response = typeof g.sanitized_response === 'string' && g.sanitized_response ? g.sanitized_response : FALLBACK_RESPONSE;
return [{ json: { response } }];
""", (2220, 300))
    respond(wf, "Responder OK", "{ response: $json.response, agent: true }", 200, (2440, 300))
    respond(wf, "Responder error agente",
            "{ error: 'El agente tardó demasiado o falló. Intenta de nuevo.' }", 504, (2000, 560))
    wf.link("Webhook agent", "Preparar petición")
    wf.link("Preparar petición", "Validar sesión")
    wf.link("Validar sesión", "¿Estudiante válido?", 0)
    wf.link("Validar sesión", "Responder 503", 1)
    wf.link("¿Estudiante válido?", "Guardrails entrada", 0)
    wf.link("¿Estudiante válido?", "Responder 401", 1)
    wf.link("Guardrails entrada", "¿Entrada permitida?", 0)
    wf.link("Guardrails entrada", "Responder 503", 1)
    wf.link("¿Entrada permitida?", "Entrada del agente", 0)
    wf.link("Entrada del agente", "Agente académico")
    wf.link("¿Entrada permitida?", "Responder mensaje rechazado", 1)
    wf.link("Agente académico", "Guardrails salida", 0)
    wf.link("Agente académico", "Responder error agente", 1)
    wf.link("Guardrails salida", "Respuesta final", 0)
    wf.link("Guardrails salida", "Respuesta final", 1)
    wf.link("Respuesta final", "Responder OK")
    # Sub-nodos del agente (conexiones ai_*)
    wf.connections["Modelo LLM (Ollama)"] = {"ai_languageModel": [[{"node": "Agente académico", "type": "ai_languageModel", "index": 0}]]}
    wf.connections["Memoria (PostgreSQL)"] = {"ai_memory": [[{"node": "Agente académico", "type": "ai_memory", "index": 0}]]}
    wf.connections["Herramientas MCP"] = {"ai_tool": [[{"node": "Agente académico", "type": "ai_tool", "index": 0}]]}
    return wf.dump()


# ================================================================== 12. Ingesta de documentos (RAG)
def build_ingest() -> dict:
    """Ingesta → chunking (220 tokens, overlap 30) → embeddings (granite) → pgvector, desde n8n.
    Se ejecuta a mano (botón "Execute workflow") o por POST /webhook/ingest con el encabezado x-ingest-token."""
    wf = WF("UNAB Chatbot - Ingesta de documentos (RAG)", "unabIngestDocs01")
    summary_js = """
const r = $input.first().json;
const ok = Array.isArray(r.errors) ? r.errors.length === 0 : false;
return [{ json: {
  ok,
  documentos: r.total_documents, procesados: r.processed_documents,
  chunks: r.total_chunks, embeddings: r.total_embeddings, errores: r.errors || [],
  parametros: { chunk_tokens: 220, overlap_tokens: 30, modelo_embeddings: 'granite-embedding:278m', indice: 'HNSW coseno' },
} }];
"""
    # a) Manual (desde la interfaz de n8n)
    wf.add("Ejecutar a mano", "n8n-nodes-base.manualTrigger", 1, {}, (0, 100))
    http_json(wf, "Ingerir documentos (MCP)", f"{MCP}/tools/ingest_documents", "{ file_paths: [] }", (240, 100),
              timeout_ms=600000)
    code(wf, "Resumen de ingesta", summary_js, (480, 100))
    wf.link("Ejecutar a mano", "Ingerir documentos (MCP)")
    wf.link("Ingerir documentos (MCP)", "Resumen de ingesta")
    # b) Webhook protegido con token
    webhook(wf, "Webhook ingest", "POST", "ingest", (0, 400))
    if_node(wf, "¿Token válido?",
            "($json.headers['x-ingest-token'] || '') !== '' && $json.headers['x-ingest-token'] === $env.INGEST_TOKEN",
            "boolean", "true", (240, 400))
    http_json(wf, "Ingerir documentos (webhook)", f"{MCP}/tools/ingest_documents",
              "{ file_paths: ($('Webhook ingest').first().json.body || {}).file_paths || [] }", (480, 300),
              timeout_ms=600000, onError="continueErrorOutput")
    code(wf, "Resumen (webhook)", summary_js, (720, 300))
    respond(wf, "Responder resumen", "$json", 200, (960, 300))
    respond(wf, "Responder 401 (token)", "{ error: 'Token inválido. Envía el encabezado x-ingest-token.' }", 401, (480, 520))
    respond(wf, "Responder 503 (ingesta)", ERR_UNAVAILABLE, 503, (720, 520))
    wf.link("Webhook ingest", "¿Token válido?")
    wf.link("¿Token válido?", "Ingerir documentos (webhook)", 0)
    wf.link("¿Token válido?", "Responder 401 (token)", 1)
    wf.link("Ingerir documentos (webhook)", "Resumen (webhook)", 0)
    wf.link("Ingerir documentos (webhook)", "Responder 503 (ingesta)", 1)
    wf.link("Resumen (webhook)", "Responder resumen")
    return wf.dump()


BUILDERS = {
    "01_chat_ruteo.json": build_chat,
    "02_login.json": build_login,
    "03_ruta_academica.json": build_academic_route,
    "04_calendario.json": build_calendar,
    "05_registrar_dispositivo.json": build_register_device,
    "06_notificaciones_push.json": build_push,
    "07_buscar_estudiante.json": build_student_lookup,
    "08_plan_academico.json": build_academic_plan,
    "09_noticias.json": build_news,
    "10_scraper_noticias.json": build_scraper,
    "11_agente_ia_mcp.json": build_agent,
    "12_ingesta_documentos.json": build_ingest,
}


def check_lib_syntax() -> None:
    """Falla si lib.js no es JavaScript válido (un error rompería TODOS los nodos Code)."""
    import shutil
    import subprocess
    if shutil.which("node"):
        subprocess.run(["node", "--check", str(ROOT / "code" / "lib.js")], check=True)


def main() -> None:
    check_lib_syntax()
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, fn in BUILDERS.items():
        (OUT / fname).write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
        print("generado", OUT / fname)


if __name__ == "__main__":
    main()
