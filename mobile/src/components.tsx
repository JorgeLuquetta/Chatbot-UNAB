import Ionicons from '@expo/vector-icons/Ionicons';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from './theme';

export function Centered({ children }: { children: React.ReactNode }) {
  return <View style={styles.centered}>{children}</View>;
}

export function Loading() {
  const t = useTheme();
  return <Centered><ActivityIndicator size="large" color={t.purple} /></Centered>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useTheme();
  return (
    <Centered>
      <Ionicons name="cloud-offline-outline" size={40} color={t.muted} />
      <Text style={[styles.msg, { color: t.text }]}>{message}</Text>
      <Pressable onPress={onRetry} style={[styles.btn, { backgroundColor: t.purple }]}>
        <Text style={styles.btnText}>Reintentar</Text>
      </Pressable>
    </Centered>
  );
}

export function OfflineBanner({ since }: { since: string }) {
  const t = useTheme();
  const when = new Date(since).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
  return (
    <View style={[styles.banner, { backgroundColor: t.errorBg }]}>
      <Ionicons name="cloud-offline-outline" size={16} color={t.errorText} />
      <Text style={{ color: t.errorText, flex: 1, fontSize: 13 }}>Sin conexión · mostrando la copia guardada del {when}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  msg: { textAlign: 'center', fontSize: 15 },
  btn: { borderRadius: 12, paddingHorizontal: 20, paddingVertical: 12 },
  btnText: { color: '#fff', fontWeight: '700' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, marginBottom: 12 },
});
