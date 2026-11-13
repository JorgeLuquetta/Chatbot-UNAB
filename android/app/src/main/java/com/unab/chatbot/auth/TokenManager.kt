package com.unab.chatbot.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.time.Instant
import java.time.OffsetDateTime

/** Abstracción del almacén de sesión (permite fakes en tests). */
interface TokenStore {
    fun token(): String?
    fun sessionId(): String?
    fun fullName(): String?
    fun expiresAtMillis(): Long
    fun save(token: String, sessionId: String, expiresAtIso: String?, fullName: String?)
    fun clear()

    fun isLoggedIn(nowMillis: Long = System.currentTimeMillis()): Boolean =
        !token().isNullOrBlank() && nowMillis < expiresAtMillis()
}

/** Guarda el JWT/token de sesión cifrado con EncryptedSharedPreferences (Requirement 1.3). */
class TokenManager(context: Context) : TokenStore {

    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "unab_session",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    override fun token(): String? = prefs.getString(KEY_TOKEN, null)
    override fun sessionId(): String? = prefs.getString(KEY_SESSION, null)
    override fun fullName(): String? = prefs.getString(KEY_NAME, null)
    override fun expiresAtMillis(): Long = prefs.getLong(KEY_EXPIRES, 0L)

    override fun save(token: String, sessionId: String, expiresAtIso: String?, fullName: String?) {
        prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_SESSION, sessionId)
            .putString(KEY_NAME, fullName)
            .putLong(KEY_EXPIRES, parseExpiry(expiresAtIso))
            .apply()
    }

    override fun clear() {
        prefs.edit().clear().apply()
    }

    companion object {
        private const val KEY_TOKEN = "token"
        private const val KEY_SESSION = "session_id"
        private const val KEY_NAME = "full_name"
        private const val KEY_EXPIRES = "expires_at"
        private const val DEFAULT_TTL_MS = 8L * 60 * 60 * 1000

        fun parseExpiry(iso: String?, now: Long = System.currentTimeMillis()): Long {
            if (iso.isNullOrBlank()) return now + DEFAULT_TTL_MS
            return runCatching { Instant.parse(iso).toEpochMilli() }
                .recoverCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
                .recoverCatching { OffsetDateTime.parse(iso.replace(' ', 'T')).toInstant().toEpochMilli() }
                .getOrDefault(now + DEFAULT_TTL_MS)
        }
    }
}
