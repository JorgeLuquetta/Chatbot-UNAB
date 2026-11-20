// Piezas visuales compartidas, con la misma estética de la página web:
// fondo con manchas pastel, tarjetas de vidrio, logo "U" de colores y chips redondeados.
import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useRef } from 'react';
import {
  ActivityIndicator, Animated, Easing, Pressable, StyleSheet, Text, View, useWindowDimensions,
  type StyleProp, type ViewStyle,
} from 'react-native';
import { glassShadow, useTheme } from './theme';

// ---------- Fondo: manchas pastel difuminadas (como .aurora / .blobs de la web) ----------
// Sin librerías nativas extra (Expo Go): cada mancha son varios círculos concéntricos
// casi transparentes, que juntos dan un borde suave.
function Blob({ size, color, style }: { size: number; color: string; style: ViewStyle }) {
  const rings = 7;
  return (
    <View pointerEvents="none" style={[{ position: 'absolute', width: size, height: size }, style]}>
      {Array.from({ length: rings }, (_, i) => {
        const s = size * (1 - i / (rings + 1));
        return (
          <View
            key={i}
            style={{
              position: 'absolute', left: (size - s) / 2, top: (size - s) / 2, width: s, height: s,
              borderRadius: s / 2, backgroundColor: color, opacity: 0.16,
            }}
          />
        );
      })}
    </View>
  );
}

export function Aurora() {
  const t = useTheme();
  const { width, height } = useWindowDimensions();
  const big = Math.max(width, height) * 0.62;
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, { overflow: 'hidden' }]}>
      <Blob size={big} color={t.blobs[0]} style={{ top: -big * 0.35, left: -big * 0.3 }} />
      <Blob size={big * 0.9} color={t.blobs[1]} style={{ top: height * 0.18, right: -big * 0.45 }} />
      <Blob size={big * 0.95} color={t.blobs[2]} style={{ bottom: -big * 0.4, left: width * 0.05 }} />
      <Blob size={big * 0.7} color={t.blobs[3]} style={{ bottom: height * 0.12, right: -big * 0.3 }} />
    </View>
  );
}

// Contenedor de pantalla: color de fondo + manchas detrás del contenido
export function Backdrop({ children }: { children: React.ReactNode }) {
  const t = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <Aurora />
      {children}
    </View>
  );
}

// ---------- Tarjeta de vidrio (.glass) ----------
export function Glass({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const t = useTheme();
  return (
    <View style={[styles.glass, { backgroundColor: t.glass, borderColor: t.glassLine }, glassShadow(t), style]}>
      {children}
    </View>
  );
}

// ---------- Título de página (h1 + .lead de las páginas del portal) ----------
export function PageTitle({ title, lead }: { title: string; lead?: string }) {
  const t = useTheme();
  return (
    <View style={{ marginBottom: 16 }}>
      <Text style={[styles.h1, { color: t.text }]}>{title}</Text>
      {!!lead && <Text style={[styles.lead, { color: t.muted }]}>{lead}</Text>}
    </View>
  );
}

// ---------- Chip de filtro (.chip / aria-pressed) ----------
export function FilterChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={[styles.filterChip, { borderColor: t.brandDeep, backgroundColor: active ? t.brandDeep : 'transparent' }]}
    >
      <Text style={{ color: active ? t.bg : t.brandDeep, fontWeight: '700', fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}

// ---------- Logo "U" con colores pastel y punto verde de "en línea" ----------
export function Logo({ size = 42 }: { size?: number }) {
  const t = useTheme();
  const wobble = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(wobble, { toValue: 1, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(wobble, { toValue: 0, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [wobble]);
  const rotate = wobble.interpolate({ inputRange: [0, 1], outputRange: ['-4deg', '4deg'] });
  const half = size / 2;
  const r = size / 3;
  return (
    <Animated.View style={{ width: size, height: size, transform: [{ rotate }] }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <View style={[styles.logoTile, { width: size, height: size, borderRadius: r }]}>
        <View style={{ position: 'absolute', left: 0, top: 0, width: half, height: half, backgroundColor: t.pink }} />
        <View style={{ position: 'absolute', right: 0, top: 0, width: half, height: half, backgroundColor: t.lavender }} />
        <View style={{ position: 'absolute', right: 0, bottom: 0, width: half, height: half, backgroundColor: t.sky }} />
        <View style={{ position: 'absolute', left: 0, bottom: 0, width: half, height: half, backgroundColor: t.mint }} />
        <View style={{ position: 'absolute', left: size * 0.2, top: size * 0.2, width: size * 0.6, height: size * 0.6, borderRadius: size * 0.3, backgroundColor: t.lemon, opacity: 0.55 }} />
        <Text style={[styles.logoText, { color: t.onPastel, fontSize: size * 0.46 }]}>U</Text>
      </View>
      <View style={[styles.logoDot, { backgroundColor: t.online, borderColor: t.glassStrong }]} />
    </Animated.View>
  );
}

// ---------- Indicador "escribiendo" con tres puntos de colores ----------
export function TypingDots() {
  const t = useTheme();
  const values = useRef([0, 1, 2].map(() => new Animated.Value(0))).current;
  useEffect(() => {
    const anims = values.map((v, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 150),
          Animated.timing(v, { toValue: 1, duration: 300, easing: Easing.out(Easing.quad), useNativeDriver: true }),
          Animated.timing(v, { toValue: 0, duration: 300, easing: Easing.in(Easing.quad), useNativeDriver: true }),
          Animated.delay(500 - i * 150),
        ]),
      ),
    );
    anims.forEach((a) => a.start());
    return () => anims.forEach((a) => a.stop());
  }, [values]);
  const colors = [t.lavender, t.pink, t.sky];
  return (
    <View style={{ flexDirection: 'row', gap: 5, paddingVertical: 4 }} accessibilityLabel="Escribiendo…">
      {values.map((v, i) => (
        <Animated.View
          key={i}
          style={{
            width: 8, height: 8, borderRadius: 4, backgroundColor: colors[i],
            opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }),
            transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -7] }) }],
          }}
        />
      ))}
    </View>
  );
}

// ---------- Estados de carga, error y sin conexión ----------
export function Centered({ children }: { children: React.ReactNode }) {
  return <View style={styles.centered}>{children}</View>;
}

export function Loading() {
  const t = useTheme();
  return <Centered><ActivityIndicator size="large" color={t.brand} /></Centered>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useTheme();
  return (
    <Centered>
      <Glass style={styles.errorCard}>
        <Text style={{ fontSize: 36 }}>☁️</Text>
        <Text style={[styles.msg, { color: t.text }]}>{message}</Text>
        <Pressable onPress={onRetry} style={[styles.btn, { backgroundColor: t.lavender }]}>
          <Ionicons name="refresh" size={16} color={t.onPastel} />
          <Text style={[styles.btnText, { color: t.onPastel }]}>Reintentar</Text>
        </Pressable>
      </Glass>
    </Centered>
  );
}

export function OfflineBanner({ since }: { since: string }) {
  const t = useTheme();
  const when = new Date(since).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
  return (
    <View style={[styles.banner, { backgroundColor: t.warnBg, borderColor: t.warnLine }]}>
      <Ionicons name="cloud-offline-outline" size={16} color={t.warn} />
      <Text style={{ color: t.warn, flex: 1, fontSize: 13, fontWeight: '600' }}>Sin conexión · mostrando la copia guardada del {when}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  glass: { borderRadius: 20, borderWidth: 1 },
  h1: { fontSize: 28, fontWeight: '700', letterSpacing: 0.2 },
  lead: { fontSize: 14, lineHeight: 20, marginTop: 4 },
  filterChip: { borderWidth: 1.5, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 7 },
  logoTile: { overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  logoText: { fontWeight: '700' },
  logoDot: { position: 'absolute', right: -3, bottom: -3, width: 14, height: 14, borderRadius: 7, borderWidth: 3 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  errorCard: { alignItems: 'center', padding: 24, gap: 12, alignSelf: 'stretch' },
  msg: { textAlign: 'center', fontSize: 15, lineHeight: 21 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingHorizontal: 20, paddingVertical: 11 },
  btnText: { fontWeight: '800' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 14, borderWidth: 1, marginBottom: 12 },
});
