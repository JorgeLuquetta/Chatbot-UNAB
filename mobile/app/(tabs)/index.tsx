import Ionicons from '@expo/vector-icons/Ionicons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { useAuth, useSession } from '../../src/auth';
import { MESSAGE_MAX, isValidMessage } from '../../src/lib/academic';
import { api } from '../../src/lib/api';
import { chatErrorMessage, isSessionExpired } from '../../src/lib/errors';
import { useTheme } from '../../src/theme';

type Role = 'user' | 'bot' | 'error';
interface Msg {
  id: string;
  role: Role;
  text: string;
  intent?: string;
  retryOf?: string; // texto a reenviar si fue un error
}

const INTENT_LABEL: Record<string, string> = {
  'consulta-general': 'Documentos UNAB',
  calendario: 'Calendario',
  'cursos-realizados': 'Mis cursos',
  noticias: 'Noticias',
  'plan-academico': 'Mi plan académico',
  correo: 'Correo',
};

const SUGGESTIONS = [
  '¿Qué materias debo matricular el próximo semestre?',
  '¿Cuál es mi estado académico?',
  '¿Cuándo me voy a graduar?',
  'Dame recomendaciones para tener éxito',
  '¿Cuáles son los requisitos de grado?',
  '¿Qué noticias de tecnología hay hoy?',
  'Envíame mi informe de avance al correo',
];

const newId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export default function ChatScreen() {
  const t = useTheme();
  const session = useSession();
  const { signOut } = useAuth();
  const storageKey = `chat:${session.student_id}`;
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const listRef = useRef<FlatList<Msg>>(null);

  // Historial local (la memoria "real" está en el servidor; esto es para mostrarla al abrir la app)
  useEffect(() => {
    AsyncStorage.getItem(storageKey).then((raw) => raw && setMessages(JSON.parse(raw))).catch(() => {});
  }, [storageKey]);
  useEffect(() => {
    AsyncStorage.setItem(storageKey, JSON.stringify(messages.slice(-60))).catch(() => {});
  }, [messages, storageKey]);

  useEffect(() => {
    if (!sending) return;
    setElapsed(0);
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [sending]);

  const send = useCallback(async (text: string) => {
    if (!isValidMessage(text) || sending) return;
    setInput('');
    setMessages((m) => [...m.filter((x) => x.role !== 'error'), { id: newId(), role: 'user', text }]);
    setSending(true);
    try {
      const r = await api.chat(session.student_id, text);
      setMessages((m) => [...m, { id: newId(), role: 'bot', text: r.response, intent: r.intent }]);
    } catch (e) {
      if (isSessionExpired(e)) {
        await signOut();
        return;
      }
      setMessages((m) => [...m, { id: newId(), role: 'error', text: chatErrorMessage(e), retryOf: text }]);
    } finally {
      setSending(false);
    }
  }, [sending, session, signOut]);

  // Pregunta enviada desde otra pantalla (p. ej. "Pregúntale al asistente" en Mi plan)
  const { q } = useLocalSearchParams<{ q?: string }>();
  const lastQ = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (typeof q === 'string' && q && q !== lastQ.current) {
      lastQ.current = q;
      send(q);
    }
  }, [q, send]);

  const retry = (msg: Msg) => {
    if (!msg.retryOf) return;
    // Quita el error y la pregunta que lo causó; send() la vuelve a agregar
    setMessages((m) => {
      const i = m.findIndex((x) => x.id === msg.id);
      return m.filter((_, j) => j !== i && !(j === i - 1 && m[j].role === 'user'));
    });
    send(msg.retryOf);
  };

  const firstName = session.full_name?.split(' ')[0] ?? '';
  const tooLong = input.length > MESSAGE_MAX;

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'} keyboardVerticalOffset={90}>
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={[styles.hello, { color: t.text }]}>Hola{firstName ? `, ${firstName}` : ''} 👋</Text>
            <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
              {!!session.program && <Text style={{ color: t.text }}>• Programa: {session.program}</Text>}
              <Text style={{ color: t.text }}>
                • Semestre actual: {session.current_semester ? `${session.current_semester}.º` : 'sin materias en curso'}
              </Text>
              {session.progress_percentage != null && (
                <Text style={{ color: t.text }}>• Avance en la carrera: {session.progress_percentage} %</Text>
              )}
            </View>
            <Text style={{ color: t.muted, textAlign: 'center', marginBottom: 16 }}>
              ¿En qué te ayudo? Pregúntame qué matricular, tu estado académico, cuándo te gradúas, el reglamento, el calendario o las noticias.
            </Text>
            {SUGGESTIONS.map((s) => (
              <Pressable key={s} onPress={() => send(s)} style={[styles.chip, { borderColor: t.purple }]}>
                <Text style={{ color: t.purple, fontWeight: '600' }}>{s}</Text>
              </Pressable>
            ))}
          </View>
        }
        renderItem={({ item }) => {
          if (item.role === 'user') {
            return (
              <View style={[styles.bubble, styles.right, { backgroundColor: t.userBubble }]}>
                <Text style={{ color: t.userText, fontSize: 15 }}>{item.text}</Text>
              </View>
            );
          }
          if (item.role === 'error') {
            return (
              <View style={[styles.bubble, styles.left, { backgroundColor: t.errorBg }]}>
                <Text style={{ color: t.errorText }}>{item.text}</Text>
                <Pressable onPress={() => retry(item)} style={styles.retry} accessibilityRole="button">
                  <Ionicons name="refresh" size={16} color={t.errorText} />
                  <Text style={{ color: t.errorText, fontWeight: '700' }}>Reintentar</Text>
                </Pressable>
              </View>
            );
          }
          return (
            <View style={[styles.bubble, styles.left, { backgroundColor: t.botBubble, borderColor: t.border, borderWidth: 1 }]}>
              {item.intent && INTENT_LABEL[item.intent] && (
                <Text style={[styles.tag, { color: t.warn }]}>{INTENT_LABEL[item.intent]}</Text>
              )}
              <Text style={{ color: t.text, fontSize: 15, lineHeight: 21 }}>
                {/* Negritas **así** del asistente */}
                {item.text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
                  /^\*\*[^*]+\*\*$/.test(part)
                    ? <Text key={i} style={{ fontWeight: '800' }}>{part.slice(2, -2)}</Text>
                    : part.replace(/\*([^*\n]+)\*/g, '$1'))}
              </Text>
            </View>
          );
        }}
        ListFooterComponent={
          sending ? (
            <View style={[styles.bubble, styles.left, styles.typing, { backgroundColor: t.botBubble, borderColor: t.border }]}>
              <ActivityIndicator color={t.purple} />
              <Text style={{ color: t.muted }}>
                Pensando… {elapsed}s{elapsed > 20 ? ' (el modelo local puede tardar hasta un minuto)' : ''}
              </Text>
            </View>
          ) : undefined
        }
      />

      <View style={[styles.composer, { backgroundColor: t.card, borderTopColor: t.border }]}>
        <TextInput
          style={[styles.input, { color: t.text, backgroundColor: t.bg, borderColor: tooLong ? t.errorText : t.border }]}
          value={input}
          onChangeText={setInput}
          placeholder="Escribe tu pregunta…"
          placeholderTextColor={t.tabInactive}
          multiline
          maxLength={MESSAGE_MAX + 50}
          editable={!sending}
        />
        <Pressable
          onPress={() => send(input)}
          disabled={!isValidMessage(input) || sending}
          style={[styles.send, { backgroundColor: isValidMessage(input) && !sending ? t.purple : t.tabInactive }]}
          accessibilityLabel="Enviar"
        >
          <Ionicons name="send" size={18} color="#fff" />
        </Pressable>
      </View>
      {input.length > MESSAGE_MAX - 200 && (
        <Text style={[styles.counter, { color: tooLong ? t.errorText : t.muted, backgroundColor: t.card }]}>
          {input.length}/{MESSAGE_MAX}
        </Text>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  list: { padding: 16, gap: 10, flexGrow: 1 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 32 },
  hello: { fontSize: 24, fontWeight: '800', marginBottom: 6 },
  card: { borderWidth: 1, borderRadius: 12, padding: 12, gap: 4, marginBottom: 14, alignSelf: 'stretch' },
  chip: { borderWidth: 1.5, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 9, marginTop: 8, maxWidth: '100%' },
  bubble: { maxWidth: '85%', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10 },
  right: { alignSelf: 'flex-end', borderBottomRightRadius: 4 },
  left: { alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  tag: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', marginBottom: 4, letterSpacing: 0.5 },
  typing: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, marginTop: 10 },
  retry: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', padding: 10, gap: 8, borderTopWidth: 1 },
  input: { flex: 1, borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingTop: 10, paddingBottom: 10, maxHeight: 120, fontSize: 15 },
  send: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  counter: { textAlign: 'right', paddingHorizontal: 16, paddingBottom: 6, fontSize: 12 },
});
