// Funciones puras usadas dentro de los nodos Code de n8n.
// build_workflows.py inserta este archivo (hasta la marca de export) en cada nodo Code,
// y tests/test_n8n_code.py las prueba con Node.js.

const INTENT_LABELS = ['consulta-general', 'calendario', 'cursos-realizados', 'noticias'];

const FALLBACK_RESPONSE = 'Solo puedo ayudarte con temas académicos de la UNAB.';

const SYSTEM_BASE =
  'Eres el asistente académico de la Universidad Autónoma de Bucaramanga (UNAB). ' +
  'Responde SIEMPRE en español, de forma clara, breve y amable. ' +
  'Solo atiendes temas académicos e institucionales de la UNAB. ' +
  'Usa únicamente la información del contexto proporcionado; si no está, dilo con honestidad ' +
  'y sugiere la dependencia de la UNAB a la que el estudiante puede acudir. No inventes datos.';

const CLASSIFIER_PROMPT =
  'Clasifica el mensaje del estudiante en exactamente una de estas etiquetas:\n' +
  '- consulta-general: preguntas sobre normas, programas, plan de estudios, competencias, trámites o documentos institucionales.\n' +
  '- calendario: fechas académicas (matrículas, parciales, inicio/fin de clases, festivos, plazos).\n' +
  '- cursos-realizados: el progreso personal del estudiante (cursos aprobados, pendientes, en curso, notas, avance).\n' +
  '- noticias: noticias, eventos o novedades recientes de la universidad.\n' +
  'Responde solo con la etiqueta, sin explicación.';

function stripAccents(s) {
  return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '');
}

// Property 5: siempre devuelve exactamente una etiqueta válida.
function normalizeIntent(raw) {
  const text = stripAccents(raw == null ? '' : raw).toLowerCase().trim();
  const cleaned = text.replace(/[^a-z\- ]/g, ' ').replace(/\s+/g, ' ').trim();
  const asLabel = cleaned.replace(/ /g, '-');
  if (INTENT_LABELS.includes(asLabel)) return asLabel;
  const found = INTENT_LABELS.filter((l) => cleaned.includes(l) || cleaned.includes(l.replace('-', ' ')));
  if (found.length === 1) return found[0];
  return 'consulta-general'; // Requirement 3.6: fallback
}

function bearerToken(headers) {
  const h = headers || {};
  const auth = String(h.authorization || h.Authorization || '').trim();
  return /^bearer\s+/i.test(auth) ? auth.replace(/^bearer\s+/i, '').trim() : '';
}

function historyMessages(history) {
  let h = history;
  if (typeof h === 'string') {
    try { h = JSON.parse(h); } catch (e) { h = []; }
  }
  if (!Array.isArray(h)) return [];
  return h
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .slice(-20) // Property 16: máximo 10 intercambios
    .map((m) => ({ role: m.role, content: m.content }));
}

function buildMessages(systemExtra, history, message) {
  return [
    { role: 'system', content: SYSTEM_BASE + '\n\n' + systemExtra },
    ...historyMessages(history),
    { role: 'user', content: String(message || '') },
  ];
}

function todayBogota(now) {
  return (now || new Date()).toLocaleDateString('es-CO', {
    timeZone: 'America/Bogota', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
}

function ragContext(chunks) {
  if (!Array.isArray(chunks) || chunks.length === 0) {
    return 'CONTEXTO: (no se encontraron fragmentos relevantes en los documentos institucionales)';
  }
  return 'CONTEXTO (fragmentos de documentos oficiales CCD de la UNAB):\n' +
    chunks.map((c, i) => `[${i + 1}] (${c.document_name}) ${c.text}`).join('\n\n');
}

// Acepta encabezados en inglés o español en la hoja de Google Sheets.
function normalizeEvent(row) {
  const r = {};
  for (const [k, v] of Object.entries(row || {})) r[stripAccents(k).toLowerCase().trim()] = v;
  const name = r.event_name ?? r.evento ?? r.nombre ?? r.actividad ?? '';
  const date = r.event_date ?? r.fecha ?? r.date ?? '';
  const desc = r.description ?? r.descripcion ?? r.detalle ?? '';
  return { event_name: String(name).trim(), event_date: String(date).trim(), description: String(desc).trim() };
}

function calendarEvents(rows) {
  return (rows || [])
    .filter((r) => r && typeof r === 'object' && !r.error)
    .map(normalizeEvent)
    .filter((e) => e.event_name && e.event_date)
    .sort((a, b) => a.event_date.localeCompare(b.event_date));
}

function calendarContext(events, now) {
  const list = events.length
    ? events.map((e) => `- ${e.event_name}: ${e.event_date}${e.description ? ' — ' + e.description : ''}`).join('\n')
    : '(el calendario no tiene eventos registrados)';
  return `Hoy es ${todayBogota(now)}.\nCALENDARIO ACADÉMICO UNAB:\n${list}`;
}

function coursesContext(record) {
  const r = record || {};
  const courses = Array.isArray(r.courses) ? r.courses : [];
  const label = { completed: 'aprobado', in_progress: 'en curso', pending: 'pendiente' };
  const lines = courses.map((c) =>
    `- Semestre ${c.semester}: ${c.course_code} ${c.course_name} — ${label[c.status] || c.status}` +
    (c.grade != null ? ` (nota ${c.grade})` : ''));
  return 'HISTORIAL ACADÉMICO DEL ESTUDIANTE (solo de este estudiante):\n' +
    `Total cursos: ${r.total || 0}; aprobados: ${r.completed || 0}; en curso: ${r.in_progress || 0}; ` +
    `pendientes: ${r.pending || 0}; avance: ${r.progress_percentage || 0}%.\n` + (lines.join('\n') || '(sin cursos registrados)') +
    '\nIncluye en tu respuesta el porcentaje de avance cuando sea pertinente.';
}

function newsContext(news) {
  const items = Array.isArray(news) ? news : [];
  return 'NOTICIAS RECIENTES DE LA UNAB (más recientes primero):\n' +
    items.map((n) => `- [${String(n.published_at).slice(0, 10)}] ${n.title}: ${n.summary} (${n.source_url})`).join('\n') +
    '\nResume solo las noticias relacionadas con la pregunta; si ninguna aplica, menciona las más recientes.';
}

function parseEventDate(value) {
  const s = String(value || '').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(s + 'T00:00:00-05:00'); // medianoche Colombia
  const iso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(s) ? s : (s.includes('T') ? s + '-05:00' : s);
  const d = new Date(iso);
  return isNaN(d.getTime()) || !/^\d{4}-\d{2}-\d{2}/.test(s) ? null : d;
}

// Property 24: eventos con fecha en (now, now + 48h].
function eventsInWindow(events, now, hours) {
  const t0 = (now || new Date()).getTime();
  const t1 = t0 + (hours || 48) * 3600 * 1000;
  return (events || [])
    .map((e) => ({ e, d: parseEventDate(e.event_date) }))
    .filter(({ d }) => d && d.getTime() > t0 && d.getTime() <= t1)
    .map(({ e }) => ({ ...e, event_key: `${e.event_name}|${e.event_date}` }));
}

function llmText(resp) {
  try {
    const t = resp.choices[0].message.content;
    return typeof t === 'string' ? t.trim() : '';
  } catch (e) {
    return '';
  }
}

// @export
if (typeof module !== 'undefined') {
  module.exports = {
    INTENT_LABELS, FALLBACK_RESPONSE, CLASSIFIER_PROMPT, normalizeIntent, bearerToken, historyMessages,
    buildMessages, ragContext, calendarEvents, calendarContext, coursesContext, newsContext,
    eventsInWindow, parseEventDate, llmText, normalizeEvent,
  };
}
