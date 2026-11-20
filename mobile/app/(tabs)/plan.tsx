// Mi plan académico: estado académico, matrícula sugerida, proyección de grado y recomendaciones.
// Datos de /webhook/academic-plan (n8n → MCP get_academic_plan → función SQL academic_plan).
import Ionicons from '@expo/vector-icons/Ionicons';
import { useRouter } from 'expo-router';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { ErrorState, Loading, OfflineBanner } from '../../src/components';
import { api, type AcademicPlan } from '../../src/lib/api';
import { useTheme, type Theme } from '../../src/theme';
import { useCachedResource } from '../../src/useCachedResource';

const STANDING: Record<string, { label: string; color: (t: Theme) => string }> = {
  'excelencia': { label: 'Excelencia académica', color: (t) => t.ok },
  'normal': { label: 'Normal', color: (t) => t.ok },
  'en observación': { label: 'En observación', color: (t) => t.warn },
  'prueba académica': { label: 'Prueba académica', color: (t) => t.errorText },
  'sin notas': { label: 'Sin notas todavía', color: (t) => t.pending },
};

const REC_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  matricula: 'clipboard-outline', riesgo: 'alert-circle-outline', precision: 'locate-outline',
  investigacion: 'flask-outline', autoaprendizaje: 'bulb-outline', grado: 'ribbon-outline',
};

function Card({ title, icon, children }: { title: string; icon: keyof typeof Ionicons.glyphMap; children: React.ReactNode }) {
  const t = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
      <View style={styles.cardHead}>
        <Ionicons name={icon} size={20} color={t.purple} />
        <Text style={[styles.cardTitle, { color: t.text }]}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

export default function PlanScreen() {
  const t = useTheme();
  const router = useRouter();
  const { data, loading, refreshing, error, offlineSince, reload } =
    useCachedResource<AcademicPlan>('academic-plan', api.academicPlan);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return null;

  const { status: st, enrollment: en, projection: pr, recommendations } = data;
  const standing = STANDING[st.standing] ?? { label: st.standing, color: (x: Theme) => x.text };
  const askChat = (q: string) => router.push({ pathname: '/', params: { q } });

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.purple} />}
    >
      {offlineSince && <OfflineBanner since={offlineSince} />}

      {/* Estado académico */}
      <View style={[styles.hero, { backgroundColor: t.navy }]}>
        <Text style={styles.heroLabel}>{data.student.program} · semestre {data.student.current_semester}</Text>
        <View style={styles.heroRow}>
          <View>
            <Text style={styles.heroValue}>{st.gpa != null ? Number(st.gpa).toFixed(2) : '—'}</Text>
            <Text style={styles.heroSub}>promedio ponderado</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.heroValue}>{Number(st.progress_percentage).toFixed(0)}%</Text>
            <Text style={styles.heroSub}>{st.approved_credits} de {st.total_credits} créditos</Text>
          </View>
        </View>
        <View style={[styles.pill, { backgroundColor: 'rgba(255,255,255,0.12)' }]}>
          <View style={[styles.dot, { backgroundColor: standing.color(t) }]} />
          <Text style={styles.pillText}>
            {standing.label}{st.failed_courses > 0 ? ` · ${st.failed_courses} reprobada(s) por repetir` : ''}
          </Text>
        </View>
      </View>

      {/* Matrícula sugerida */}
      <Card title={`Matrícula sugerida ${en.term}`} icon="clipboard-outline">
        <Text style={[styles.muted, { color: t.muted }]}>
          {en.credits} de {en.max_credits} créditos permitidos
        </Text>
        {en.courses.length === 0 && <Text style={{ color: t.muted }}>No hay materias disponibles para matricular.</Text>}
        {en.courses.map((c) => (
          <View key={c.course_code} style={[styles.row, { borderColor: t.border }]}>
            <Ionicons name={c.repeat ? 'refresh-circle' : 'add-circle-outline'} size={22} color={c.repeat ? t.warn : t.ok} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.name, { color: t.text }]}>{c.course_name}</Text>
              <Text style={{ color: t.muted, fontSize: 12 }}>
                {c.course_code} · {c.credits} créditos{c.repeat ? ' · repetir' : ''}
                {c.conditional ? ` · si apruebas ${c.conditional_on.map((x) => x.course_name).join(' y ')}` : ''}
              </Text>
            </View>
          </View>
        ))}
        {en.blocked.length > 0 && (
          <>
            <Text style={[styles.subTitle, { color: t.text }]}>Bloqueadas por prerrequisitos</Text>
            {en.blocked.slice(0, 3).map((b) => (
              <Text key={b.course_code} style={{ color: t.muted, fontSize: 13, marginBottom: 4 }}>
                🔒 {b.course_name}: falta {b.missing_prerequisites.map((m) => m.course_name).join(', ')}
              </Text>
            ))}
          </>
        )}
      </Card>

      {/* Proyección */}
      <Card title="Proyección de grado" icon="trending-up-outline">
        <View style={styles.stats}>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: t.purple }]}>{pr.estimated_graduation_term}</Text>
            <Text style={[styles.statLabel, { color: t.muted }]}>periodo estimado</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: t.purple }]}>{pr.terms_remaining}</Text>
            <Text style={[styles.statLabel, { color: t.muted }]}>periodos restantes</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: t.purple }]}>{pr.remaining_credits}</Text>
            <Text style={[styles.statLabel, { color: t.muted }]}>créditos por aprobar</Text>
          </View>
        </View>
        <Text style={{ color: pr.on_track ? t.ok : t.warn, fontWeight: '600', marginTop: 8 }}>
          {pr.on_track ? 'Vas al día con tu plan de estudios.' : 'Tienes atrasos: prioriza las materias reprobadas y los prerrequisitos.'}
        </Text>
      </Card>

      {/* Recomendaciones */}
      <Card title="Recomendaciones para tu éxito" icon="bulb-outline">
        {recommendations.map((r, i) => (
          <View key={i} style={styles.rec}>
            <Ionicons name={REC_ICON[r.type] ?? 'checkmark-circle-outline'} size={18} color={t.orange} />
            <Text style={{ color: t.text, flex: 1, lineHeight: 20 }}>{r.text}</Text>
          </View>
        ))}
        <Pressable onPress={() => askChat('Dame recomendaciones para tener éxito en el programa')}
          style={[styles.btn, { backgroundColor: t.purple }]}>
          <Ionicons name="chatbubbles-outline" size={16} color="#fff" />
          <Text style={styles.btnText}>Pregúntale al asistente</Text>
        </Pressable>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32, gap: 12 },
  hero: { borderRadius: 16, padding: 18, gap: 10 },
  heroLabel: { color: '#C9D1E6', fontSize: 13, fontWeight: '600' },
  heroRow: { flexDirection: 'row', justifyContent: 'space-between' },
  heroValue: { color: '#FFFFFF', fontSize: 32, fontWeight: '800' },
  heroSub: { color: '#C9D1E6', fontSize: 12 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  pillText: { color: '#FFFFFF', fontWeight: '700', fontSize: 13 },
  card: { borderRadius: 14, borderWidth: 1, padding: 14, gap: 8 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardTitle: { fontSize: 16, fontWeight: '800' },
  muted: { fontSize: 13 },
  subTitle: { fontWeight: '700', marginTop: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: StyleSheet.hairlineWidth },
  name: { fontSize: 15, fontWeight: '600' },
  stats: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  stat: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 22, fontWeight: '800' },
  statLabel: { fontSize: 12, textAlign: 'center' },
  rec: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  btn: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', borderRadius: 12, paddingVertical: 12, marginTop: 6 },
  btnText: { color: '#fff', fontWeight: '700' },
});
