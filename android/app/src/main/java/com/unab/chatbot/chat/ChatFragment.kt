package com.unab.chatbot.chat

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.recyclerview.widget.LinearLayoutManager
import com.unab.chatbot.ServiceLocator
import com.unab.chatbot.databinding.FragmentChatBinding
import kotlinx.coroutines.launch

class ChatFragment : Fragment() {

    private var _binding: FragmentChatBinding? = null
    private val binding get() = _binding!!
    private val adapter = MessageAdapter()

    private val viewModel: ChatViewModel by viewModels {
        viewModelFactory { initializer { ChatViewModel(ServiceLocator.chatRepository) } }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentChatBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding.messages.layoutManager = LinearLayoutManager(requireContext()).apply { stackFromEnd = true }
        binding.messages.adapter = adapter

        binding.inputLayout.counterMaxLength = MessageValidator.MAX_LENGTH
        binding.input.doAfterTextChanged { refreshSendButton() }
        binding.sendButton.setOnClickListener { submit() }
        binding.input.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) { submit(); true } else false
        }
        refreshSendButton()

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.state.collect { s ->
                    adapter.submitList(s.messages) {
                        if (s.messages.isNotEmpty()) binding.messages.scrollToPosition(s.messages.size - 1)
                    }
                    binding.typingIndicator.isVisible = s.isLoading
                    refreshSendButton(s.isLoading)
                }
            }
        }
    }

    private fun submit() {
        val text = binding.input.text?.toString().orEmpty()
        if (viewModel.state.value.isLoading) return
        if (viewModel.send(text)) binding.input.setText("")
    }

    private fun refreshSendButton(loading: Boolean = viewModel.state.value.isLoading) {
        val b = _binding ?: return
        b.sendButton.isEnabled = !loading && MessageValidator.isValid(b.input.text?.toString())
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "chat"
    }
}
