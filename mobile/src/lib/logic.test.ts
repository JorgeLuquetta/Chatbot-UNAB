// Pruebas de la lógica pura de la app (equivalentes a las propiedades Kotest de la app Android).
// Ejecutar: npm test   (Node 22.6+ con --experimental-strip-types)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  MESSAGE_MAX, groupBySemester, isValidMessage, parseEventDate, progressPercentage, reminderTimes,
  upcomingEvents, type Course,
} from './academic.ts';
import {
  ApiError, AuthErrors, ChatErrors, authErrorMessage, chatErrorMessage, isRetryable, isSessionExpired,
} from './errors.ts';

const rand = (n: number) => Math.floor(Math.random() * n);

test('Property 2: mensaje válido sii longitud en [1, 2000] y no vacío', () => {
  assert.equal(isValidMessage(''), false);
  assert.equal(isValidMessage('   '), false);
  assert.equal(isValidMessage(null), false);
  assert.equal(isValidMessage('a'), true);
  assert.equal(isValidMessage('x'.repeat(MESSAGE_MAX)), true);
  assert.equal(isValidMessage('x'.repeat(MESSAGE_MAX + 1)), false);
  for (let i = 0; i < 200; i++) {
    const len = rand(2600);
    assert.equal(isValidMessage('a'.repeat(len)), len >= 1 && len <= MESSAGE_MAX);
  }
});

test('Property 4: los errores de chat siempre son uno de los mensajes fijos, sin detalles técnicos', () => {
  const allowed = new Set(Object.values(ChatErrors));
  for (let s = -1; s < 700; s++) {
    const msg = chatErrorMessage(new ApiError(s));
    assert.ok(allowed.has(msg as never), `status ${s} → ${msg}`);
    assert.ok(!/\d{3}/.test(msg), 'no debe incluir códigos HTTP');
  }
  assert.equal(chatErrorMessage(new Error('SELECT * FROM students')), ChatErrors.GENERIC);
  assert.equal(chatErrorMessage(new ApiError(401)), ChatErrors.SESSION);
  assert.equal(chatErrorMessage(new ApiError(400)), ChatErrors.REJECTED);
  assert.equal(chatErrorMessage(new ApiError(0)), ChatErrors.CONNECTIVITY);
  assert.equal(chatErrorMessage(new ApiError(-1)), ChatErrors.TIMEOUT);
});

test('Property 1: errores de login no filtran credenciales', () => {
  const allowed = new Set(Object.values(AuthErrors));
  for (const s of [0, -1, 400, 401, 403, 404, 500, 503]) {
    const msg = authErrorMessage(new ApiError(s));
    assert.ok(allowed.has(msg as never));
    assert.ok(!msg.includes('U00000001') && !msg.includes('Unab2026*'));
  }
  assert.equal(authErrorMessage(new ApiError(401)), AuthErrors.INVALID_CREDENTIALS);
  assert.equal(authErrorMessage(new ApiError(0)), AuthErrors.UNREACHABLE);
  assert.equal(isRetryable(new ApiError(0)), true);
  assert.equal(isRetryable(new ApiError(503)), true);
  assert.equal(isRetryable(new ApiError(401)), false);
  assert.equal(isSessionExpired(new ApiError(401)), true);
});

function randomCourses(n: number): Course[] {
  const st = ['completed', 'in_progress', 'pending'];
  return Array.from({ length: n }, (_, i) => ({
    course_code: `ISC${rand(9) + 1}0${i}`, course_name: `Curso ${i}`, semester: rand(10) + 1,
    status: st[rand(3)], grade: null,
  }));
}

test('Property 22: agrupación por semestre conserva todos los cursos y ordena ascendente', () => {
  for (let k = 0; k < 100; k++) {
    const courses = randomCourses(rand(40));
    const groups = groupBySemester(courses);
    assert.equal(groups.reduce((a, g) => a + g.courses.length, 0), courses.length);
    for (let i = 1; i < groups.length; i++) assert.ok(groups[i - 1].semester < groups[i].semester);
    for (const g of groups) assert.ok(g.courses.every((c) => c.semester === g.semester));
  }
});

test('Property 23: porcentaje de avance en [0, 100] y exacto', () => {
  assert.equal(progressPercentage([]), 0);
  for (let k = 0; k < 100; k++) {
    const courses = randomCourses(rand(40) + 1);
    const p = progressPercentage(courses);
    const done = courses.filter((c) => c.status === 'completed').length;
    assert.ok(p >= 0 && p <= 100);
    assert.ok(Math.abs(p - (100 * done) / courses.length) <= 0.05 + 1e-9); // redondeo a 1 decimal
  }
});

test('calendario: fechas inválidas se descartan y los eventos futuros se ordenan', () => {
  assert.equal(parseEventDate('17/11/2026'), null);
  const now = new Date('2026-11-17T12:00:00-05:00');
  const ev = upcomingEvents([
    { event_name: 'B', event_date: '2026-12-01' }, { event_name: 'Pasado', event_date: '2026-10-02' },
    { event_name: 'A', event_date: '2026-11-27' }, { event_name: 'Malo', event_date: 'mañana' },
  ], now);
  assert.deepEqual(ev.map((e) => e.event_name), ['A', 'B']);
});

test('recordatorios: 48 h antes, nunca en el pasado ni después del evento', () => {
  const now = new Date('2026-11-17T12:00:00-05:00');
  const r = reminderTimes([
    { event_name: 'Lejano', event_date: '2026-12-01' },
    { event_name: 'Mañana', event_date: '2026-11-18' },
    { event_name: 'Pasado', event_date: '2026-11-01' },
  ], now);
  assert.deepEqual(r.map((x) => x.event.event_name), ['Lejano', 'Mañana']);
  assert.equal(r[0].at.toISOString(), new Date('2026-11-29T00:00:00-05:00').toISOString());
  assert.ok(r[1].at.getTime() > now.getTime());
});
