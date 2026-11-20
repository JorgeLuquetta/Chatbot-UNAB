// Piezas del chat con el mismo diseño de la página web (web/index.html):
// encabezado con logo, fila de temas, burbujas pastel, sugerencias de colores y caja de texto tipo píldora.
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Logo } from './components';
import { bubbleShadow, glassShadow, useTheme, type Theme } from './theme';

export const HEADER_HEIGHT = 66;

// Etiquetas y colores de la intención detectada (LABELS / TAG_COLORS de la web)
export const INTENT_LABEL: Record<string, string> = {
  'consulta-general': 'Reglamento',
  'cursos-realizados': 'Tu historial',
  noticias: 'Noticias',
  calendario: 'Calendario',
  'plan-academico': 'Tu plan académico',
  correo: 'Correo',
};
export function intentColor(intent: string | undefined, t: Theme): string {
  const map: Record<string, string> = {
    'consulta-general': t.lavender, 'cursos-realizados': t.mint, noticias: t.pink,
    calendario: t.sky, 'plan-academico': t.lemon, correo: t.peach,
  };
  return (intent && map[intent]) || t.mint;
}

function initials(full?: string) {
  return String(full ?? '').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

// ---------- Encabezado ----------
export function ChatHeader({ student, onChange }: {
  student?: { student_id: string; full_name?: string } | null;
  onChange?: () => void;
}) {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.header, { paddingTop: insets.top + 10, backgroundColor: t.glassStrong, borderBottomColor: t.line }]}>
      <Logo size={42} />
      <View style={{ flexShrink: 1 }}>
        <Text style={[styles.title, { color: t.text }]} numberOfLines={1}>
          Chatbot <Text style={{ color: t.brand }}>UN</Text><Text style={{ color: '#f07aa8' }}>AB</Text>
        </Text>
        {!student && <Text style={[styles.subtitle, { color: t.muted }]}>Tu asistente académico, en línea</Text>}
      </View>
      {student && (
        <View style={[styles.who, { backgroundColor: t.glassStrong, borderColor: t.line }]}>
          <View style={[styles.avatar, { backgroundColor: t.mint }]}>
            <View style={[StyleSheet.absoluteFill, styles.avatarHalf, { backgroundColor: t.sky }]} />
            <Text style={[styles.avatarText, { color: t.onPastel }]}>{initials(student.full_name)}</Text>
          </View>
          <View style={{ flexShrink: 1 }}>
            <Text style={[styles.whoName, { color: t.text }]} numberOfLines={1}>
              {student.full_name?.split(' ')[0] ?? ''} · {student.student_id}
            </Text>
            {onChange && (
              <Pressable onPress={onChange} hitSlop={8} accessibilityRole="button" accessibilityLabel="Cambiar estudiante">
                <Text style={[styles.link, { color: t.brand }]}>Cambiar estudiante</Text>
              </Pressable>
            )}
          </View>
        </View>
      )}
    </View>
  );
}

// ---------- Temas que conoce el asistente ----------
const TOPICS: [string, string, keyof Pick<Theme, 'lavender' | 'mint' | 'pink' | 'sky' | 'lemon' | 'peach'>][] = [
  ['🎓', 'Matrícula y plan', 'lavender'],
  ['📘', 'Reglamento', 'mint'],
  ['🧾', 'Tus cursos', 'pink'],
  ['📰', 'Noticias', 'sky'],
  ['📅', 'Calendario', 'lemon'],
  ['✉️', 'Envíos por correo', 'peach'],
];

export function Topics() {
  const t = useTheme();
  return (
    <View style={{ borderBottomWidth: 1, borderBottomColor: t.line }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.topics}
        accessibilityLabel="Temas que conoce el asistente">
        {TOPICS.map(([icon, label, color]) => (
          <View key={label} style={[styles.topic, { backgroundColor: t[color] }]}>
            <View style={styles.topicIcon}><Text style={{ fontSize: 11 }}>{icon}</Text></View>
            <Text style={[styles.topicText, { color: t.onPastel }]}>{label}</Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

// ---------- Burbujas ----------
// Negritas **así** del asistente; *cursiva* se muestra como texto normal
export function RichText({ text, color }: { text: string; color: string }) {
  return (
    <Text style={{ color, fontSize: 15, lineHeight: 22 }}>
      {text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
        /^\*\*[^*]+\*\*$/.test(part)
          ? <Text key={i} style={{ fontWeight: '800' }}>{part.slice(2, -2)}</Text>
          : part.replace(/\*([^*\n]+)\*/g, '$1'))}
    </Text>
  );
}

export function MeBubble({ text }: { text: string }) {
  const t = useTheme();
  return (
    <View style={[styles.bubble, styles.me, { backgroundColor: t.meBubble }, bubbleShadow(t)]}>
      <Text style={{ color: t.onPastel, fontSize: 15, lineHeight: 21, fontWeight: '600' }}>{text}</Text>
    </View>
  );
}

export function BotBubble({ children, warn }: { children: React.ReactNode; warn?: boolean }) {
  const t = useTheme();
  return (
    <View style={styles.botRow}>
      <View style={[styles.botAvatar, { backgroundColor: warn ? t.peach : t.lavender }, bubbleShadow(t)]}>
        <View style={[StyleSheet.absoluteFill, styles.avatarHalf, { backgroundColor: warn ? t.lemon : t.pink }]} />
        <Text style={{ fontSize: 15 }}>{warn ? '⚠️' : '🎓'}</Text>
      </View>
      <View
        style={[
          styles.bubble, styles.bot,
          { backgroundColor: warn ? t.warnBg : t.botBubble, borderColor: warn ? t.warnLine : t.line },
          bubbleShadow(t),
        ]}
      >
        {children}
      </View>
    </View>
  );
}

export function IntentTag({ intent, secs }: { intent?: string; secs?: number }) {
  const t = useTheme();
  const label = (intent && INTENT_LABEL[intent]) || 'Respuesta';
  return (
    <View style={[styles.tag, { backgroundColor: intentColor(intent, t) }]}>
      <View style={[styles.tagDot, { backgroundColor: t.onPastel }]} />
      <Text style={[styles.tagText, { color: t.onPastel }]}>{label}{secs != null ? ` · ${secs} s` : ''}</Text>
    </View>
  );
}

// ---------- Sugerencias ----------
export function Suggestions({ items, onPick }: { items: string[]; onPick: (q: string) => void }) {
  const t = useTheme();
  return (
    <View style={styles.chips}>
      {items.map((q, i) => (
        <Pressable
          key={q}
          onPress={() => onPick(q)}
          style={({ pressed }) => [
            styles.suggestion, { backgroundColor: t.suggestion[i % 4] }, bubbleShadow(t),
            pressed && { transform: [{ translateY: -2 }, { rotate: '-1deg' }] },
          ]}
        >
          <Text style={[styles.suggestionText, { color: t.onPastel }]}>{q}</Text>
        </Pressable>
      ))}
    </View>
  );
}

// ---------- Caja de texto ----------
export function Composer({ value, onChangeText, onSend, canSend, invalid, ...input }: TextInputProps & {
  value: string; onChangeText: (v: string) => void; onSend: () => void; canSend: boolean; invalid?: boolean;
}) {
  const t = useTheme();
  return (
    <View style={styles.composerWrap}>
      <View style={[styles.form, { backgroundColor: t.glassStrong, borderColor: invalid ? t.bad : t.line }, glassShadow(t)]}>
        <TextInput
          style={[styles.input, { color: t.text }]}
          value={value}
          onChangeText={onChangeText}
          placeholderTextColor={t.muted}
          {...input}
        />
        <Pressable
          onPress={onSend}
          disabled={!canSend}
          style={({ pressed }) => [
            styles.send, { backgroundColor: t.lavender, opacity: canSend ? 1 : 0.55 },
            pressed && canSend && { transform: [{ scale: 0.95 }], backgroundColor: t.pink },
          ]}
          accessibilityLabel="Enviar"
          accessibilityRole="button"
        >
          <Ionicons name="arrow-forward" size={20} color={t.onPastel} />
        </Pressable>
      </View>
      <Text style={[styles.hint, { color: t.muted }]}>Cada respuesta tarda alrededor de 1 minuto ✨</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 10, borderBottomWidth: 1 },
  title: { fontSize: 20, fontWeight: '700', letterSpacing: 0.2 },
  subtitle: { fontSize: 12, marginTop: 1 },
  who: {
    marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 8, maxWidth: '58%',
    borderWidth: 1, borderRadius: 999, paddingVertical: 4, paddingLeft: 4, paddingRight: 12,
  },
  avatar: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  avatarHalf: { left: '50%', opacity: 0.7 },
  avatarText: { fontWeight: '800', fontSize: 12 },
  whoName: { fontWeight: '700', fontSize: 12 },
  link: { fontSize: 11, fontWeight: '700' },
  topics: { gap: 8, paddingHorizontal: 16, paddingVertical: 10 },
  topic: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingVertical: 4, paddingLeft: 5, paddingRight: 12 },
  topicIcon: { width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(255,255,255,0.7)', alignItems: 'center', justifyContent: 'center' },
  topicText: { fontSize: 13, fontWeight: '700' },
  bubble: { borderRadius: 20, paddingHorizontal: 15, paddingVertical: 11 },
  me: { alignSelf: 'flex-end', maxWidth: '85%', borderBottomRightRadius: 6 },
  botRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 10, alignSelf: 'flex-start', maxWidth: '92%' },
  botAvatar: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  bot: { flexShrink: 1, borderWidth: 1, borderBottomLeftRadius: 6 },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', marginTop: 8, borderRadius: 999, paddingVertical: 2, paddingLeft: 8, paddingRight: 10 },
  tagDot: { width: 6, height: 6, borderRadius: 3, opacity: 0.55 },
  tagText: { fontSize: 11, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginLeft: 42 },
  suggestion: { borderRadius: 14, paddingHorizontal: 14, paddingVertical: 8, maxWidth: '100%' },
  suggestionText: { fontSize: 14, fontWeight: '700' },
  composerWrap: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
  form: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, borderRadius: 26, borderWidth: 2, paddingVertical: 5, paddingRight: 5, paddingLeft: 18 },
  input: { flex: 1, fontSize: 15, fontWeight: '600', paddingTop: 11, paddingBottom: 11, maxHeight: 120 },
  send: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  hint: { textAlign: 'center', fontSize: 12, marginTop: 6 },
});
