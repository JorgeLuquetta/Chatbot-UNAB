package com.unab.chatbot.academic

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.unab.chatbot.databinding.ItemCourseBinding
import com.unab.chatbot.databinding.ItemEventBinding
import com.unab.chatbot.databinding.ItemHeaderBinding

private const val TYPE_HEADER = 0
private const val TYPE_ROW = 1

class HeaderVH(val b: ItemHeaderBinding) : RecyclerView.ViewHolder(b.root)
class CourseVH(val b: ItemCourseBinding) : RecyclerView.ViewHolder(b.root)
class EventVH(val b: ItemEventBinding) : RecyclerView.ViewHolder(b.root)

class RouteAdapter : ListAdapter<RouteItem, RecyclerView.ViewHolder>(object : DiffUtil.ItemCallback<RouteItem>() {
    override fun areItemsTheSame(a: RouteItem, b: RouteItem) = when {
        a is RouteItem.SemesterHeader && b is RouteItem.SemesterHeader -> a.semester == b.semester
        a is RouteItem.CourseRow && b is RouteItem.CourseRow -> a.course.code == b.course.code
        else -> false
    }
    override fun areContentsTheSame(a: RouteItem, b: RouteItem) = a == b
}) {
    override fun getItemViewType(position: Int) = if (getItem(position) is RouteItem.SemesterHeader) TYPE_HEADER else TYPE_ROW

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inf = LayoutInflater.from(parent.context)
        return if (viewType == TYPE_HEADER) HeaderVH(ItemHeaderBinding.inflate(inf, parent, false))
        else CourseVH(ItemCourseBinding.inflate(inf, parent, false))
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        when (val item = getItem(position)) {
            is RouteItem.SemesterHeader -> (holder as HeaderVH).b.apply {
                title.text = "Semestre ${item.semester}"
                subtitle.isVisible = true
                subtitle.text = "${item.completed}/${item.total} aprobados"
            }
            is RouteItem.CourseRow -> (holder as CourseVH).b.apply {
                val c = item.course
                val color = ContextCompat.getColor(root.context, c.status.color)
                courseName.text = c.name
                courseCode.text = c.code
                statusLabel.text = c.status.label
                statusLabel.setTextColor(color)
                statusIcon.setImageResource(c.status.icon)
                statusIcon.setColorFilter(color)
                statusIcon.contentDescription = c.status.label
                grade.isVisible = c.grade != null
                grade.text = c.grade?.let { String.format(LOCALE_CO, "%.1f", it) }.orEmpty()
            }
        }
    }
}

class CalendarAdapter(private val onClick: (CalendarEvent) -> Unit) :
    ListAdapter<CalendarItem, RecyclerView.ViewHolder>(object : DiffUtil.ItemCallback<CalendarItem>() {
        override fun areItemsTheSame(a: CalendarItem, b: CalendarItem) = when {
            a is CalendarItem.MonthHeader && b is CalendarItem.MonthHeader -> a.yearMonth == b.yearMonth
            a is CalendarItem.EventRow && b is CalendarItem.EventRow -> a.event.key == b.event.key
            else -> false
        }
        override fun areContentsTheSame(a: CalendarItem, b: CalendarItem) = a == b
    }) {

    override fun getItemViewType(position: Int) = if (getItem(position) is CalendarItem.MonthHeader) TYPE_HEADER else TYPE_ROW

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inf = LayoutInflater.from(parent.context)
        return if (viewType == TYPE_HEADER) HeaderVH(ItemHeaderBinding.inflate(inf, parent, false))
        else EventVH(ItemEventBinding.inflate(inf, parent, false))
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        when (val item = getItem(position)) {
            is CalendarItem.MonthHeader -> (holder as HeaderVH).b.apply {
                title.text = item.title
                subtitle.isVisible = false
            }
            is CalendarItem.EventRow -> (holder as EventVH).b.apply {
                val e = item.event
                day.text = e.localDate?.dayOfMonth?.toString() ?: "—"
                eventName.text = e.name
                eventDescription.text = e.description
                eventDescription.isVisible = e.description.isNotBlank()
                root.setOnClickListener { onClick(e) }
            }
        }
    }

    fun positionOf(eventKey: String): Int =
        currentList.indexOfFirst { it is CalendarItem.EventRow && it.event.key == eventKey }
}
