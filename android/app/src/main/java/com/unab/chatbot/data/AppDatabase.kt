package com.unab.chatbot.data

import android.content.Context
import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Transaction

@Entity(tableName = "courses")
data class CourseEntity(
    @PrimaryKey @ColumnInfo(name = "course_code") val courseCode: String,
    @ColumnInfo(name = "course_name") val courseName: String,
    val semester: Int,
    val status: String,
    val grade: Double?,
    @ColumnInfo(name = "last_fetched_at") val lastFetchedAt: Long,
)

@Entity(tableName = "calendar_events")
data class CalendarEventEntity(
    @PrimaryKey @ColumnInfo(name = "event_key") val eventKey: String,
    @ColumnInfo(name = "event_name") val eventName: String,
    @ColumnInfo(name = "event_date") val eventDate: String,
    val description: String,
    @ColumnInfo(name = "last_fetched_at") val lastFetchedAt: Long,
)

@Dao
interface CourseDao {
    @Query("SELECT * FROM courses ORDER BY semester, course_code")
    suspend fun getAll(): List<CourseEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<CourseEntity>)

    @Query("DELETE FROM courses")
    suspend fun clear()

    @Transaction
    suspend fun replaceAll(items: List<CourseEntity>) {
        clear()
        upsertAll(items)
    }
}

@Dao
interface CalendarDao {
    @Query("SELECT * FROM calendar_events ORDER BY event_date")
    suspend fun getAll(): List<CalendarEventEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<CalendarEventEntity>)

    @Query("DELETE FROM calendar_events")
    suspend fun clear()

    @Transaction
    suspend fun replaceAll(items: List<CalendarEventEntity>) {
        clear()
        upsertAll(items)
    }
}

@Database(entities = [CourseEntity::class, CalendarEventEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun courseDao(): CourseDao
    abstract fun calendarDao(): CalendarDao

    companion object {
        fun build(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "unab_chatbot.db")
                .fallbackToDestructiveMigration()
                .build()
    }
}
