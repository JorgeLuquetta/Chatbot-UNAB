# App móvil — Chatbot UNAB (Expo / React Native)

App del estudiante que se ejecuta en **Expo Go** (Android e iOS), sin Android Studio. Reemplaza a la app
Kotlin de `android/` y usa exactamente los mismos endpoints del backend n8n.

| Pantalla | Qué hace | Requisito |
|---|---|---|
| Login | Código de estudiante + contraseña → token guardado cifrado (SecureStore) | Req. 1 |
| Chat | Preguntas al asistente; muestra la intención detectada, errores amigables y "Reintentar" | Req. 2 |
| Mi ruta | Cursos por semestre, estado, notas y % de avance; funciona **sin conexión** con la última copia | Req. 11 |
| Calendario | Próximos eventos; copia offline y **recordatorios locales 48 h antes** | Req. 12–13 |

> **Notificaciones:** Expo Go no permite notificaciones push remotas (FCM) en Android desde el SDK 53, así que la app
> programa recordatorios **locales** con los eventos del calendario, con la misma regla de 48 h del workflow
> `06_notificaciones_push`. Para push remoto real hace falta una *development build* (`npx eas-cli build`).

## Ejecutar con Expo Go

1. Instala **Expo Go** en el celular (Play Store / App Store).
2. En el PC (Node 20+):
   ```bash
   cd mobile
   npm install
   npx expo start            # muestra un código QR
   ```
   Si el celular no está en la misma red Wi-Fi que el PC usa: `npx expo start --tunnel`.
3. Escanea el QR con Expo Go (Android) o con la cámara (iOS).
4. Entra con `U00000001` / `Unab2026*` (o `U00000002`).

El backend por defecto es `http://20.221.211.215:9000/webhook` (`app.json → expo.extra.apiUrl`). Para otro servidor
copia `.env.example` a `.env` y cambia `EXPO_PUBLIC_API_URL` (luego `npx expo start --clear`).
Emulador Android con backend local: `EXPO_PUBLIC_API_URL=http://10.0.2.2:9000/webhook`.

## Pruebas y verificación

```bash
npm test            # lógica pura: validación de mensajes, errores, avance, calendario, recordatorios
npx tsc --noEmit    # tipos
npx expo-doctor     # dependencias compatibles con el SDK
```

## Estructura

```
app/                 rutas (Expo Router)
  _layout.tsx        proveedor de sesión + stack
  login.tsx
  (tabs)/            chat (index), ruta, calendario
src/
  auth.tsx           contexto de sesión
  lib/api.ts         cliente de los webhooks (timeout de 3 min para el LLM local)
  lib/errors.ts      mensajes de error fijos (sin detalles técnicos)
  lib/academic.ts    lógica pura (probada en logic.test.ts)
  lib/storage.ts     SecureStore (token) + caché offline por estudiante
  lib/reminders.ts   recordatorios locales del calendario
```

**Tiempo de respuesta:** el LLM corre gratis en CPU (Ollama `qwen2.5:1.5b`), así que una respuesta del chat tarda
de 30 a 90 s. La app muestra un contador mientras tanto.
