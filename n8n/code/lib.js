// Funciones puras usadas dentro de los nodos Code de n8n.
// build_workflows.py inserta este archivo (hasta la marca de export) en cada nodo Code,
// y tests/test_n8n_code.py las prueba con Node.js.

const INTENT_LABELS = ['consulta-general', 'calendario', 'cursos-realizados', 'noticias', 'plan-academico', 'correo'];

const FALLBACK_RESPONSE = 'Solo puedo ayudarte con temas académicos de la UNAB.';

const SYSTEM_BASE =
  'Eres el asistente académico de la Universidad Autónoma de Bucaramanga (UNAB). ' +
  'Responde SIEMPRE en español, de forma clara, breve y amable. ' +
  'Solo atiendes temas académicos e institucionales de la UNAB. ' +
  'Usa únicamente la información del contexto proporcionado; si no está, dilo con honestidad ' +
  'y sugiere la dependencia de la UNAB a la que el estudiante puede acudir. No inventes datos. ' +
  'Responde en máximo 5 frases, usando las mismas palabras del contexto (porcentajes, notas, artículos); ' +
  'no agregues pasos, fórmulas ni ejemplos que no aparezcan en el contexto.';

const CLASSIFIER_PROMPT =
  'Clasifica el mensaje del estudiante en exactamente una de estas etiquetas:\n' +
  '- consulta-general: preguntas sobre normas, programas, plan de estudios, competencias, trámites o documentos institucionales.\n' +
  '- calendario: fechas académicas (matrículas, parciales, inicio/fin de clases, festivos, plazos).\n' +
  '- cursos-realizados: el progreso personal del estudiante (cursos aprobados, pendientes, en curso, notas, avance).\n' +
  '- noticias: noticias, eventos o novedades recientes de la universidad.\n' +
  '- plan-academico: matrícula (qué materias inscribir), estado académico (promedio, situación), proyección de grado ' +
  'y recomendaciones personalizadas para tener éxito.\n' +
  '- correo: pide que le ENVÍEN por correo noticias, su informe de avance o su informe de materias.\n' +
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

// Ruteo por reglas ANTES del LLM: frases inequívocas se enrutan sin gastar una llamada al clasificador
// (más rápido y determinista con un LLM pequeño en CPU). Devuelve null si hay duda → decide el LLM.
const RULES = [
  ['cursos-realizados', [
    /\b(mi|mis)\s+(avance|progreso|cursos?|materias?|asignaturas?|notas?|calificaciones|historial|creditos)\b/,
    /\bhe\s+(aprobado|cursado|visto|reprobado|perdido|ganado)\b/,
    /\b(que|cuales|cuantas?|cuantos)\s+(cursos|materias|asignaturas|creditos)\s+(he|me\s+faltan?|tengo|llevo|debo)\b/,
    /\bme\s+faltan?\s+(cursos|materias|asignaturas|creditos|semestres)\b/,
  ]],
  ['noticias', [/\b(noticias?|novedades|convocatorias?)\b/]],
  ['correo', [
    /\b(envia\w*|manda\w*|reenvia\w*|remite\w*)\b.*\b(correo|e-?mail|mail|gmail|yopmail|bandeja)\b/,
    /\b(al|a mi|por|por el)\s+(correo|e-?mail|mail)\b/,
  ]],
  ['plan-academico', [
    /\b(matricul\w*|inscribir|inscribo|inscripcion de materias)\b.*\b(materias?|asignaturas?|cursos?|creditos|semestre|periodo)\b/,
    /\b(que|cuales)\s+(materias|asignaturas|cursos)\s+(puedo|debo|deberia|me\s+recomiendas?)\b/,
    /\b(proyeccion|proyectar|cuando\s+me\s+(graduo|voy\s+a\s+graduar)|en\s+cuant[oa]s?\s+(semestres|periodos))\b/,
    /\b(estado|situacion|rendimiento)\s+academic[oa]\b/,
    /\b(mi\s+promedio|prueba\s+academica|carga\s+maxima)\b/,
    /\b(recomendaciones?|recomiendas?|recomiendame|consejos?|como\s+(mejorar|tener\s+exito|me\s+va))\b/,
  ]],
  ['consulta-general', [
    /\b(reglamento|requisitos?|grado|graduarme|titulo|supletorios?|habilitaci\w*|reprob\w*|repruebo|sancion\w*|homologa\w*|transferencia|reintegro|insignia|competencias?)\b/,
  ]],
  ['calendario', [
    /\b(fecha|fechas|calendario|cronograma)\b/,
    /\bcuando\b.*\b(parcial(es)?|examen(es)?|finales|matriculas?|inscripcion(es)?|clases|semestre|vacaciones|festivos?|cancelar|entrega)\b/,
  ]],
];

function ruleIntent(message) {
  const text = stripAccents(String(message || '')).toLowerCase();
  const hits = RULES.filter(([, patterns]) => patterns.some((p) => p.test(text))).map(([label]) => label);
  // "Envíame las noticias al correo" también toca noticias: si pide un envío por correo, gana el correo
  if (hits.includes('correo')) return 'correo';
  // "¿qué materias debo matricular?" o "¿cuándo me gradúo?" también tocan cursos/reglamento: gana el plan
  if (hits.includes('plan-academico') && hits.every((h) => ['plan-academico', 'cursos-realizados', 'consulta-general'].includes(h))) {
    return 'plan-academico';
  }
  return hits.length === 1 ? hits[0] : null; // ambiguo (0 o 2+ coincidencias) → LLM
}

function bearerToken(headers) {
  const h = headers || {};
  const auth = String(h.authorization || h.Authorization || '').trim();
  return /^bearer\s+/i.test(auth) ? auth.replace(/^bearer\s+/i, '').trim() : '';
}

// Recorta textos largos para que el prompt quepa y sea rápido en un LLM local (Ollama en CPU).
function clip(text, max) {
  const s = String(text == null ? '' : text);
  return s.length > max ? s.slice(0, max).trimEnd() + '…' : s;
}

const HISTORY_CHARS = 300;
// Largo de cada fragmento del reglamento en el prompt (menos texto = respuesta más rápida en CPU)
const RAG_CHUNK_CHARS = 600;

// maxMessages: 20 = 10 intercambios (Property 16). Con un LLM local se puede bajar con LLM_HISTORY_MESSAGES.
function historyMessages(history, maxMessages) {
  const max = Number.isInteger(maxMessages) && maxMessages >= 0 ? Math.min(maxMessages, 20) : 20;
  let h = history;
  if (typeof h === 'string') {
    try { h = JSON.parse(h); } catch (e) { h = []; }
  }
  if (!Array.isArray(h) || max === 0) return [];
  return h
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .slice(-max) // Property 16: máximo 10 intercambios
    .map((m) => ({ role: m.role, content: clip(m.content, HISTORY_CHARS) }));
}

function buildMessages(systemExtra, history, message, maxMessages) {
  return [
    { role: 'system', content: SYSTEM_BASE + '\n\n' + systemExtra },
    ...historyMessages(history, maxMessages),
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
    chunks.map((c, i) => `[${i + 1}] (${c.document_name}) ${clip(c.text, RAG_CHUNK_CHARS)}`).join('\n\n');
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
  const items = (Array.isArray(news) ? news : []).slice(0, 8);
  return 'NOTICIAS RECIENTES (educación, tecnología e ingeniería de sistemas; más recientes primero):\n' +
    items.map((n) => `- [${String(n.published_at).slice(0, 10)}] (${n.category || 'general'}, ${n.source_name || 'UNAB'}) ` +
      `${n.title}: ${clip(n.summary, 160)}`).join('\n') +
    '\nResponde con las noticias de esta lista (título y fecha). Si la pregunta es general, presenta las 3 más ' +
    'recientes; si pregunta por un tema, las relacionadas con ese tema. No digas que no hay noticias.';
}

// Guía pedagógica: educación de precisión (decisiones con los datos del propio estudiante),
// autoaprendizaje e investigación. Se usa en el prompt del plan académico.
const PEDAGOGY =
  'Eres un consejero académico. Aplica educación de precisión: basa cada consejo en los datos de ESTE estudiante ' +
  '(promedio, materias reprobadas, nota más baja, créditos, prerrequisitos). Promueve el autoaprendizaje y la ' +
  'investigación (semilleros, monitorías). Da pasos concretos y accionables, en viñetas cortas.';

const STANDING_LABEL = {
  'excelencia': 'excelencia académica', 'normal': 'normal', 'en observación': 'en observación',
  'prueba académica': 'prueba académica', 'sin notas': 'sin notas todavía (primer semestre)',
};

// Resume el JSON de academic_plan() para el LLM (texto corto = respuesta más rápida en CPU).
function planContext(plan) {
  const p = plan || {};
  const s = p.student || {}, st = p.status || {}, en = p.enrollment || {}, pr = p.projection || {};
  const courses = (en.courses || []).map((c) =>
    `- ${c.course_code} ${c.course_name} (${c.credits} cr${c.repeat ? ', repetir: reprobada' : ''}` +
    `${c.conditional ? ', condicionada a aprobar ' + (c.conditional_on || []).map((x) => x.course_name).join(' y ') : ''})`);
  const blocked = (en.blocked || []).slice(0, 3).map((b) =>
    `- ${b.course_name}: falta ${(b.missing_prerequisites || []).map((m) => m.course_name).join(', ')}`);
  const recs = (p.recommendations || []).map((r) => `- ${r.text}`);
  return PEDAGOGY + '\n\n' +
    `PLAN ACADÉMICO DE ${s.full_name || 'el estudiante'} (${s.program || ''}, semestre ${s.current_semester || '?'}):\n` +
    `ESTADO ACADÉMICO: promedio ponderado ${st.gpa ?? 'sin notas'}; situación ${STANDING_LABEL[st.standing] || st.standing}; ` +
    `${st.approved_credits || 0} de ${st.total_credits || 0} créditos aprobados (${st.progress_percentage || 0}%); ` +
    `materias reprobadas: ${st.failed_courses || 0}.\n` +
    `MATRÍCULA SUGERIDA ${en.term || ''} (${en.credits || 0} de máximo ${en.max_credits || 18} créditos):\n` +
    (courses.join('\n') || '- (no hay materias disponibles para matricular)') + '\n' +
    (blocked.length ? 'BLOQUEADAS POR PRERREQUISITOS:\n' + blocked.join('\n') + '\n' : '') +
    `PROYECCIÓN: faltan ${pr.remaining_credits ?? '?'} créditos; ${pr.terms_remaining ?? '?'} periodos más; ` +
    `grado estimado en ${pr.estimated_graduation_term || '?'}; ${pr.on_track ? 'va al día' : 'tiene atrasos'}.\n` +
    'RECOMENDACIONES:\n' + (recs.join('\n') || '-') + '\n' +
    'Responde SOLO lo que pregunta (matrícula, estado, proyección o recomendaciones) con estas cifras exactas.\n' +
    'Si pregunta qué matricular, enumera TODAS las materias de la MATRÍCULA SUGERIDA (primero las que debe repetir).';
}

// Categoría de noticias pedida en el mensaje ('' = todas).
function newsCategory(message) {
  const t = stripAccents(String(message || '')).toLowerCase();
  if (/\b(ingenieria de sistemas|software|programacion|sistemas)\b/.test(t)) return 'ingenieria-sistemas';
  if (/\b(tecnolog\w*|inteligencia artificial|ia|digital|innovacion|ingenieria\w*)\b/.test(t)) return 'tecnologia';
  if (/\b(educacion|educativ\w*|becas?|cursos?|diplomados?|posgrados?)\b/.test(t)) return 'educacion';
  return '';
}

// Garantiza que una respuesta sobre matrícula liste TODAS las materias sugeridas: un LLM pequeño a veces
// omite alguna. Si falta un código, agrega la lista exacta calculada en SQL (educación de precisión).
function ensureEnrollment(response, plan, message) {
  const text = stripAccents(String(message || '')).toLowerCase();
  const courses = ((plan || {}).enrollment || {}).courses || [];
  if (!/\b(matricul\w*|inscrib\w*)\b/.test(text) || courses.length === 0) return response;
  const out = String(response || '');
  if (courses.every((c) => out.includes(c.course_code) || out.includes(c.course_name))) return out;
  const en = plan.enrollment;
  const list = courses.map((c) => `- ${c.course_code} ${c.course_name} (${c.credits} créditos` +
    (c.repeat ? ', repetir' : '') +
    (c.conditional ? ', si apruebas ' + (c.conditional_on || []).map((x) => x.course_name).join(' y ') : '') + ')');
  return `${out}\n\nMatrícula sugerida ${en.term} (${en.credits} de ${en.max_credits} créditos):\n${list.join('\n')}`;
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
    INTENT_LABELS, FALLBACK_RESPONSE, CLASSIFIER_PROMPT, normalizeIntent, ruleIntent, bearerToken, historyMessages, clip,
    buildMessages, ragContext, calendarEvents, calendarContext, coursesContext, newsContext, planContext, PEDAGOGY, newsCategory, ensureEnrollment,
    eventsInWindow, parseEventDate, llmText, normalizeEvent,
  };
}
