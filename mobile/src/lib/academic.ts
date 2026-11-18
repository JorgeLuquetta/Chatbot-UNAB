// Lógica pura de mensajes, ruta académica y calendario (sin React, se prueba con node --test).

export const MESSAGE_MIN = 1;
export const MESSAGE_MAX = 2000;

/** Requirement 2.6 / Property 2: un mensaje se puede enviar si su longitud está en [1, 2000]. */
export function isValidMessage(text: string | null | undefined): boolean {
  return typeof text === 'string' && text.trim().length >= MESSAGE_MIN && text.length <= MESSAGE_MAX;
}

export type CourseStatus = 'completed' | 'in_progress' | 'pending';

export interface Course {
  course_code: string;
  course_name: string;
  semester: number;
  status: CourseStatus | string;
  grade: number | null;
}

export interface SemesterGroup {
  semester: number;
  courses: Course[];
}

/** Agrupa por semestre en orden ascendente, y dentro de cada semestre por código. */
export function groupBySemester(courses: Course[]): SemesterGroup[] {
  const map = new Map<number, Course[]>();
  for (const c of courses ?? []) {
    const list = map.get(c.semester) ?? [];
    list.push(c);
    map.set(c.semester, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a - b)
    .map(([semester, list]) => ({
      semester,
      courses: [...list].sort((x, y) => x.course_code.localeCompare(y.course_code)),
    }));
}

/** % de cursos aprobados con un decimal; 0 si no hay cursos. Siempre en [0, 100]. */
export function progressPercentage(courses: Course[]): number {
  const total = courses?.length ?? 0;
  if (total === 0) return 0;
  const done = courses.filter((c) => c.status === 'completed').length;
  return Math.round((done / total) * 1000) / 10;
}

export function statusLabel(status: string): string {
  return { completed: 'Aprobado', in_progress: 'En curso', pending: 'Pendiente' }[status] ?? status;
}

export interface CalendarEvent {
  event_name: string;
  event_date: string; // AAAA-MM-DD
  description?: string | null;
}

/** Fecha AAAA-MM-DD a medianoche de Colombia (UTC-5). null si no es válida. */
export function parseEventDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value ?? '').trim())) return null;
  const d = new Date(`${value.trim()}T00:00:00-05:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Eventos de hoy en adelante, ordenados por fecha. */
export function upcomingEvents(events: CalendarEvent[], now: Date = new Date()): CalendarEvent[] {
  const startOfToday = new Date(now.getTime() - 24 * 3600 * 1000);
  return (events ?? [])
    .map((e) => ({ e, d: parseEventDate(e.event_date) }))
    .filter(({ d }) => d !== null && d.getTime() >= startOfToday.getTime())
    .sort((a, b) => a.d!.getTime() - b.d!.getTime())
    .map(({ e }) => e);
}

/**
 * Recordatorios locales: para cada evento futuro, aviso 48 h antes (o lo antes posible si ya falta menos).
 * Reemplaza en Expo Go a las notificaciones push FCM (Requirement 13), que Expo Go no soporta en Android.
 */
export function reminderTimes(events: CalendarEvent[], now: Date = new Date(), hoursBefore = 48) {
  const out: { event: CalendarEvent; at: Date }[] = [];
  for (const event of events ?? []) {
    const d = parseEventDate(event.event_date);
    if (!d || d.getTime() <= now.getTime()) continue;
    const at = new Date(Math.max(d.getTime() - hoursBefore * 3600 * 1000, now.getTime() + 60 * 1000));
    if (at.getTime() < d.getTime()) out.push({ event, at });
  }
  return out;
}

export function formatDateEs(value: string): string {
  const d = parseEventDate(value);
  if (!d) return value;
  return d.toLocaleDateString('es-CO', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Bogota',
  });
}
