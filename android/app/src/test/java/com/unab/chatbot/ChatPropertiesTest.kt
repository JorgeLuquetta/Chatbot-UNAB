package com.unab.chatbot

import com.unab.chatbot.chat.ChatViewModel
import com.unab.chatbot.chat.MessageValidator
import com.unab.chatbot.chat.model.Sender
import com.unab.chatbot.data.ChatRepository
import com.unab.chatbot.network.ErrorMapper
import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.collections.shouldContain
import io.kotest.matchers.shouldBe
import io.kotest.matchers.string.shouldNotContain
import io.kotest.property.Arb
import io.kotest.property.PropTestConfig
import io.kotest.property.arbitrary.choice
import io.kotest.property.arbitrary.int
import io.kotest.property.arbitrary.string
import io.kotest.property.checkAll
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException
import java.net.SocketTimeoutException

private val cfg = PropTestConfig(iterations = 100)

@OptIn(ExperimentalCoroutinesApi::class)
class ChatPropertiesTest : StringSpec({

    beforeTest { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    afterTest { Dispatchers.resetMain() }

    // Feature: chatbot-apoyo-academico, Property 2: Validación de longitud del mensaje de chat
    "Property 2: solo se permite enviar mensajes de 1 a 2000 caracteres" {
        checkAll(cfg, Arb.string(0..2600)) { text ->
            MessageValidator.isValid(text) shouldBe (text.length in 1..2000)
        }
    }

    "Property 2: el ViewModel bloquea mensajes fuera de rango" {
        checkAll(cfg, Arb.choice(Arb.string(2001..2400), Arb.string(0..0))) { text ->
            val vm = ChatViewModel(FakeChatRepository())
            val before = vm.state.value.messages.size
            vm.send(text) shouldBe false
            vm.state.value.messages.size shouldBe before
        }
    }

    // Feature: chatbot-apoyo-academico, Property 3: Mensajes enviados aparecen en la lista de chat
    "Property 3: un mensaje válido aparece en la lista inmediatamente" {
        checkAll(cfg, Arb.string(1..2000)) { text ->
            val pending = CompletableDeferred<Result<String>>() // el backend aún no responde
            val vm = ChatViewModel(FakeChatRepository { pending.await() })
            vm.send(text) shouldBe true
            val last = vm.state.value.messages.last()
            last.text shouldBe text
            last.sender shouldBe Sender.STUDENT
            vm.state.value.isLoading shouldBe true
            pending.complete(Result.success("ok"))
            vm.state.value.messages.last().sender shouldBe Sender.BOT
            vm.state.value.isLoading shouldBe false
        }
    }

    // Feature: chatbot-apoyo-academico, Property 4: Errores del backend no exponen detalles internos
    "Property 4: los errores mostrados nunca contienen detalles técnicos" {
        val internal = listOf("conversation_memory", "student_courses", "Traceback", "at com.", "Exception",
            "sess_", "mcp-server", "guardrails:8080", "SELECT", "stack")
        checkAll(cfg, Arb.int(100..599), Arb.string(0..200)) { code, body ->
            val errors = listOf<Throwable>(
                HttpException(Response.error<Any>(code.coerceAtLeast(400), body.toResponseBody(null))),
                IOException(body), SocketTimeoutException(body), IllegalStateException("conversation_memory $body"),
            )
            for (e in errors) {
                val msg = ErrorMapper.friendlyMessage(e)
                ErrorMapper.ALL_MESSAGES shouldContain msg
                msg shouldNotContain code.toString()
                internal.forEach { msg shouldNotContain it }
                if (body.trim().length >= 12) msg shouldNotContain body
            }
        }
    }

    "Property 4: un error del backend se muestra como mensaje amigable en el chat" {
        val vm = ChatViewModel(FakeChatRepository {
            Result.failure(HttpException(Response.error<Any>(500, "relation \"student_courses\" error".toResponseBody(null))))
        })
        vm.send("¿Cuándo son los parciales?")
        val last = vm.state.value.messages.last()
        last.sender shouldBe Sender.ERROR
        last.text shouldBe ErrorMapper.UNAVAILABLE
    }
})

class FakeChatRepository(private val reply: suspend (String) -> Result<String> = { Result.success("respuesta") }) :
    ChatRepository {
    override suspend fun send(message: String): Result<String> = reply(message)
}
