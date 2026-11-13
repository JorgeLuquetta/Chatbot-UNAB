package com.unab.chatbot.auth

import retrofit2.HttpException
import java.io.IOException

/**
 * Mensajes de error de autenticación. Son constantes: nunca incluyen la contraseña,
 * el usuario, tokens ni detalles del servidor (Requirement 1.2 / Property 1).
 */
object AuthErrorMapper {
    const val INVALID_CREDENTIALS = "Usuario o contraseña incorrectos."
    const val MISSING_FIELDS = "Ingresa tu código de estudiante y tu contraseña."
    const val UNREACHABLE = "No fue posible conectar con el servicio de autenticación. Revisa tu conexión e inténtalo de nuevo."
    const val GENERIC = "No fue posible iniciar sesión. Inténtalo de nuevo."

    fun message(error: Throwable?): String = when (error) {
        is HttpException -> if (error.code() in 400..499) INVALID_CREDENTIALS else UNREACHABLE
        is IOException -> UNREACHABLE
        else -> GENERIC
    }

    /** true si el error permite reintentar (Requirement 1.5). */
    fun isRetryable(error: Throwable?): Boolean =
        error is IOException || (error is HttpException && error.code() >= 500)
}
