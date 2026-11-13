package com.unab.chatbot.chat.model

import com.google.gson.annotations.SerializedName

/** Cuerpo de POST /webhook/chat. El backend toma el session_id real del token Bearer. */
data class ChatRequest(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("message") val message: String,
)
