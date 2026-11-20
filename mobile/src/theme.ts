import { useColorScheme } from 'react-native';

// Misma paleta pastel de la página web (web/index.html y web/comun.css): fondo lavanda,
// manchas de colores suaves, tarjetas "de vidrio" y acentos morados.
const pastel = {
  lavender: '#b9a6f5',
  pink: '#ffb3cf',
  mint: '#9fe3c1',
  sky: '#9fd3ff',
  peach: '#ffc7a8',
  lemon: '#ffe58f',
  onPastel: '#2e2645', // texto sobre colores pastel (siempre oscuro)
  online: '#5fd39a',
};

const light = {
  ...pastel,
  dark: false,
  bg: '#f6f1ff',
  blobs: ['#ffd6e8', '#c9e8ff', '#d4f5e4', '#fff1c9'],
  glass: 'rgba(255,255,255,0.72)',
  glassStrong: 'rgba(255,255,255,0.88)',
  glassLine: 'rgba(255,255,255,0.9)',
  text: '#2e2645',
  muted: '#6f6789',
  line: '#e7defa',
  brand: '#8a6cf0',
  brandDeep: '#6a4fd6',
  chip: '#ece5ff',
  meBubble: '#c9b8ff',
  botBubble: 'rgba(255,255,255,0.94)',
  // Sugerencias del chat (igual que .chips button en la web)
  suggestion: ['#e4dbff', '#d3f4e3', '#ffdbe9', '#d6ebff'],
  warn: '#8a3b12',
  warnBg: '#ffe4d4',
  warnLine: '#ffc7a8',
  ok: '#1f7a52',
  caution: '#a15c00',
  bad: '#b3261e',
  pending: '#8d86a6',
  shadow: '#6e50c8',
};

const dark: typeof light = {
  ...pastel,
  dark: true,
  bg: '#17132a',
  blobs: ['#5a2f55', '#24406a', '#1f4f45', '#5a4a24'],
  glass: 'rgba(34,28,58,0.78)',
  glassStrong: 'rgba(40,33,68,0.92)',
  glassLine: 'rgba(255,255,255,0.08)',
  text: '#efeaff',
  muted: '#b3aacf',
  line: '#3a3160',
  brand: '#b9a6f5',
  brandDeep: '#d4c8ff',
  chip: '#2e2652',
  meBubble: '#b9a6f5',
  botBubble: 'rgba(52,44,86,0.94)',
  suggestion: ['#e4dbff', '#d3f4e3', '#ffdbe9', '#d6ebff'],
  warn: '#ffd2b8',
  warnBg: '#4a2d24',
  warnLine: '#7a4632',
  ok: '#8ff0c0',
  caution: '#f5c065',
  bad: '#ffb4ab',
  pending: '#8d86a6',
  shadow: '#000000',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}

// Sombra morada suave de las tarjetas de la web (--shadow)
export function glassShadow(t: Theme) {
  return {
    shadowColor: t.shadow,
    shadowOpacity: t.dark ? 0.5 : 0.22,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    // Sin elevation en Android: con fondos translúcidos deja una sombra gris visible a través del vidrio
  };
}

export function bubbleShadow(t: Theme) {
  return {
    shadowColor: t.shadow,
    shadowOpacity: t.dark ? 0.5 : 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  };
}
