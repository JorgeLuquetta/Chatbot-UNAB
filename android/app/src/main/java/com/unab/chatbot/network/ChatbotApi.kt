package com.unab.chatbot.network

import com.unab.chatbot.chat.model.ChatRequest
import com.unab.chatbot.network.dto.CalendarResponse
import com.unab.chatbot.network.dto.ChatResponse
import com.unab.chatbot.network.dto.CoursesResponse
import com.unab.chatbot.network.dto.LoginRequest
import com.unab.chatbot.network.dto.LoginResponse
import com.unab.chatbot.network.dto.RegisterDeviceRequest
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface ChatbotApi {
    @POST("webhook/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @POST("webhook/chat")
    suspend fun chat(@Body body: ChatRequest): ChatResponse

    @GET("webhook/academic-route")
    suspend fun academicRoute(): CoursesResponse

    @GET("webhook/calendar")
    suspend fun calendar(): CalendarResponse

    @POST("webhook/register-device")
    suspend fun registerDevice(@Body body: RegisterDeviceRequest)
}
