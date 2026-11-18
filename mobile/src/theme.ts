import { useColorScheme } from 'react-native';

// Colores institucionales de la presentación del curso: naranja y morado UNAB, azul noche.
const brand = { orange: '#F5A800', purple: '#8A00E6', navy: '#1C2A48' };

const light = {
  ...brand,
  bg: '#F6F7FB',
  card: '#FFFFFF',
  text: '#1C2A48',
  muted: '#5B6478',
  border: '#E2E5EE',
  botBubble: '#FFFFFF',
  userBubble: '#8A00E6',
  userText: '#FFFFFF',
  errorBg: '#FDECEC',
  errorText: '#B3261E',
  ok: '#1E7F4F',
  warn: '#B26A00',
  pending: '#6B7280',
  tabInactive: '#8A91A3',
};

const dark: typeof light = {
  ...brand,
  bg: '#0F1524',
  card: '#1A2236',
  text: '#ECEFF6',
  muted: '#A3ABBF',
  border: '#2A3450',
  botBubble: '#1A2236',
  userBubble: '#7B12CC',
  userText: '#FFFFFF',
  errorBg: '#3A1D22',
  errorText: '#FFB4AB',
  ok: '#6FD3A0',
  warn: '#F5C065',
  pending: '#9CA3AF',
  tabInactive: '#7C8499',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}
