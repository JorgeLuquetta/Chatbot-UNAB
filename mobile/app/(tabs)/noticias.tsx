// Noticias del día (educación, tecnología, ingeniería de sistemas) con fuente y fecha.
// Datos del scraper automático (n8n cada 6 h → MCP run_news_scraper) vía /webhook/news.
import Ionicons from '@expo/vector-icons/Ionicons';
import { useCallback, useEffect, useState } from 'react';
import { FlatList, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { ErrorState, Loading } from '../../src/components';
import { api, type NewsItem } from '../../src/lib/api';
import { chatErrorMessage } from '../../src/lib/errors';
import { useTheme } from '../../src/theme';

const CATEGORIES = [
  { key: '', label: 'Todas' },
  { key: 'ingenieria-sistemas', label: 'Ing. de Sistemas' },
  { key: 'tecnologia', label: 'Tecnología' },
  { key: 'educacion', label: 'Educación' },
];
const LABEL: Record<string, string> = {
  'ingenieria-sistemas': 'Ing. de Sistemas', tecnologia: 'Tecnología', educacion: 'Educación', general: 'General',
};

function fmtDate(iso: string) {
  const d = new Date(`${iso}T12:00:00-05:00`);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function NoticiasScreen() {
  const t = useTheme();
  const [category, setCategory] = useState('');
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (refresh = false) => {
    refresh ? setRefreshing(true) : setItems(null);
    try {
      const r = await api.news(category);
      setItems(r.news);
      setError(null);
    } catch (e) {
      setError(chatErrorMessage(e));
    } finally {
      setRefreshing(false);
    }
  }, [category]);

  useEffect(() => { load(); }, [load]);

  const chips = (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
      {CATEGORIES.map((c) => {
        const active = c.key === category;
        return (
          <Pressable key={c.key || 'all'} onPress={() => setCategory(c.key)}
            style={[styles.chip, { borderColor: t.purple, backgroundColor: active ? t.purple : 'transparent' }]}>
            <Text style={{ color: active ? '#fff' : t.purple, fontWeight: '700' }}>{c.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );

  if (error && !items) return <View style={{ flex: 1 }}>{chips}<ErrorState message={error} onRetry={() => load()} /></View>;
  if (!items) return <View style={{ flex: 1 }}>{chips}<Loading /></View>;

  return (
    <FlatList
      data={items}
      keyExtractor={(n) => n.source_url}
      ListHeaderComponent={chips}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={t.purple} />}
      renderItem={({ item }) => (
        <Pressable onPress={() => Linking.openURL(item.source_url)}
          style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
          <View style={styles.meta}>
            <Text style={[styles.badge, { color: t.purple, borderColor: t.purple }]}>{LABEL[item.category] ?? item.category}</Text>
            <Text style={{ color: t.muted, fontSize: 12, flex: 1 }} numberOfLines={1}>
              {item.source_name} · {fmtDate(item.published_at)}
            </Text>
            <Ionicons name="open-outline" size={16} color={t.muted} />
          </View>
          <Text style={[styles.title, { color: t.text }]}>{item.title}</Text>
          {item.summary && item.summary !== item.title && (
            <Text style={{ color: t.muted, fontSize: 13 }} numberOfLines={3}>{item.summary}</Text>
          )}
        </Pressable>
      )}
      ListEmptyComponent={<Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay noticias en esta categoría.</Text>}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32 },
  chips: { gap: 8, paddingHorizontal: 16, paddingVertical: 12 },
  chip: { borderWidth: 1.5, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 7 },
  card: { borderWidth: 1, borderRadius: 14, padding: 14, gap: 6, marginBottom: 10 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  badge: { fontSize: 11, fontWeight: '800', borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  title: { fontSize: 15, fontWeight: '700', lineHeight: 20 },
});
