package com.unab.chatbot.chat.model

enum class Sender { STUDENT, BOT, ERROR }

data class Message(
    val id: Long,
    val text: String,
    val sender: Sender,
    val timestamp: Long = System.currentTimeMillis(),
)
