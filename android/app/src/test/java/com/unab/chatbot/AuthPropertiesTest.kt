package com.unab.chatbot

import com.unab.chatbot.auth.AuthErrorMapper
import com.unab.chatbot.auth.AuthRepository
import com.unab.chatbot.auth.AuthViewModel
import com.unab.chatbot.auth.LoginUiState
import com.unab.chatbot.auth.TokenManager
import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.collections.shouldBeIn
import io.kotest.matchers.longs.shouldBeGreaterThan
import io.kotest.matchers.shouldBe
import io.kotest.matchers.string.shouldNotContain
import io.kotest.matchers.types.shouldBeInstanceOf
import io.kotest.property.Arb
import io.kotest.property.PropTestConfig
import io.kotest.property.arbitrary.int
import io.kotest.property.arbitrary.string
import io.kotest.property.checkAll
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class AuthPropertiesTest : StringSpec({

    beforeTest { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    afterTest { Dispatchers.resetMain() }

    // Feature: chatbot-apoyo-academico, Property 1: Credenciales inválidas nunca exponen información sensible
    "Property 1: el mensaje de error no revela contraseña, tokens ni trazas" {
        checkAll(PropTestConfig(iterations = 100), Arb.string(1..30), Arb.string(1..40), Arb.int(400..599)) { user, pass, code ->
            val serverBody = """{"error":"token=abc123 password=$pass","trace":"at org.postgres"}"""
            val repo = object : AuthRepository {
                override suspend fun login(studentId: String, password: String) =
                    Result.failure<String>(HttpException(Response.error<Any>(code, serverBody.toResponseBody(null))))
                override suspend fun logout() = Unit
            }
            val vm = AuthViewModel(repo)
            vm.login(user.ifBlank { "U1" }, pass)
            val state = vm.state.value
            state.shouldBeInstanceOf<LoginUiState.Error>()
            val msg = state.message
            msg shouldBeIn setOf(AuthErrorMapper.INVALID_CREDENTIALS, AuthErrorMapper.UNREACHABLE, AuthErrorMapper.GENERIC)
            if (pass.trim().length >= 8) msg shouldNotContain pass
            listOf("token", "abc123", "trace", "postgres", "at org", code.toString()).forEach { msg shouldNotContain it }
        }
    }

    "credenciales inválidas muestran el mensaje genérico; sin red permite reintentar" {
        val http401 = HttpException(Response.error<Any>(401, "".toResponseBody(null)))
        AuthErrorMapper.message(http401) shouldBe AuthErrorMapper.INVALID_CREDENTIALS
        AuthErrorMapper.isRetryable(http401) shouldBe false
        AuthErrorMapper.message(IOException("unreachable host 10.0.0.1")) shouldBe AuthErrorMapper.UNREACHABLE
        AuthErrorMapper.isRetryable(IOException()) shouldBe true
    }

    "campos vacíos no llaman al backend" {
        var called = false
        val vm = AuthViewModel(object : AuthRepository {
            override suspend fun login(studentId: String, password: String): Result<String> { called = true; return Result.success("") }
            override suspend fun logout() = Unit
        })
        vm.login("", "")
        called shouldBe false
        (vm.state.value as LoginUiState.Error).message shouldBe AuthErrorMapper.MISSING_FIELDS
    }

    "parseExpiry entiende las fechas ISO que retorna n8n/PostgreSQL" {
        TokenManager.parseExpiry("2026-11-12T23:05:00.123Z", now = 0) shouldBe 1794524700123L
        TokenManager.parseExpiry("2026-11-12T18:05:00-05:00", now = 0) shouldBe 1794524700000L
        TokenManager.parseExpiry(null, now = 1000) shouldBeGreaterThan 1000L
    }
})
