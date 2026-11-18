// Mensajes de error amigables de un conjunto FIJO: nunca incluyen códigos HTTP, trazas,
// tokens ni datos internos (Requirement 2.5 / Property 4 y Requirement 1.2 / Property 1).

export const ChatErrors = {
  CONNECTIVITY: 'No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.',
  TIMEOUT: 'El asistente está tardando más de lo normal. Inténtalo de nuevo en un momento.',
  SESSION: 'No encontramos tu ID de estudiante. Escríbelo de nuevo.',
  REJECTED: 'No pude procesar tu mensaje. Reformula tu pregunta sobre temas académicos de la UNAB.',
  UNAVAILABLE: 'El servicio no está disponible en este momento. Inténtalo más tarde.',
  GENERIC: 'Ocurrió un problema inesperado. Inténtalo de nuevo.',
} as const;

export const AuthErrors = {
  INVALID_CREDENTIALS: 'No encontré ese ID en la base de datos. Revísalo e inténtalo de nuevo.',
  MISSING_FIELDS: 'Escribe tu ID de estudiante: una U seguida de 8 dígitos, por ejemplo U00000001.',
  UNREACHABLE: 'No pude conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
  GENERIC: 'No pude buscar tu ID. Inténtalo de nuevo.',
} as const;

/** Error de red/HTTP normalizado. status = 0 → sin conexión; status = -1 → timeout. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number) {
    super(`api-error-${status}`);
    this.status = status;
    this.name = 'ApiError';
  }
}

export function chatErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return ChatErrors.GENERIC;
  const s = error.status;
  if (s === 0) return ChatErrors.CONNECTIVITY;
  if (s === -1 || s === 408 || s === 504) return ChatErrors.TIMEOUT;
  if (s === 401 || s === 403) return ChatErrors.SESSION;
  if (s === 400 || s === 413 || s === 422) return ChatErrors.REJECTED;
  if (s >= 500 && s <= 599) return ChatErrors.UNAVAILABLE;
  return ChatErrors.GENERIC;
}

export function authErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return AuthErrors.GENERIC;
  if (error.status >= 400 && error.status <= 499) return AuthErrors.INVALID_CREDENTIALS;
  return AuthErrors.UNREACHABLE; // sin conexión, timeout o 5xx
}

/** true si conviene ofrecer "Reintentar" (Requirement 1.5). */
export function isRetryable(error: unknown): boolean {
  return error instanceof ApiError && (error.status <= 0 || error.status >= 500);
}

export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}
