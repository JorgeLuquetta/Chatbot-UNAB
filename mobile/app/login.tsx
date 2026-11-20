// Pantalla inicial (sin login): el asistente saluda, pide el ID de estudiante y lo busca en la BD.
// Mismo diseño que la página web antes de identificarse.
import { Redirect } from 'expo-router';
import { useRef, useState, type ComponentRef } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../src/auth';
import { BotBubble, ChatHeader, Composer, MeBubble, RichText, Topics } from '../src/chatui';
import { Backdrop, TypingDots } from '../src/components';
import { AuthErrors, authErrorMessage } from '../src/lib/errors';
import { useTheme } from '../src/theme';

const ID_RE = /\b(U\d{8})\b/i;
type Msg = { id: number; role: 'bot' | 'user' | 'warn'; text: string };

const GREETING =
  '¡Hola! 👋 Soy el asistente académico de la UNAB.\n\n' +
  'Puedo ayudarte con tu matrícula (qué materias inscribir), tu estado académico, tu proyección de grado, ' +
  'recomendaciones para tener éxito, el reglamento y los requisitos de grado, el calendario académico y las ' +
  'noticias de educación y tecnología.\n\nPara empezar, escribe tu ID de estudiante (por ejemplo, U00000001).';

export default function IdentifyScreen() {
  const t = useTheme();
  const insets = useSafeAreaInsets();
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
    <Backdrop>
      <ChatHeader />
      <Topics />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView
          ref={scroll}
          style={styles.flex}
          contentContainerStyle={styles.list}
          onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((msg) =>
            msg.role === 'user' ? (
              <MeBubble key={msg.id} text={msg.text} />
            ) : (
              <BotBubble key={msg.id} warn={msg.role === 'warn'}>
                <RichText text={msg.text} color={msg.role === 'warn' ? t.warn : t.text} />
              </BotBubble>
            ),
          )}
          {busy && (
            <BotBubble>
              <View style={styles.typing}>
                <TypingDots />
                <Text style={{ color: t.muted, fontSize: 13 }}>Buscando tu ID…</Text>
              </View>
            </BotBubble>
          )}
        </ScrollView>

        <View style={{ paddingBottom: Math.max(insets.bottom, 6) }}>
          <Composer
            value={input}
            onChangeText={setInput}
            onSend={submit}
            canSend={!busy && !!input.trim()}
            placeholder="Escribe tu ID de estudiante…"
            autoCapitalize="characters"
            autoCorrect={false}
            editable={!busy}
            returnKeyType="send"
            onSubmitEditing={submit}
            maxLength={200}
          />
        </View>
      </KeyboardAvoidingView>
    </Backdrop>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  list: { padding: 16, gap: 14, flexGrow: 1 },
  typing: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});
