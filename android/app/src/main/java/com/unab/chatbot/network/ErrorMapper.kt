package com.unab.chatbot.network

import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

/**
 * Traduce cualquier error técnico a un mensaje amigable de un conjunto FIJO.
 * Nunca incluye códigos HTTP, trazas, nombres de tablas ni identificadores internos
 * (Requirement 2.5 / Property 4).
 */
object ErrorMapper {
    const val CONNECTIVITY = "No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo."
    const val TIMEOUT = "El asistente está tardando más de lo normal. Inténtalo de nuevo en un momento."
    const val SESSION = "Tu sesión expiró. Inicia sesión de nuevo."
    const val REJECTED = "No pude procesar tu mensaje. Reformula tu pregunta sobre temas académicos de la UNAB."
    const val UNAVAILABLE = "El servicio no está disponible en este momento. Inténtalo más tarde."
    const val GENERIC = "Ocurrió un problema inesperado. Inténtalo de nuevo."

    val ALL_MESSAGES = setOf(CONNECTIVITY, TIMEOUT, SESSION, REJECTED, UNAVAILABLE, GENERIC)

    fun fromHttpCode(code: Int): String = when (code) {
        401, 403 -> SESSION
        400, 413, 422 -> REJECTED
        408, 504 -> TIMEOUT
        in 500..599 -> UNAVAILABLE
        else -> GENERIC
    }

    fun friendlyMessage(error: Throwable?): String = when (error) {
        is HttpException -> fromHttpCode(error.code())
        is SocketTimeoutException -> TIMEOUT
        is IOException -> CONNECTIVITY
        else -> GENERIC
    }
}
