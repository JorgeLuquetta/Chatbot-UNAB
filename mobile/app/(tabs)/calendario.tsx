import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Backdrop, ErrorState, Glass, Loading, OfflineBanner, PageTitle } from '../../src/components';
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

  let body: React.ReactNode;
  if (loading && !data) body = <Loading />;
  else if (error && !data) body = <ErrorState message={error} onRetry={reload} />;
  else {
    const tints = [t.lavender, t.sky, t.mint, t.pink];
    body = (
      <FlatList
        data={events}
        keyExtractor={(e) => `${e.event_name}|${e.event_date}`}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.brand} />}
        ListHeaderComponent={
          <View>
            <PageTitle title="Calendario académico" lead="Próximas fechas importantes del semestre. Te aviso 48 horas antes de cada una." />
            {offlineSince && <OfflineBanner since={offlineSince} />}
            {reminders != null && reminders > 0 && (
              <Glass style={styles.info}>
                <Ionicons name="notifications-outline" size={18} color={t.brandDeep} />
                <Text style={{ color: t.muted, flex: 1, fontSize: 13, fontWeight: '600' }}>
                  Te avisaré 48 horas antes de {reminders === 1 ? 'este evento' : `estos ${reminders} eventos`}.
                </Text>
              </Glass>
            )}
          </View>
        }
        renderItem={({ item, index }) => {
          const days = daysUntil(item.event_date);
          const soon = days != null && days <= 2;
          return (
            <Glass style={[styles.card, soon && { borderColor: t.peach, borderWidth: 2 }]}>
              <View style={[styles.badge, { backgroundColor: soon ? t.peach : tints[index % tints.length] }]}>
                <Text style={[styles.badgeNum, { color: t.onPastel }]}>{days != null && days >= 0 ? days : '–'}</Text>
                <Text style={[styles.badgeTxt, { color: t.onPastel }]}>{days === 1 ? 'día' : 'días'}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.title, { color: t.text }]}>{item.event_name}</Text>
                <Text style={{ color: t.brandDeep, fontSize: 13, fontWeight: '700', marginTop: 2 }}>{formatDateEs(item.event_date)}</Text>
                {!!item.description && <Text style={{ color: t.muted, fontSize: 13, marginTop: 4, lineHeight: 18 }}>{item.description}</Text>}
              </View>
            </Glass>
          );
        }}
        ListEmptyComponent={
          <Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay eventos próximos en el calendario.</Text>
        }
      />
    );
  }

  return <Backdrop>{body}</Backdrop>;
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingTop: 20, paddingBottom: 32 },
  info: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: 16, marginBottom: 12 },
  card: { flexDirection: 'row', gap: 14, padding: 14, borderRadius: 18, marginBottom: 12 },
  badge: { width: 58, borderRadius: 16, alignItems: 'center', justifyContent: 'center', paddingVertical: 8 },
  badgeNum: { fontSize: 20, fontWeight: '800' },
  badgeTxt: { fontSize: 11, fontWeight: '700' },
  title: { fontSize: 15, fontWeight: '800' },
});
