package com.unab.chatbot

import com.unab.chatbot.academic.CalendarEvent
import com.unab.chatbot.academic.CalendarItem
import com.unab.chatbot.academic.Course
import com.unab.chatbot.academic.CourseStatus
import com.unab.chatbot.academic.RouteItem
import com.unab.chatbot.academic.buildCalendarItems
import com.unab.chatbot.academic.buildRouteItems
import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.shouldBe
import io.kotest.matchers.shouldNotBe
import io.kotest.property.Arb
import io.kotest.property.PropTestConfig
import io.kotest.property.arbitrary.bind
import io.kotest.property.arbitrary.choice
import io.kotest.property.arbitrary.constant
import io.kotest.property.arbitrary.double
import io.kotest.property.arbitrary.element
import io.kotest.property.arbitrary.int
import io.kotest.property.arbitrary.list
import io.kotest.property.arbitrary.localDate
import io.kotest.property.arbitrary.map
import io.kotest.property.arbitrary.orNull
import io.kotest.property.arbitrary.string
import io.kotest.property.checkAll
import java.time.LocalDate
import java.time.YearMonth

private val cfg = PropTestConfig(iterations = 100)

class AcademicPropertiesTest : StringSpec({

    // Feature: chatbot-apoyo-academico, Property 22: Estado de cursos coincide con datos del backend
    "Property 22: cada curso renderizado conserva exactamente el status del backend" {
        val dto = Arb.bind(
            Arb.string(3..8), Arb.string(1..30), Arb.int(1..10),
            Arb.element("completed", "pending", "in_progress"), Arb.double(0.0, 5.0).orNull(),
        ) { code, name, sem, status, grade -> listOf(code, name, sem, status, grade) }
        checkAll(cfg, Arb.list(dto, 0..40)) { raw ->
            val backend = raw.distinctBy { it[0] }
            val courses = backend.map {
                Course(it[0] as String, it[1] as String, it[2] as Int, CourseStatus.fromApi(it[3] as String), it[4] as Double?)
            }
            val rows = buildRouteItems(courses).filterIsInstance<RouteItem.CourseRow>()
            rows.size shouldBe backend.size
            val statusByCode = backend.associate { it[0] as String to it[3] as String }
            rows.forEach { row -> row.course.status.apiValue shouldBe statusByCode.getValue(row.course.code) }
        }
    }

    "las cabeceras de semestre preceden a sus cursos y los estados tienen estilos distintos" {
        val items = buildRouteItems(listOf(
            Course("B", "B", 2, CourseStatus.PENDING, null),
            Course("A", "A", 1, CourseStatus.COMPLETED, 4.5),
        ))
        (items[0] as RouteItem.SemesterHeader).semester shouldBe 1
        (items[2] as RouteItem.SemesterHeader).semester shouldBe 2
        CourseStatus.COMPLETED.color shouldNotBe CourseStatus.PENDING.color
        CourseStatus.COMPLETED.icon shouldNotBe CourseStatus.PENDING.icon
    }

    // Feature: chatbot-apoyo-academico, Property 23: Agrupación correcta de eventos de calendario por mes
    "Property 23: cada evento aparece bajo el encabezado de su mes y año" {
        val date = Arb.localDate(LocalDate.of(2024, 1, 1), LocalDate.of(2028, 12, 31))
        val dateText = Arb.choice(date.map { it.toString() }, date.map { "${it}T08:00:00-05:00" }, Arb.constant("por definir"))
        val event = Arb.bind(Arb.string(1..20), dateText, Arb.string(0..30)) { n, d, desc -> CalendarEvent(n, d, desc) }
        checkAll(cfg, Arb.list(event, 0..50)) { events ->
            val items = buildCalendarItems(events)
            items.count { it is CalendarItem.EventRow } shouldBe events.size
            var current: YearMonth? = null
            var seenHeader = false
            for (item in items) {
                when (item) {
                    is CalendarItem.MonthHeader -> { current = item.yearMonth; seenHeader = true }
                    is CalendarItem.EventRow -> {
                        seenHeader shouldBe true
                        item.event.localDate?.let { YearMonth.from(it) } shouldBe current
                    }
                }
            }
            val headers = items.filterIsInstance<CalendarItem.MonthHeader>().map { it.yearMonth }
            headers.size shouldBe headers.toSet().size // un encabezado por mes
        }
    }

    "título de mes en español y clave de evento compatible con el backend" {
        CalendarItem.MonthHeader(YearMonth.of(2026, 11)).title shouldBe "Noviembre 2026"
        CalendarEvent("Parciales", "2026-11-20", "").key shouldBe "Parciales|2026-11-20"
    }
})
