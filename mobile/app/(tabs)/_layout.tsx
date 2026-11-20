import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, Alert, View } from 'react-native';
import { useAuth } from '../../src/auth';
import { ChatHeader } from '../../src/chatui';
import { Aurora } from '../../src/components';
import { useTheme } from '../../src/theme';

export default function TabsLayout() {
  const t = useTheme();
  const { session, loading, signOut } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: t.bg }}>
        <Aurora />
        <ActivityIndicator color={t.brand} size="large" />
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
        // Mismo encabezado de la web: logo, "Chatbot UNAB" y la píldora con el estudiante
        header: () => <ChatHeader student={session} onChange={confirmLogout} />,
        tabBarActiveTintColor: t.brandDeep,
        tabBarInactiveTintColor: t.muted,
        tabBarLabelStyle: { fontWeight: '700', fontSize: 11 },
        tabBarStyle: { backgroundColor: t.glassStrong, borderTopColor: t.line, borderTopWidth: 1 },
        sceneStyle: { backgroundColor: t.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Chat',
          tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="ruta"
        options={{
          title: 'Mi ruta',
          tabBarIcon: ({ color, size }) => <Ionicons name="school-outline" size={size} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="plan"
        options={{
          title: 'Mi plan',
          tabBarIcon: ({ color, size }) => <Ionicons name="trending-up-outline" size={size} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="noticias"
        options={{
          title: 'Noticias',
          tabBarIcon: ({ color, size }) => <Ionicons name="newspaper-outline" size={size} color={String(color)} />,
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
