// Mi plan académico: estado académico, matrícula sugerida, proyección de grado y recomendaciones.
// Datos de /webhook/academic-plan (n8n → MCP get_academic_plan → función SQL academic_plan).
// Mismo diseño que web/plan.html: tarjetas de vidrio con cifras grandes en morado.
import Ionicons from '@expo/vector-icons/Ionicons';
import { useRouter } from 'expo-router';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Backdrop, ErrorState, Glass, Loading, OfflineBanner, PageTitle } from '../../src/components';
import { api, type AcademicPlan } from '../../src/lib/api';
import { useTheme, type Theme } from '../../src/theme';
import { useCachedResource } from '../../src/useCachedResource';

const STANDING: Record<string, { label: string; color: (t: Theme) => string }> = {
  'excelencia': { label: 'Excelencia académica', color: (t) => t.ok },
  'normal': { label: 'Normal', color: (t) => t.ok },
  'en observación': { label: 'En observación', color: (t) => t.caution },
  'prueba académica': { label: 'Prueba académica', color: (t) => t.bad },
  'sin notas': { label: 'Sin notas todavía', color: (t) => t.muted },
};

const REC_ICON: Record<string, string> = {
  matricula: '🧾', riesgo: '⚠️', precision: '🎯', investigacion: '🔬', autoaprendizaje: '💡', grado: '🎓',
};

function Card({ title, icon, tint, children }: { title: string; icon: string; tint: string; children: React.ReactNode }) {
  const t = useTheme();
  return (
    <Glass style={styles.card}>
      <View style={styles.cardHead}>
        <View style={[styles.cardIcon, { backgroundColor: tint }]}><Text style={{ fontSize: 16 }}>{icon}</Text></View>
        <Text style={[styles.cardTitle, { color: t.text }]}>{title}</Text>
      </View>
      {children}
    </Glass>
  );
}

function Kpi({ value, label }: { value: string | number; label: string }) {
  const t = useTheme();
  return (
    <View style={styles.kpi}>
      <Text style={[styles.kpiValue, { color: t.brandDeep }]} adjustsFontSizeToFit numberOfLines={1}>{value}</Text>
      <Text style={[styles.kpiLabel, { color: t.muted }]}>{label}</Text>
    </View>
  );
}

export default function PlanScreen() {
  const t = useTheme();
  const router = useRouter();
  const { data, loading, refreshing, error, offlineSince, reload } =
    useCachedResource<AcademicPlan>('academic-plan', api.academicPlan);

  if (loading && !data) return <Backdrop><Loading /></Backdrop>;
  if (error && !data) return <Backdrop><ErrorState message={error} onRetry={reload} /></Backdrop>;
  if (!data) return <Backdrop>{null}</Backdrop>;

  const { status: st, enrollment: en, projection: pr, recommendations } = data;
  const standing = STANDING[st.standing] ?? { label: st.standing, color: (x: Theme) => x.text };
  const askChat = (q: string) => router.push({ pathname: '/', params: { q } });

  return (
    <Backdrop>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} tintColor={t.brand} />}
      >
        <PageTitle
          title="Plan académico"
          lead="Estado académico, matrícula sugerida, proyección de grado y recomendaciones calculadas con tus datos (prerrequisitos, créditos y notas)."
        />
        {offlineSince && <OfflineBanner since={offlineSince} />}

        {/* Estado académico */}
        <Glass style={styles.card}>
          <Text style={[styles.cardTitle, { color: t.text }]}>{data.student.full_name}</Text>
          <Text style={{ color: t.muted, fontWeight: '600' }}>
            {data.student.program} · semestre {data.student.current_semester}
          </Text>
          <View style={[styles.kpis, { marginTop: 6 }]}>
            <Kpi value={st.gpa != null ? Number(st.gpa).toFixed(2) : '—'} label="promedio ponderado" />
            <Kpi value={`${Math.round(Number(st.progress_percentage))}%`} label={`${st.approved_credits} de ${st.total_credits} créditos`} />
            <Kpi value={st.failed_courses} label="reprobadas por repetir" />
          </View>
          <View style={[styles.badge, { backgroundColor: t.chip }]}>
            <View style={[styles.dot, { backgroundColor: standing.color(t) }]} />
            <Text style={{ color: standing.color(t), fontWeight: '800', fontSize: 13 }}>Situación: {standing.label}</Text>
          </View>
        </Glass>

        {/* Proyección */}
        <Card title="Proyección de grado" icon="📈" tint={t.sky}>
          <View style={styles.kpis}>
            <Kpi value={pr.estimated_graduation_term} label="periodo estimado" />
            <Kpi value={pr.terms_remaining} label="periodos restantes" />
            <Kpi value={pr.remaining_credits} label="créditos por aprobar" />
          </View>
          <Text style={{ color: pr.on_track ? t.ok : t.caution, fontWeight: '700', marginTop: 4 }}>
            {pr.on_track ? 'Vas al día con tu plan de estudios.' : 'Tienes atrasos: prioriza las materias reprobadas y los prerrequisitos.'}
          </Text>
        </Card>

        {/* Matrícula sugerida */}
        <Card title={`Matrícula sugerida ${en.term}`} icon="🧾" tint={t.lavender}>
          <Text style={{ color: t.muted, fontSize: 13, fontWeight: '600' }}>
            {en.credits} de {en.max_credits} créditos permitidos
          </Text>
          {en.courses.length === 0 && <Text style={{ color: t.muted }}>No hay materias disponibles para matricular.</Text>}
          {en.courses.map((c) => (
            <View key={c.course_code} style={[styles.row, { borderTopColor: t.line }]}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.name, { color: t.text }]}>
                  <Text style={{ fontWeight: '800' }}>{c.course_code}</Text> {c.course_name}
                </Text>
                <Text style={{ color: t.muted, fontSize: 12, fontWeight: '700' }}>
                  {c.credits} créditos{c.repeat ? ' · repetir' : ''}
                  {c.conditional ? ` · si apruebas ${c.conditional_on.map((x) => x.course_name).join(' y ')}` : ''}
                </Text>
              </View>
              <View style={[styles.rowIcon, { backgroundColor: c.repeat ? t.peach : t.mint }]}>
                <Ionicons name={c.repeat ? 'refresh' : 'add'} size={16} color={t.onPastel} />
              </View>
            </View>
          ))}
          {en.blocked.length > 0 && (
            <View style={[styles.blocked, { backgroundColor: t.chip }]}>
              <Text style={{ color: t.text, fontWeight: '800', marginBottom: 4 }}>Bloqueadas por prerrequisitos</Text>
              {en.blocked.slice(0, 3).map((b) => (
                <Text key={b.course_code} style={{ color: t.muted, fontSize: 13, marginBottom: 3, fontWeight: '600' }}>
                  🔒 {b.course_name}: falta {b.missing_prerequisites.map((m) => m.course_name).join(', ')}
                </Text>
              ))}
            </View>
          )}
        </Card>

        {/* Recomendaciones */}
        <Card title="Recomendaciones" icon="💡" tint={t.lemon}>
          {recommendations.map((r, i) => (
            <View key={i} style={styles.rec}>
              <Text style={{ fontSize: 14 }}>{REC_ICON[r.type] ?? '✅'}</Text>
              <Text style={{ color: t.text, flex: 1, lineHeight: 20 }}>{r.text}</Text>
            </View>
          ))}
          <Pressable
            onPress={() => askChat('Dame recomendaciones para tener éxito en el programa')}
            style={({ pressed }) => [styles.btn, { backgroundColor: pressed ? t.pink : t.lavender }]}
          >
            <Ionicons name="chatbubbles-outline" size={16} color={t.onPastel} />
            <Text style={[styles.btnText, { color: t.onPastel }]}>Pregúntale al asistente</Text>
          </Pressable>
        </Card>
      </ScrollView>
    </Backdrop>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingTop: 20, paddingBottom: 32, gap: 14 },
  card: { padding: 18, gap: 8 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 2 },
  cardIcon: { width: 34, height: 34, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: 18, fontWeight: '800' },
  kpis: { flexDirection: 'row', gap: 8 },
  kpi: { flex: 1 },
  kpiValue: { fontSize: 22, fontWeight: '800', fontVariant: ['tabular-nums'] },
  kpiLabel: { fontSize: 12 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5, marginTop: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: 1 },
  rowIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 14, lineHeight: 19 },
  blocked: { borderRadius: 14, padding: 12, marginTop: 4 },
  rec: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  btn: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', borderRadius: 999, paddingVertical: 12, marginTop: 8 },
  btnText: { fontWeight: '800' },
});
