// Carga un recurso del backend con respaldo offline: si la red falla, muestra la última copia guardada.
import { useCallback, useEffect, useState } from 'react';
import { useAuth, useSession } from './auth';
import { chatErrorMessage, isSessionExpired } from './lib/errors';
import { loadCache, saveCache } from './lib/storage';

export interface ResourceState<T> {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null; // mensaje amigable
  offlineSince: string | null; // ISO de la copia guardada que se está mostrando
  reload: () => Promise<void>;
}

export function useCachedResource<T>(key: string, fetcher: (studentId: string) => Promise<T>): ResourceState<T> {
  const session = useSession();
  const { signOut } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offlineSince, setOfflineSince] = useState<string | null>(null);

  const load = useCallback(async (isRefresh: boolean) => {
    isRefresh ? setRefreshing(true) : setLoading(true);
    try {
      const fresh = await fetcher(session.student_id);
      setData(fresh);
      setError(null);
      setOfflineSince(null);
      await saveCache(session.student_id, key, fresh);
    } catch (e) {
      if (isSessionExpired(e)) {
        await signOut();
        return;
      }
      const cached = await loadCache<T>(session.student_id, key);
      if (cached) {
        setData(cached.data);
        setOfflineSince(cached.savedAt);
        setError(null);
      } else {
        setError(chatErrorMessage(e));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [fetcher, key, session.student_id, signOut]);

  useEffect(() => {
    load(false);
  }, [load]);

  return { data, loading, refreshing, error, offlineSince, reload: () => load(true) };
}
