// Pantalla inicial (sin login): el asistente saluda, pide el ID de estudiante y lo busca en la BD.
import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect } from 'expo-router';
import { useRef, useState, type ComponentRef } from 'react';
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../src/auth';
import { AuthErrors, authErrorMessage } from '../src/lib/errors';
import { useTheme } from '../src/theme';

const ID_RE = /\b(U\d{8})\b/i;
type Msg = { id: number; role: 'bot' | 'user' | 'warn'; text: string };

const GREETING =
  '¡Hola! 👋 Soy el asistente académico de la UNAB.\n\n' +
  'Puedo ayudarte con el reglamento estudiantil, tus materias y tu avance, las noticias de la universidad ' +
  'y el calendario académico.\n\nPara empezar, escribe tu ID de estudiante (por ejemplo, U00000001).';

export default function IdentifyScreen() {
  const t = useTheme();
  const { session, loading, signIn } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([{ id: 0, role: 'bot', text: GREETING }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const nextId = useRef(1);

  if (!loading && session) return <Redirect href="/" />;

  const push = (role: Msg['role'], text: string) =>
    setMessages((m) => [...m, { id: nextId.current++, role, text }]);

  const submit = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    push('user', text);
    const m = text.match(ID_RE);
    if (!m) {
      push('bot', 'Antes de responder necesito saber quién eres. ' + AuthErrors.MISSING_FIELDS);
      return;
    }
    setBusy(true);
    try {
      await signIn(m[1]); // al guardar la sesión, el Redirect lleva al chat con la bienvenida
    } catch (e) {
      push('warn', authErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={[styles.flex, { backgroundColor: t.bg }]}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={[styles.hero, { backgroundColor: t.orange }]}>
          <View style={[styles.heroAccent, { backgroundColor: t.purple }]} />
          <Text style={styles.kicker}>UNIVERSIDAD AUTÓNOMA DE BUCARAMANGA</Text>
          <Text style={styles.title}>Asistente académico</Text>
        </View>

        <ScrollView
          ref={scroll}
          style={styles.flex}
          contentContainerStyle={styles.list}
          onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
        >
          {messages.map((msg) => (
            <View
              key={msg.id}
              style={[
                styles.bubble,
                msg.role === 'user'
                  ? [styles.right, { backgroundColor: t.userBubble }]
                  : [styles.left, { backgroundColor: msg.role === 'warn' ? t.errorBg : t.botBubble, borderColor: t.border, borderWidth: msg.role === 'warn' ? 0 : 1 }],
              ]}
            >
              <Text style={{ color: msg.role === 'user' ? t.userText : msg.role === 'warn' ? t.errorText : t.text, fontSize: 15, lineHeight: 21 }}>
                {msg.text}
              </Text>
            </View>
          ))}
          {busy && (
            <View style={[styles.bubble, styles.left, styles.typing, { backgroundColor: t.botBubble, borderColor: t.border }]}>
              <ActivityIndicator color={t.purple} />
              <Text style={{ color: t.muted }}>Buscando tu ID…</Text>
            </View>
          )}
        </ScrollView>

        <View style={[styles.composer, { backgroundColor: t.card, borderTopColor: t.border }]}>
          <TextInput
            style={[styles.input, { color: t.text, backgroundColor: t.bg, borderColor: t.border }]}
            value={input}
            onChangeText={setInput}
            placeholder="Escribe tu ID de estudiante…"
            placeholderTextColor={t.tabInactive}
            autoCapitalize="characters"
            autoCorrect={false}
            editable={!busy}
            returnKeyType="send"
            onSubmitEditing={submit}
            maxLength={200}
          />
          <Pressable
            onPress={submit}
            disabled={busy || !input.trim()}
            style={[styles.send, { backgroundColor: !busy && input.trim() ? t.purple : t.tabInactive }]}
            accessibilityLabel="Enviar"
          >
            <Ionicons name="send" size={18} color="#fff" />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  hero: { paddingHorizontal: 24, paddingTop: 28, paddingBottom: 22, overflow: 'hidden' },
  heroAccent: { position: 'absolute', right: -60, top: -60, width: 180, height: 180, borderRadius: 90, opacity: 0.9 },
  kicker: { color: '#1C2A48', fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
  title: { color: '#FFFFFF', fontSize: 26, fontWeight: '800', marginTop: 6 },
  list: { padding: 16, gap: 10, flexGrow: 1 },
  bubble: { maxWidth: '85%', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10 },
  right: { alignSelf: 'flex-end', borderBottomRightRadius: 4 },
  left: { alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  typing: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', padding: 10, gap: 8, borderTopWidth: 1 },
  input: { flex: 1, borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15 },
  send: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});
