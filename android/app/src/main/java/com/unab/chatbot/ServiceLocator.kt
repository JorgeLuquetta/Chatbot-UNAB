package com.unab.chatbot

import android.app.Application
import android.content.Context
import com.unab.chatbot.auth.AuthRepository
import com.unab.chatbot.auth.DefaultAuthRepository
import com.unab.chatbot.auth.TokenManager
import com.unab.chatbot.auth.TokenStore
import com.unab.chatbot.data.AcademicRepository
import com.unab.chatbot.data.AppDatabase
import com.unab.chatbot.data.CalendarRepository
import com.unab.chatbot.data.ChatRepository
import com.unab.chatbot.data.DefaultAcademicRepository
import com.unab.chatbot.data.DefaultCalendarRepository
import com.unab.chatbot.data.DefaultChatRepository
import com.unab.chatbot.network.ApiClient
import com.unab.chatbot.network.ChatbotApi
import com.unab.chatbot.notifications.NotificationHelper

/** Inyección de dependencias manual (suficiente para el tamaño del proyecto). */
object ServiceLocator {
    lateinit var tokenStore: TokenStore
    lateinit var api: ChatbotApi
    lateinit var database: AppDatabase
    lateinit var authRepository: AuthRepository
    lateinit var chatRepository: ChatRepository
    lateinit var academicRepository: AcademicRepository
    lateinit var calendarRepository: CalendarRepository

    val isInitialized: Boolean get() = ::api.isInitialized

    fun init(context: Context) {
        if (isInitialized) return
        tokenStore = TokenManager(context)
        api = ApiClient.create(tokenStore)
        database = AppDatabase.build(context)
        authRepository = DefaultAuthRepository(api, tokenStore) {
            database.courseDao().clear()
            database.calendarDao().clear()
        }
        chatRepository = DefaultChatRepository(api, tokenStore)
        academicRepository = DefaultAcademicRepository(api, database.courseDao())
        calendarRepository = DefaultCalendarRepository(api, database.calendarDao())
    }
}

class ChatbotApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ServiceLocator.init(this)
        NotificationHelper.ensureChannel(this)
    }
}
