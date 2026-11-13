package com.unab.chatbot.network.dto

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("password") val password: String,
)

data class LoginResponse(
    @SerializedName("token") val token: String?,
    @SerializedName("session_id") val sessionId: String?,
    @SerializedName("expires_at") val expiresAt: String?,
    @SerializedName("full_name") val fullName: String?,
)

data class ChatResponse(
    @SerializedName("response") val response: String?,
    @SerializedName("intent") val intent: String?,
)

data class ErrorResponse(@SerializedName("error") val error: String?)

data class CourseDto(
    @SerializedName("course_code") val courseCode: String,
    @SerializedName("course_name") val courseName: String,
    @SerializedName("semester") val semester: Int,
    @SerializedName("status") val status: String,
    @SerializedName("grade") val grade: Double?,
)

data class CoursesResponse(
    @SerializedName("courses") val courses: List<CourseDto>?,
    @SerializedName("progress_percentage") val progressPercentage: Double?,
)

data class EventDto(
    @SerializedName("event_name") val eventName: String,
    @SerializedName("event_date") val eventDate: String,
    @SerializedName("description") val description: String?,
)

data class CalendarResponse(@SerializedName("events") val events: List<EventDto>?)

data class RegisterDeviceRequest(@SerializedName("fcm_token") val fcmToken: String)
