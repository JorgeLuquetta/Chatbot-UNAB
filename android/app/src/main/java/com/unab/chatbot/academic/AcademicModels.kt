package com.unab.chatbot.academic

import androidx.annotation.ColorRes
import androidx.annotation.DrawableRes
import com.unab.chatbot.R
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

val LOCALE_CO: Locale = Locale("es", "CO")

enum class CourseStatus(val apiValue: String, val label: String, @ColorRes val color: Int, @DrawableRes val icon: Int) {
    COMPLETED("completed", "Aprobado", R.color.status_completed, R.drawable.ic_status_completed),
    IN_PROGRESS("in_progress", "En curso", R.color.status_in_progress, R.drawable.ic_status_in_progress),
    PENDING("pending", "Pendiente", R.color.status_pending, R.drawable.ic_status_pending);

    companion object {
        fun fromApi(value: String?): CourseStatus =
            entries.firstOrNull { it.apiValue == value?.trim()?.lowercase() } ?: PENDING
    }
}

data class Course(
    val code: String,
    val name: String,
    val semester: Int,
    val status: CourseStatus,
    val grade: Double?,
)

data class CalendarEvent(val name: String, val date: String, val description: String) {
    /** Misma clave que usa el backend para las notificaciones push: "<nombre>|<fecha>". */
    val key: String get() = "$name|$date"

    val localDate: LocalDate? get() = parseDate(date)

    val displayDate: String
        get() = localDate?.format(DateTimeFormatter.ofPattern("EEEE d 'de' MMMM 'de' yyyy", LOCALE_CO)) ?: date

    companion object {
        fun parseDate(value: String): LocalDate? =
            runCatching { LocalDate.parse(value.trim().take(10)) }.getOrNull()
    }
}

// ---------------------------------------------------------------- elementos de lista
sealed interface RouteItem {
    data class SemesterHeader(val semester: Int, val completed: Int, val total: Int) : RouteItem
    data class CourseRow(val course: Course) : RouteItem
}

sealed interface CalendarItem {
    /** yearMonth == null agrupa eventos con fecha no reconocida. */
    data class MonthHeader(val yearMonth: YearMonth?) : CalendarItem {
        val title: String
            get() = yearMonth?.let {
                it.month.getDisplayName(TextStyle.FULL_STANDALONE, LOCALE_CO)
                    .replaceFirstChar { c -> c.titlecase(LOCALE_CO) } + " " + it.year
            } ?: "Sin fecha"
    }

    data class EventRow(val event: CalendarEvent) : CalendarItem
}

/** Ruta académica agrupada por semestre (Requirement 12.1). El estado se conserva tal cual (Property 22). */
fun buildRouteItems(courses: List<Course>): List<RouteItem> =
    courses.groupBy { it.semester }.toSortedMap().flatMap { (semester, list) ->
        listOf<RouteItem>(RouteItem.SemesterHeader(semester, list.count { it.status == CourseStatus.COMPLETED }, list.size)) +
            list.sortedBy { it.code }.map { RouteItem.CourseRow(it) }
    }

/** Eventos agrupados por mes y año (Requirement 13.2 / Property 23). */
fun buildCalendarItems(events: List<CalendarEvent>): List<CalendarItem> {
    val groups = events.groupBy { e -> e.localDate?.let { YearMonth.from(it) } }
    val ordered = groups.keys.sortedWith(nullsLast(naturalOrder()))
    return ordered.flatMap { ym ->
        listOf<CalendarItem>(CalendarItem.MonthHeader(ym)) +
            groups.getValue(ym).sortedWith(compareBy<CalendarEvent>({ it.localDate }, { it.name })).map { CalendarItem.EventRow(it) }
    }
}

fun progressPercentage(courses: List<Course>): Int =
    if (courses.isEmpty()) 0 else (100.0 * courses.count { it.status == CourseStatus.COMPLETED } / courses.size).toInt()
