package com.unab.chatbot.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unab.chatbot.chat.model.Message
import com.unab.chatbot.chat.model.Sender
import com.unab.chatbot.data.ChatRepository
import com.unab.chatbot.network.ErrorMapper
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicLong

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val isLoading: Boolean = false,
)

class ChatViewModel(private val repository: ChatRepository) : ViewModel() {

    private val ids = AtomicLong(0)
    private val _state = MutableStateFlow(ChatUiState(messages = listOf(welcome())))
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    /**
     * Agrega el mensaje del estudiante a la lista de inmediato (Property 3) y lo envía al backend.
     * Retorna false si el mensaje no cumple la longitud permitida (Property 2).
     */
    fun send(text: String): Boolean {
        if (!MessageValidator.isValid(text)) return false
        val userMsg = Message(ids.incrementAndGet(), text, Sender.STUDENT)
        _state.update { it.copy(messages = it.messages + userMsg, isLoading = true) }
        viewModelScope.launch {
            val reply = repository.send(text).fold(
                onSuccess = { Message(ids.incrementAndGet(), it, Sender.BOT) },
                onFailure = { Message(ids.incrementAndGet(), ErrorMapper.friendlyMessage(it), Sender.ERROR) },
            )
            _state.update { it.copy(messages = it.messages + reply, isLoading = false) }
        }
        return true
    }

    private fun welcome() = Message(
        ids.incrementAndGet(),
        "¡Hola! Soy el asistente académico de la UNAB. Pregúntame por tu plan de estudios, el calendario académico, " +
            "tus cursos o las noticias de la universidad.",
        Sender.BOT,
    )
}
