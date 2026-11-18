// Recordatorios locales de eventos del calendario (48 h antes).
// Expo Go no soporta notificaciones push remotas (FCM) en Android desde SDK 53, pero sí las locales.
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { reminderTimes, type CalendarEvent } from './academic';

const CHANNEL = 'calendario';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

async function ensurePermission(): Promise<boolean> {
  if (Platform.OS === 'android') {
    // En Android 13+ el diálogo de permiso no aparece hasta que exista un canal
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: 'Calendario académico',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#F5A800',
    });
  }
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === 'granted') return true;
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

/** Reprograma los recordatorios con la lista actual de eventos. Devuelve cuántos quedaron programados. */
export async function scheduleCalendarReminders(events: CalendarEvent[]): Promise<number> {
  try {
    if (Platform.OS === 'web' || !(await ensurePermission())) return 0;
    await Notifications.cancelAllScheduledNotificationsAsync();
    let count = 0;
    for (const { event, at } of reminderTimes(events).slice(0, 30)) {
      const content = {
        title: `Recordatorio UNAB: ${event.event_name}`,
        body: `${event.event_date}${event.description ? ' — ' + event.description : ''}`,
      };
      try {
        await Notifications.scheduleNotificationAsync({
          content,
          trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: at, channelId: CHANNEL },
        });
      } catch {
        // Sin permiso de alarma exacta (Android 12+ en Expo Go): intervalo relativo, también válido aquí
        const seconds = Math.max(60, Math.round((at.getTime() - Date.now()) / 1000));
        await Notifications.scheduleNotificationAsync({
          content,
          trigger: { type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL, seconds, channelId: CHANNEL },
        });
      }
      count++;
    }
    return count;
  } catch {
    return 0; // las notificaciones son opcionales: nunca rompen la pantalla
  }
}

export async function cancelReminders(): Promise<void> {
  try {
    await Notifications.cancelAllScheduledNotificationsAsync();
  } catch {
    // ignorar
  }
}
