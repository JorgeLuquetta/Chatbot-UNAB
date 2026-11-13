package com.unab.chatbot.network

import com.unab.chatbot.BuildConfig
import com.unab.chatbot.auth.TokenStore
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/** Adjunta "Authorization: Bearer <token>" a cada petición cuando hay sesión. */
class AuthInterceptor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokens.token()
        val request = if (token.isNullOrBlank()) chain.request()
        else chain.request().newBuilder().header("Authorization", "Bearer $token").build()
        return chain.proceed(request)
    }
}

/** Ante un 401 (fuera del login) limpia el token y avisa a la UI para volver al login. */
class ResponseInterceptor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        val isLogin = chain.request().url.encodedPath.endsWith("/login")
        if (response.code == 401 && !isLogin) {
            tokens.clear()
            SessionEvents.notifyExpired()
        }
        return response
    }
}

object ApiClient {
    fun create(tokens: TokenStore, baseUrl: String = BuildConfig.API_BASE_URL): ChatbotApi {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokens))
            .addInterceptor(ResponseInterceptor(tokens))
            .addInterceptor(logging)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
        return Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ChatbotApi::class.java)
    }
}
