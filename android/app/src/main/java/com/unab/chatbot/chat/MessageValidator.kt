package com.unab.chatbot.chat

/** Requirement 2.6 / Property 2: un mensaje se puede enviar si su longitud está en [1, 2000]. */
object MessageValidator {
    const val MIN_LENGTH = 1
    const val MAX_LENGTH = 2000

    fun isValid(text: String?): Boolean = text != null && text.length in MIN_LENGTH..MAX_LENGTH
}
