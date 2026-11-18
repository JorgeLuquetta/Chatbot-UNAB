import Ionicons from '@expo/vector-icons/Ionicons';
import { RefreshControl, SectionList, StyleSheet, Text, View } from 'react-native';
import { ErrorState, Loading, OfflineBanner } from '../../src/components';
import { groupBySemester, progressPercentage, statusLabel, type Course } from '../../src/lib/academic';
import { api } from '../../src/lib/api';
import { useTheme, type Theme } from '../../src/theme';
import { useCachedResource } from '../../src/useCachedResource';

function statusStyle(status: string, t: Theme) {
  if (status === 'completed') return { icon: 'checkmark-circle' as const, color: t.ok };
  if (status === 'in_progress') return { icon: 'time' as const, color: t.warn };
  return { icon: 'ellipse-outline' as const, color: t.pending };
}

export default function RutaScreen() {
  const t = useTheme();
  const { data, loading, refreshing, error, offlineSince, reload } = useCachedResource('academic-route', api.academicRoute);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;

  const courses: Course[] = data?.courses ?? [];
  const progress = data?.progress_percentage ?? progressPercentage(courses);
  const count = (s: string) => courses.filter((c) => c.status === s).length;
  const sections = groupBySemester(courses).map((g) => ({ title: `Semestre ${g.semester}`, data: g.courses }));

  return (
    <SectionList
      sections={sections}
      keyExtractor={(c) => c.course_code}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.purple} />}
      stickySectionHeadersEnabled={false}
      ListHeaderComponent={
        <View>
          {offlineSince && <OfflineBanner since={offlineSince} />}
          <View style={[styles.summary, { backgroundColor: t.navy }]}>
            <Text style={styles.summaryLabel}>Avance del plan de estudios</Text>
            <Text style={styles.summaryValue}>{progress.toFixed(1)}%</Text>
            <View style={styles.bar}>
              <View style={[styles.barFill, { width: `${Math.min(100, Math.max(0, progress))}%`, backgroundColor: t.orange }]} />
            </View>
            <View style={styles.stats}>
              <Text style={styles.stat}>✔ {count('completed')} aprobados</Text>
              <Text style={styles.stat}>◷ {count('in_progress')} en curso</Text>
              <Text style={styles.stat}>○ {count('pending')} pendientes</Text>
            </View>
          </View>
        </View>
      }
      renderSectionHeader={({ section }) => (
        <Text style={[styles.section, { color: t.purple }]}>{section.title}</Text>
      )}
      renderItem={({ item }) => {
        const s = statusStyle(item.status, t);
        return (
          <View style={[styles.row, { backgroundColor: t.card, borderColor: t.border }]}>
            <Ionicons name={s.icon} size={22} color={s.color} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.name, { color: t.text }]}>{item.course_name}</Text>
              <Text style={{ color: t.muted, fontSize: 12 }}>{item.course_code} · {statusLabel(item.status)}</Text>
            </View>
            {item.grade != null && <Text style={[styles.grade, { color: t.text }]}>{Number(item.grade).toFixed(1)}</Text>}
          </View>
        );
      }}
      ListEmptyComponent={<Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay cursos registrados.</Text>}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32 },
  summary: { borderRadius: 16, padding: 18, marginBottom: 8 },
  summaryLabel: { color: '#C9D1E6', fontSize: 13, fontWeight: '600' },
  summaryValue: { color: '#FFFFFF', fontSize: 36, fontWeight: '800', marginVertical: 4 },
  bar: { height: 10, borderRadius: 5, backgroundColor: 'rgba(255,255,255,0.18)', overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 5 },
  stats: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, flexWrap: 'wrap', gap: 6 },
  stat: { color: '#ECEFF6', fontSize: 12, fontWeight: '600' },
  section: { fontWeight: '800', fontSize: 13, textTransform: 'uppercase', letterSpacing: 0.8, marginTop: 18, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 8 },
  name: { fontSize: 15, fontWeight: '600' },
  grade: { fontSize: 16, fontWeight: '800', fontVariant: ['tabular-nums'] },
});
