// Sesión en almacenamiento cifrado (SecureStore) y caché offline en AsyncStorage.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

// Sesión sin login: el estudiante se identifica solo con su ID (búsqueda en la BD).
export interface Session {
  student_id: string;
  full_name: string;
  program?: string;
  current_semester?: number | null;
  progress_percentage?: number;
  expires_at?: string;
}

const SESSION_KEY = 'unab_session';

export async function loadSession(): Promise<Session | null> {
  try {
    const raw = await SecureStore.getItemAsync(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    // Sesión vencida → se descarta (el backend también la rechazaría con 401)
    if (s.expires_at && new Date(s.expires_at).getTime() <= Date.now()) {
      await clearSession();
      return null;
    }
    return s;
  } catch {
    return null;
  }
}

export async function saveSession(s: Session): Promise<void> {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(s));
}

export async function clearSession(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(SESSION_KEY);
  } catch {
    // nada que borrar
  }
}

export interface Cached<T> {
  data: T;
  savedAt: string; // ISO
}

/** Caché por estudiante: así un estudiante nunca ve los datos guardados de otro en el mismo teléfono. */
export async function saveCache<T>(studentId: string, key: string, data: T): Promise<void> {
  try {
    await AsyncStorage.setItem(`cache:${studentId}:${key}`, JSON.stringify({ data, savedAt: new Date().toISOString() }));
  } catch {
    // sin espacio o almacenamiento no disponible: la app sigue funcionando en línea
  }
}

export async function loadCache<T>(studentId: string, key: string): Promise<Cached<T> | null> {
  try {
    const raw = await AsyncStorage.getItem(`cache:${studentId}:${key}`);
    return raw ? (JSON.parse(raw) as Cached<T>) : null;
  } catch {
    return null;
  }
}
