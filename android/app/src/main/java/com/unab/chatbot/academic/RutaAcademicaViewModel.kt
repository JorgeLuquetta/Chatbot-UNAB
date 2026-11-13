package com.unab.chatbot.academic

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unab.chatbot.data.AcademicRepository
import com.unab.chatbot.data.CalendarRepository
import com.unab.chatbot.data.Loaded
import com.unab.chatbot.network.ErrorMapper
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Estado común de las pantallas con cache offline. */
data class ListUiState<T>(
    val loading: Boolean = false,
    val items: List<T> = emptyList(),
    /** Si no es null, los datos vienen de la cache y se muestra el indicador de obsolescencia. */
    val staleSince: Long? = null,
    val error: String? = null,
    val progress: Int = 0,
)

class RutaAcademicaViewModel(private val repository: AcademicRepository) : ViewModel() {
    private val _state = MutableStateFlow(ListUiState<RouteItem>())
    val state: StateFlow<ListUiState<RouteItem>> = _state.asStateFlow()

    fun load() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            _state.value = when (val r = repository.courses()) {
                is Loaded.Fresh -> ListUiState(items = buildRouteItems(r.data), progress = progressPercentage(r.data))
                is Loaded.Cached -> ListUiState(items = buildRouteItems(r.data), staleSince = r.lastFetchedAt,
                    progress = progressPercentage(r.data))
                is Loaded.Failed -> _state.value.copy(loading = false, error = ErrorMapper.friendlyMessage(r.error))
            }
        }
    }
}

class CalendarioViewModel(private val repository: CalendarRepository) : ViewModel() {
    private val _state = MutableStateFlow(ListUiState<CalendarItem>())
    val state: StateFlow<ListUiState<CalendarItem>> = _state.asStateFlow()

    fun load() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            _state.value = when (val r = repository.events()) {
                is Loaded.Fresh -> ListUiState(items = buildCalendarItems(r.data))
                is Loaded.Cached -> ListUiState(items = buildCalendarItems(r.data), staleSince = r.lastFetchedAt)
                is Loaded.Failed -> _state.value.copy(loading = false, error = ErrorMapper.friendlyMessage(r.error))
            }
        }
    }
}
