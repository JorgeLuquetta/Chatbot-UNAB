package com.unab.chatbot.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.unab.chatbot.MainActivity
import com.unab.chatbot.ServiceLocator
import com.unab.chatbot.databinding.FragmentLoginBinding
import kotlinx.coroutines.launch

class LoginFragment : Fragment() {

    private var _binding: FragmentLoginBinding? = null
    private val binding get() = _binding!!

    private val viewModel: AuthViewModel by viewModels {
        viewModelFactory { initializer { AuthViewModel(ServiceLocator.authRepository) } }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentLoginBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding.loginButton.setOnClickListener { submit() }
        binding.retryButton.setOnClickListener { submit() }
        binding.passwordInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) { submit(); true } else false
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.state.collect { render(it) }
            }
        }
    }

    private fun submit() {
        viewModel.login(binding.studentIdInput.text?.toString().orEmpty(), binding.passwordInput.text?.toString().orEmpty())
    }

    private fun render(state: LoginUiState) {
        binding.progress.isVisible = state is LoginUiState.Loading
        binding.loginButton.isEnabled = state !is LoginUiState.Loading
        binding.errorText.isVisible = state is LoginUiState.Error
        binding.retryButton.isVisible = state is LoginUiState.Error && state.canRetry
        when (state) {
            is LoginUiState.Error -> binding.errorText.text = state.message
            is LoginUiState.Success -> {
                binding.passwordInput.setText("")
                viewModel.consumed()
                (activity as? MainActivity)?.onLoggedIn()
            }
            else -> Unit
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "login"
    }
}
