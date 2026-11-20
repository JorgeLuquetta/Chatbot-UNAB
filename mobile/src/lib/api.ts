// Cliente HTTP de los webhooks de n8n.
import Constants from 'expo-constants';
import type { CalendarEvent, Course } from './academic';
import { ApiError } from './errors';

// Orden de prioridad: EXPO_PUBLIC_API_URL (archivo .env de la app) → app.json extra.apiUrl
const fromEnv = process.env.EXPO_PUBLIC_API_URL;
const fromConfig = (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;
export const API_URL = (fromEnv || fromConfig || 'https://n8n.traumado.top/webhook').replace(/\/+$/, '');

// El LLM corre en CPU (Ollama): una respuesta puede tardar más de un minuto.
const CHAT_TIMEOUT_MS = 300_000;
const DEFAULT_TIMEOUT_MS = 20_000;

async function request<T>(path: string, init: RequestInit & { token?: string; timeoutMs?: number } = {}): Promise<T> {
  const { token, timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        'content-type': 'application/json',
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(headers as Record<string, string> | undefined),
      },
    });
  } catch (e) {
    throw new ApiError(controller.signal.aborted ? -1 : 0);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) throw new ApiError(res.status);
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(502);
  }
}

export interface StudentResponse {
  student_id: string;
  full_name: string;
  program: string;
  current_semester: number | null;
  progress_percentage: number;
}

export interface PlanCourse {
  course_code: string; course_name: string; semester: number; credits: number;
  repeat: boolean; conditional: boolean; conditional_on: { course_code: string; course_name: string }[];
}
export interface AcademicPlan {
  student: { student_id: string; full_name: string; program: string; current_semester: number };
  status: {
    gpa: number | null; standing: string; approved_credits: number; total_credits: number;
    progress_percentage: number; failed_courses: number; in_progress: { course_code: string; course_name: string }[];
  };
  enrollment: {
    term: string; max_credits: number; credits: number; courses: PlanCourse[];
    blocked: { course_code: string; course_name: string; semester: number;
               missing_prerequisites: { course_code: string; course_name: string }[] }[];
  };
  projection: {
    remaining_credits: number; credits_per_term: number; terms_remaining: number;
    prerequisite_chain: number; estimated_graduation_term: string; on_track: boolean;
  };
  recommendations: { type: string; text: string }[];
}
export interface NewsItem {
  title: string; summary: string; source_url: string; source_name: string; category: string; published_at: string;
}

const qs = (student_id: string) => `?student_id=${encodeURIComponent(student_id)}`;

export const api = {
  // Busca al estudiante por su ID en la BD (chat sin login). 404 = no existe.
  lookup: (student_id: string) =>
    request<StudentResponse>('student-lookup', { method: 'POST', body: JSON.stringify({ student_id }) }),

  chat: (student_id: string, message: string) =>
    request<{ response: string; intent: string }>('chat', {
      method: 'POST', timeoutMs: CHAT_TIMEOUT_MS, body: JSON.stringify({ student_id, message }),
    }),

  academicRoute: (student_id: string) =>
    request<{ courses: Course[]; progress_percentage: number }>(`academic-route${qs(student_id)}`),

  // Matrícula sugerida, estado académico, proyección de grado y recomendaciones
  academicPlan: (student_id: string) => request<AcademicPlan>(`academic-plan${qs(student_id)}`),

  news: (category = '') =>
    request<{ news: NewsItem[] }>(`news?limit=30${category ? `&category=${encodeURIComponent(category)}` : ''}`),

  calendar: (student_id: string) => request<{ events: CalendarEvent[] }>(`calendar${qs(student_id)}`),

  registerDevice: (token: string, fcm_token: string) =>
    request<{ ok: boolean }>('register-device', { method: 'POST', token, body: JSON.stringify({ fcm_token }) }),
};
