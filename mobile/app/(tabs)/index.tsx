import Ionicons from '@expo/vector-icons/Ionicons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth, useSession } from '../../src/auth';
import { BotBubble, Composer, HEADER_HEIGHT, IntentTag, MeBubble, RichText, Suggestions, Topics } from '../../src/chatui';
import { Backdrop, TypingDots } from '../../src/components';
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
  secs?: number; // segundos que tardó la respuesta
  retryOf?: string; // texto a reenviar si fue un error
}

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
const fmtPct = (n?: number) => `${Number(n ?? 0).toLocaleString('es-CO', { maximumFractionDigits: 1 })} %`;

export default function ChatScreen() {
  const t = useTheme();
  const insets = useSafeAreaInsets();
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
    const started = Date.now();
    try {
      const r = await api.chat(session.student_id, text);
      const secs = Math.round((Date.now() - started) / 1000);
      setMessages((m) => [...m, { id: newId(), role: 'bot', text: r.response, intent: r.intent, secs }]);
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
  const semester = session.current_semester ? `${session.current_semester}.º semestre` : 'sin materias en curso';
  const welcome =
    `¡Hola, ${firstName}! 👋\n\n` +
    (session.program ? `• Programa: ${session.program}\n` : '') +
    `• Semestre actual: ${semester}` +
    (session.progress_percentage != null ? `\n• Avance en la carrera: ${fmtPct(session.progress_percentage)}` : '') +
    '\n\n¿En qué te puedo ayudar? (Cada respuesta tarda alrededor de 1 minuto.)';

  return (
    <Backdrop>
      <Topics />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={insets.top + HEADER_HEIGHT}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          ListHeaderComponent={
            <View style={{ gap: 14 }}>
              <BotBubble><RichText text={welcome} color={t.text} /></BotBubble>
              {messages.length === 0 && <Suggestions items={SUGGESTIONS} onPick={send} />}
            </View>
          }
          renderItem={({ item }) => {
            if (item.role === 'user') return <MeBubble text={item.text} />;
            if (item.role === 'error') {
              return (
                <BotBubble warn>
                  <Text style={{ color: t.warn, fontSize: 15, lineHeight: 21 }}>{item.text}</Text>
                  <Pressable onPress={() => retry(item)} style={[styles.retry, { backgroundColor: t.peach }]} accessibilityRole="button">
                    <Ionicons name="refresh" size={15} color={t.onPastel} />
                    <Text style={{ color: t.onPastel, fontWeight: '800', fontSize: 13 }}>Reintentar</Text>
                  </Pressable>
                </BotBubble>
              );
            }
            return (
              <BotBubble>
                <RichText text={item.text} color={t.text} />
                <IntentTag intent={item.intent} secs={item.secs} />
              </BotBubble>
            );
          }}
          ListFooterComponent={
            sending ? (
              <BotBubble>
                <View style={styles.typing}>
                  <TypingDots />
                  <Text style={{ color: t.muted, fontSize: 13, flexShrink: 1 }}>
                    {elapsed}s{elapsed > 20 ? ' · el modelo local puede tardar hasta un minuto' : ''}
                  </Text>
                </View>
              </BotBubble>
            ) : undefined
          }
        />

        <Composer
          value={input}
          onChangeText={setInput}
          onSend={() => send(input)}
          canSend={isValidMessage(input) && !sending}
          invalid={tooLong}
          placeholder="Escribe tu pregunta…"
          multiline
          maxLength={MESSAGE_MAX + 50}
          editable={!sending}
        />
        {input.length > MESSAGE_MAX - 200 && (
          <Text style={[styles.counter, { color: tooLong ? t.bad : t.muted }]}>
            {input.length}/{MESSAGE_MAX}
          </Text>
        )}
      </KeyboardAvoidingView>
    </Backdrop>
  );
}

const styles = StyleSheet.create({
  list: { padding: 16, gap: 14, flexGrow: 1 },
  typing: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  retry: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', marginTop: 10, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  counter: { textAlign: 'right', paddingHorizontal: 20, paddingBottom: 6, fontSize: 12 },
});
