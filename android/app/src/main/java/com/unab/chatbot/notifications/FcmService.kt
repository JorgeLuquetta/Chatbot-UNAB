package com.unab.chatbot.notifications

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.unab.chatbot.MainActivity
import com.unab.chatbot.R
import com.unab.chatbot.ServiceLocator
import com.unab.chatbot.network.dto.RegisterDeviceRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Recibe los mensajes FCM "calendar_event" enviados por el workflow n8n de notificaciones. */
class FcmService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        DeviceRegistrar.register(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val name = data["event_name"] ?: message.notification?.title ?: return
        val date = data["event_date"].orEmpty()
        NotificationHelper.showEvent(
            context = applicationContext,
            eventKey = data["event_key"] ?: "$name|$date",
            title = data["title"] ?: getString(R.string.notification_title),
            body = data["body"] ?: listOf(name, date).filter { it.isNotBlank() }.joinToString(" — "),
        )
    }
}

object NotificationHelper {
    const val EXTRA_OPEN_SCREEN = "open_screen"
    const val EXTRA_EVENT_KEY = "event_key"
    const val SCREEN_CALENDAR = "calendario"

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                context.getString(R.string.notification_channel_id),
                context.getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = context.getString(R.string.notification_channel_description) }
            context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    /** Requirement 14.4: si el usuario desactivó las notificaciones en el SO, no se intenta mostrar nada. */
    fun canNotify(context: Context): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    }

    @Suppress("MissingPermission") // verificado en canNotify()
    fun showEvent(context: Context, eventKey: String, title: String, body: String) {
        if (!canNotify(context)) return
        ensureChannel(context)
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(EXTRA_OPEN_SCREEN, SCREEN_CALENDAR)
            putExtra(EXTRA_EVENT_KEY, eventKey)
        }
        val pending = PendingIntent.getActivity(
            context, eventKey.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(context, context.getString(R.string.notification_channel_id))
            .setSmallIcon(R.drawable.ic_calendar)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        NotificationManagerCompat.from(context).notify(eventKey.hashCode(), notification)
    }
}

/** Registra el token FCM del dispositivo en el backend (tabla device_tokens). */
object DeviceRegistrar {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun isFirebaseConfigured(context: Context): Boolean = FirebaseApp.getApps(context).isNotEmpty()

    fun registerCurrentToken(context: Context) {
        if (!isFirebaseConfigured(context)) return
        FirebaseMessaging.getInstance().token.addOnSuccessListener { register(it) }
    }

    fun register(token: String) {
        if (!ServiceLocator.isInitialized || !ServiceLocator.tokenStore.isLoggedIn()) return
        scope.launch {
            runCatching { ServiceLocator.api.registerDevice(RegisterDeviceRequest(token)) }
        }
    }
}
