import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { ErrorState, Loading, OfflineBanner } from '../../src/components';
import { formatDateEs, parseEventDate, upcomingEvents } from '../../src/lib/academic';
import { api } from '../../src/lib/api';
import { scheduleCalendarReminders } from '../../src/lib/reminders';
import { useTheme } from '../../src/theme';
import { useCachedResource } from '../../src/useCachedResource';

function daysUntil(date: string): number | null {
  const d = parseEventDate(date);
  return d ? Math.ceil((d.getTime() - Date.now()) / 86_400_000) : null;
}

export default function CalendarioScreen() {
  const t = useTheme();
  const { data, loading, refreshing, error, offlineSince, reload } = useCachedResource('calendar', api.calendar);
  const [reminders, setReminders] = useState<number | null>(null);
  const events = upcomingEvents(data?.events ?? []);

  // Programa recordatorios locales 48 h antes de cada evento (sustituye al push FCM en Expo Go)
  useEffect(() => {
    if (data?.events) scheduleCalendarReminders(data.events).then(setReminders);
  }, [data]);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;

  return (
    <FlatList
      data={events}
      keyExtractor={(e) => `${e.event_name}|${e.event_date}`}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.purple} />}
      ListHeaderComponent={
        <View>
          {offlineSince && <OfflineBanner since={offlineSince} />}
          {reminders != null && reminders > 0 && (
            <View style={[styles.info, { backgroundColor: t.card, borderColor: t.border }]}>
              <Ionicons name="notifications-outline" size={18} color={t.purple} />
              <Text style={{ color: t.muted, flex: 1, fontSize: 13 }}>
                Te avisaré 48 horas antes de {reminders === 1 ? 'este evento' : `estos ${reminders} eventos`}.
              </Text>
            </View>
          )}
        </View>
      }
      renderItem={({ item }) => {
        const days = daysUntil(item.event_date);
        const soon = days != null && days <= 2;
        return (
          <View style={[styles.card, { backgroundColor: t.card, borderColor: soon ? t.orange : t.border }]}>
            <View style={[styles.badge, { backgroundColor: soon ? t.orange : t.purple }]}>
              <Text style={styles.badgeNum}>{days != null && days >= 0 ? days : '–'}</Text>
              <Text style={styles.badgeTxt}>{days === 1 ? 'día' : 'días'}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.title, { color: t.text }]}>{item.event_name}</Text>
              <Text style={{ color: t.purple, fontSize: 13, fontWeight: '600', marginTop: 2 }}>{formatDateEs(item.event_date)}</Text>
              {!!item.description && <Text style={{ color: t.muted, fontSize: 13, marginTop: 4 }}>{item.description}</Text>}
            </View>
          </View>
        );
      }}
      ListEmptyComponent={
        <Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay eventos próximos en el calendario.</Text>
      }
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32 },
  info: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 12 },
  card: { flexDirection: 'row', gap: 14, padding: 14, borderRadius: 14, borderWidth: 1.5, marginBottom: 10 },
  badge: { width: 56, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 8 },
  badgeNum: { color: '#fff', fontSize: 20, fontWeight: '800' },
  badgeTxt: { color: '#fff', fontSize: 11, fontWeight: '600' },
  title: { fontSize: 15, fontWeight: '700' },
});
