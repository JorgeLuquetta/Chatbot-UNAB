package com.unab.chatbot.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface LoginUiState {
    data object Idle : LoginUiState
    data object Loading : LoginUiState
    data class Success(val fullName: String) : LoginUiState
    data class Error(val message: String, val canRetry: Boolean) : LoginUiState
}

class AuthViewModel(private val repository: AuthRepository) : ViewModel() {

    private val _state = MutableStateFlow<LoginUiState>(LoginUiState.Idle)
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun login(studentId: String, password: String) {
        if (studentId.isBlank() || password.isEmpty()) {
            _state.value = LoginUiState.Error(AuthErrorMapper.MISSING_FIELDS, canRetry = false)
            return
        }
        if (_state.value == LoginUiState.Loading) return
        _state.value = LoginUiState.Loading
        viewModelScope.launch {
            repository.login(studentId, password)
                .onSuccess { _state.value = LoginUiState.Success(it) }
                .onFailure {
                    _state.value = LoginUiState.Error(AuthErrorMapper.message(it), AuthErrorMapper.isRetryable(it))
                }
        }
    }

    fun consumed() {
        _state.value = LoginUiState.Idle
    }
}
