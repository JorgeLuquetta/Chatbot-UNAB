import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from './lib/api';
import { cancelReminders } from './lib/reminders';
import { clearSession, loadSession, saveSession, type Session } from './lib/storage';

interface AuthState {
  session: Session | null;
  loading: boolean;
  signIn: (studentId: string) => Promise<Session>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSession().then((s) => {
      setSession(s);
      setLoading(false);
    });
  }, []);

  const signIn = useCallback(async (studentId: string) => {
    const r = await api.lookup(studentId.trim().toUpperCase());
    const s: Session = { ...r };
    await saveSession(s);
    setSession(s);
    return s;
  }, []);

  const signOut = useCallback(async () => {
    await clearSession();
    await cancelReminders();
    setSession(null);
  }, []);

  const value = useMemo(() => ({ session, loading, signIn, signOut }), [session, loading, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return ctx;
}

/** Sesión garantizada (las pantallas con pestañas solo se muestran con sesión). */
export function useSession(): Session {
  const { session } = useAuth();
  if (!session) throw new Error('Sin sesión');
  return session;
}
