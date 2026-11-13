package com.unab.chatbot.data

import com.unab.chatbot.academic.CalendarEvent
import com.unab.chatbot.academic.Course
import com.unab.chatbot.academic.CourseStatus
import com.unab.chatbot.auth.TokenStore
import com.unab.chatbot.chat.model.ChatRequest
import com.unab.chatbot.network.ChatbotApi
import retrofit2.HttpException
import java.io.IOException
import kotlin.coroutines.cancellation.CancellationException

/** Resultado de una carga con soporte offline (Requirements 12.4 y 13.4). */
sealed interface Loaded<out T> {
    data class Fresh<T>(val data: T) : Loaded<T>
    data class Cached<T>(val data: T, val lastFetchedAt: Long) : Loaded<T>
    data class Failed(val error: Throwable) : Loaded<Nothing>
}

interface ChatRepository {
    suspend fun send(message: String): Result<String>
}

class DefaultChatRepository(private val api: ChatbotApi, private val tokens: TokenStore) : ChatRepository {
    override suspend fun send(message: String): Result<String> = runCatching {
        val r = api.chat(ChatRequest(sessionId = tokens.sessionId().orEmpty(), message = message))
        r.response?.takeIf { it.isNotBlank() } ?: throw IOException("respuesta vacía")
    }
}

interface AcademicRepository {
    suspend fun courses(): Loaded<List<Course>>
}

class DefaultAcademicRepository(
    private val api: ChatbotApi,
    private val dao: CourseDao,
    private val clock: () -> Long = System::currentTimeMillis,
) : AcademicRepository {
    override suspend fun courses(): Loaded<List<Course>> = try {
        val dtos = api.academicRoute().courses.orEmpty()
        val now = clock()
        dao.replaceAll(dtos.map {
            CourseEntity(it.courseCode, it.courseName, it.semester, it.status, it.grade, now)
        })
        Loaded.Fresh(dtos.map { Course(it.courseCode, it.courseName, it.semester, CourseStatus.fromApi(it.status), it.grade) })
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        if (e is HttpException && e.code() == 401) Loaded.Failed(e) else cachedOr(e)
    }

    private suspend fun cachedOr(error: Exception): Loaded<List<Course>> {
        val cached = dao.getAll()
        if (cached.isEmpty()) return Loaded.Failed(error)
        return Loaded.Cached(
            cached.map { Course(it.courseCode, it.courseName, it.semester, CourseStatus.fromApi(it.status), it.grade) },
            cached.minOf { it.lastFetchedAt },
        )
    }
}

interface CalendarRepository {
    suspend fun events(): Loaded<List<CalendarEvent>>
}

class DefaultCalendarRepository(
    private val api: ChatbotApi,
    private val dao: CalendarDao,
    private val clock: () -> Long = System::currentTimeMillis,
) : CalendarRepository {
    override suspend fun events(): Loaded<List<CalendarEvent>> = try {
        val events = api.calendar().events.orEmpty()
            .map { CalendarEvent(it.eventName, it.eventDate, it.description.orEmpty()) }
        val now = clock()
        dao.replaceAll(events.map { CalendarEventEntity(it.key, it.name, it.date, it.description, now) })
        Loaded.Fresh(events)
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        if (e is HttpException && e.code() == 401) {
            Loaded.Failed(e)
        } else {
            val cached = dao.getAll()
            if (cached.isEmpty()) Loaded.Failed(e)
            else Loaded.Cached(cached.map { CalendarEvent(it.eventName, it.eventDate, it.description) },
                cached.minOf { it.lastFetchedAt })
        }
    }
}
