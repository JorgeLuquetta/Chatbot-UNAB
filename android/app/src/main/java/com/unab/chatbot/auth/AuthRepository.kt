package com.unab.chatbot.auth

import com.unab.chatbot.network.ChatbotApi
import com.unab.chatbot.network.dto.LoginRequest

interface AuthRepository {
    suspend fun login(studentId: String, password: String): Result<String>
    suspend fun logout()
}

class DefaultAuthRepository(
    private val api: ChatbotApi,
    private val tokens: TokenStore,
    /** Limpia la cache local (Room) para no mostrar datos de otra sesión. */
    private val clearLocalData: suspend () -> Unit = {},
) : AuthRepository {

    override suspend fun login(studentId: String, password: String): Result<String> = runCatching {
        val r = api.login(LoginRequest(studentId.trim(), password))
        val token = r.token
        val session = r.sessionId
        if (token.isNullOrBlank() || session.isNullOrBlank()) {
            throw IllegalStateException("respuesta de login incompleta")
        }
        clearLocalData() // la cache puede ser de otro estudiante
        tokens.save(token, session, r.expiresAt, r.fullName)
        r.fullName.orEmpty()
    }

    override suspend fun logout() {
        tokens.clear()
        clearLocalData()
    }
}
