// Noticias del día (educación, tecnología, ingeniería de sistemas) con imagen, fuente y fecha.
// Datos del scraper automático (n8n cada 6 h → MCP run_news_scraper) vía /webhook/news.
// Mismo diseño que web/noticias.html.
import Ionicons from '@expo/vector-icons/Ionicons';
import { useCallback, useEffect, useState } from 'react';
import { FlatList, Image, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Backdrop, ErrorState, FilterChip, Glass, Loading, PageTitle } from '../../src/components';
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
const ICON: Record<string, string> = { 'ingenieria-sistemas': '💻', tecnologia: '🤖', educacion: '🎓', general: '📰' };

function fmtDate(iso: string) {
  const d = new Date(`${iso}T12:00:00-05:00`);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });
}

function Picture({ item }: { item: NewsItem }) {
  const t = useTheme();
  const [failed, setFailed] = useState(false);
  return (
    <View style={[styles.pic, { backgroundColor: t.chip }]}>
      {item.image_url && !failed ? (
        <Image source={{ uri: item.image_url }} style={StyleSheet.absoluteFill} resizeMode="cover" onError={() => setFailed(true)} />
      ) : (
        <Text style={{ fontSize: 40 }}>{ICON[item.category] ?? '📰'}</Text>
      )}
    </View>
  );
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

  const header = (
    <View>
      <PageTitle
        title="Noticias de la UNAB"
        lead="Educación, tecnología e ingeniería de sistemas, tomadas del sitio de la UNAB cada 6 horas. Desde el chat puedes pedir: envíame las noticias de tecnología al correo."
      />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {CATEGORIES.map((c) => (
          <FilterChip key={c.key || 'all'} label={c.label} active={c.key === category} onPress={() => setCategory(c.key)} />
        ))}
      </ScrollView>
    </View>
  );

  let body: React.ReactNode;
  if (error && !items) body = <View style={styles.content}>{header}<ErrorState message={error} onRetry={() => load()} /></View>;
  else if (!items) body = <View style={[styles.content, { flex: 1 }]}>{header}<Loading /></View>;
  else {
    body = (
      <FlatList
        data={items}
        keyExtractor={(n) => n.source_url}
        ListHeaderComponent={header}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={t.brand} />}
        renderItem={({ item }) => (
          <Pressable onPress={() => Linking.openURL(item.source_url)} style={({ pressed }) => pressed && { transform: [{ translateY: -2 }] }}>
            <Glass style={styles.card}>
              <Picture item={item} />
              <View style={styles.body}>
                <View style={styles.meta}>
                  <Text style={[styles.cat, { color: t.brandDeep, borderColor: t.brandDeep }]}>{LABEL[item.category] ?? item.category}</Text>
                  <Text style={[styles.metaText, { color: t.muted }]} numberOfLines={1}>
                    {item.source_name} · {fmtDate(item.published_at)}
                  </Text>
                  <Ionicons name="open-outline" size={15} color={t.muted} />
                </View>
                <Text style={[styles.title, { color: t.text }]}>{item.title}</Text>
                {!!item.summary && item.summary !== item.title && (
                  <Text style={{ color: t.muted, fontSize: 14, lineHeight: 20 }} numberOfLines={3}>{item.summary}</Text>
                )}
              </View>
            </Glass>
          </Pressable>
        )}
        ListEmptyComponent={<Text style={{ color: t.muted, textAlign: 'center', marginTop: 24 }}>No hay noticias en esta categoría.</Text>}
      />
    );
  }

  return <Backdrop>{body}</Backdrop>;
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingTop: 20, paddingBottom: 32 },
  chips: { gap: 8, paddingBottom: 16 },
  card: { overflow: 'hidden', marginBottom: 16 },
  pic: { aspectRatio: 16 / 9, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  body: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 16, gap: 6 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cat: { fontSize: 12, fontWeight: '700', borderWidth: 1, borderRadius: 6, paddingHorizontal: 6 },
  metaText: { fontSize: 12, fontWeight: '700', flex: 1 },
  title: { fontSize: 16, fontWeight: '800', lineHeight: 21 },
});
