import Ionicons from '@expo/vector-icons/Ionicons';
import { RefreshControl, SectionList, StyleSheet, Text, View } from 'react-native';
import { Backdrop, ErrorState, Glass, Loading, OfflineBanner, PageTitle } from '../../src/components';
import { groupBySemester, progressPercentage, statusLabel, type Course } from '../../src/lib/academic';
import { api } from '../../src/lib/api';
import { useTheme, type Theme } from '../../src/theme';
import { useCachedResource } from '../../src/useCachedResource';

function statusStyle(status: string, t: Theme) {
  if (status === 'completed') return { icon: 'checkmark' as const, bg: t.mint };
  if (status === 'in_progress') return { icon: 'time-outline' as const, bg: t.lemon };
  return { icon: 'ellipse-outline' as const, bg: t.chip };
}

export default function RutaScreen() {
  const t = useTheme();
  const { data, loading, refreshing, error, offlineSince, reload } = useCachedResource('academic-route', api.academicRoute);

  let body: React.ReactNode;
  if (loading && !data) body = <Loading />;
  else if (error && !data) body = <ErrorState message={error} onRetry={reload} />;
  else {
    const courses: Course[] = data?.courses ?? [];
    const progress = data?.progress_percentage ?? progressPercentage(courses);
    const count = (s: string) => courses.filter((c) => c.status === s).length;
    const sections = groupBySemester(courses).map((g) => ({ title: `Semestre ${g.semester}`, data: g.courses }));
    const stats: [string, number, string][] = [
      ['aprobados', count('completed'), t.mint],
      ['en curso', count('in_progress'), t.lemon],
      ['pendientes', count('pending'), t.chip],
    ];

    body = (
      <SectionList
        sections={sections}
        keyExtractor={(c) => c.course_code}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.brand} />}
        stickySectionHeadersEnabled={false}
        ListHeaderComponent={
          <View>
            <PageTitle title="Mi ruta académica" lead="Tus cursos por semestre, con su estado y tu nota. Funciona sin conexión con la última copia." />
            {offlineSince && <OfflineBanner since={offlineSince} />}
            <Glass style={styles.summary}>
              <Text style={[styles.summaryLabel, { color: t.muted }]}>Avance del plan de estudios</Text>
              <Text style={[styles.summaryValue, { color: t.brandDeep }]}>{progress.toFixed(1)}%</Text>
              <View style={[styles.bar, { backgroundColor: t.chip }]}>
                <View style={[styles.barFill, { width: `${Math.min(100, Math.max(0, progress))}%`, backgroundColor: t.lavender }]} />
              </View>
              <View style={styles.stats}>
                {stats.map(([label, n, bg]) => (
                  <View key={label} style={[styles.stat, { backgroundColor: bg }]}>
                    <Text style={[styles.statNum, { color: t.onPastel }]}>{n}</Text>
                    <Text style={[styles.statLabel, { color: t.onPastel }]}>{label}</Text>
                  </View>
                ))}
              </View>
            </Glass>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Text style={[styles.section, { color: t.brandDeep }]}>{section.title}</Text>
        )}
        renderItem={({ item }) => {
          const s = statusStyle(item.status, t);
          return (
            <Glass style={styles.row}>
              <View style={[styles.statusIcon, { backgroundColor: s.bg }]}>
                <Ionicons name={s.icon} size={16} color={t.onPastel} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.name, { color: t.text }]}>{item.course_name}</Text>
                <Text style={{ color: t.muted, fontSize: 12, fontWeight: '600' }}>{item.course_code} · {statusLabel(item.status)}</Text>
              </View>
              {item.grade != null && (
                <Text style={[styles.grade, { color: t.brandDeep }]}>{Number(item.grade).toFixed(1)}</Text>
              )}
            </Glass>
          );
        }}
        ListEmptyComponent={<Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay cursos registrados.</Text>}
      />
    );
  }

  return <Backdrop>{body}</Backdrop>;
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingTop: 20, paddingBottom: 32 },
  summary: { padding: 18, marginBottom: 6 },
  summaryLabel: { fontSize: 13, fontWeight: '700' },
  summaryValue: { fontSize: 36, fontWeight: '800', marginVertical: 4, fontVariant: ['tabular-nums'] },
  bar: { height: 12, borderRadius: 6, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 6 },
  stats: { flexDirection: 'row', gap: 8, marginTop: 14 },
  stat: { flex: 1, borderRadius: 14, paddingVertical: 8, alignItems: 'center' },
  statNum: { fontSize: 18, fontWeight: '800' },
  statLabel: { fontSize: 11, fontWeight: '700' },
  section: { fontWeight: '800', fontSize: 13, textTransform: 'uppercase', letterSpacing: 0.8, marginTop: 18, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 16, marginBottom: 8 },
  statusIcon: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 15, fontWeight: '700' },
  grade: { fontSize: 16, fontWeight: '800', fontVariant: ['tabular-nums'] },
});
