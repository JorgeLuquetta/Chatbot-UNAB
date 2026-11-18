import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, Alert, Pressable, View } from 'react-native';
import { useAuth } from '../../src/auth';
import { useTheme } from '../../src/theme';

export default function TabsLayout() {
  const t = useTheme();
  const { session, loading, signOut } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: t.bg }}>
        <ActivityIndicator color={t.purple} size="large" />
      </View>
    );
  }
  if (!session) return <Redirect href="/login" />;

  const confirmLogout = () =>
    Alert.alert('Cambiar estudiante', '¿Quieres ingresar con otro ID de estudiante?', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Cambiar', style: 'destructive', onPress: signOut },
    ]);

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: t.orange },
        headerTintColor: '#1C2A48',
        headerTitleStyle: { fontWeight: '800' },
        tabBarActiveTintColor: t.purple,
        tabBarInactiveTintColor: t.tabInactive,
        tabBarStyle: { backgroundColor: t.card, borderTopColor: t.border },
        sceneStyle: { backgroundColor: t.bg },
        headerRight: () => (
          <Pressable onPress={confirmLogout} hitSlop={12} style={{ marginRight: 16 }} accessibilityLabel="Cambiar estudiante">
            <Ionicons name="log-out-outline" size={24} color="#1C2A48" />
          </Pressable>
        ),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Asistente UNAB',
          tabBarLabel: 'Chat',
          tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="ruta"
        options={{
          title: 'Ruta académica',
          tabBarLabel: 'Mi ruta',
          tabBarIcon: ({ color, size }) => <Ionicons name="school-outline" size={size} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="calendario"
        options={{
          title: 'Calendario',
          tabBarIcon: ({ color, size }) => <Ionicons name="calendar-outline" size={size} color={String(color)} />,
        }}
      />
    </Tabs>
  );
}
