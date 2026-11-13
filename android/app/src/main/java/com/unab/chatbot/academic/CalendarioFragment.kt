package com.unab.chatbot.academic

import android.os.Bundle
import android.text.format.DateUtils
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.unab.chatbot.ServiceLocator
import com.unab.chatbot.databinding.FragmentCalendarioBinding
import kotlinx.coroutines.launch

class CalendarioFragment : Fragment() {

    private var _binding: FragmentCalendarioBinding? = null
    private val binding get() = _binding!!
    private val adapter = CalendarAdapter(::showDetail)
    /** Evento al que hay que desplazarse (al abrir desde una notificación push). */
    private var pendingScrollKey: String? = null

    private val viewModel: CalendarioViewModel by viewModels {
        viewModelFactory { initializer { CalendarioViewModel(ServiceLocator.calendarRepository) } }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingScrollKey = arguments?.getString(ARG_EVENT_KEY)
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentCalendarioBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding.list.layoutManager = LinearLayoutManager(requireContext())
        binding.list.adapter = adapter
        binding.swipe.setOnRefreshListener { viewModel.load() }
        binding.retryButton.setOnClickListener { viewModel.load() }

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.state.collect { s ->
                    binding.swipe.isRefreshing = s.loading
                    adapter.submitList(s.items) { scrollToPendingEvent() }
                    binding.staleBanner.isVisible = s.staleSince != null
                    s.staleSince?.let {
                        binding.staleBanner.text = "Los datos pueden no estar actualizados (guardados " +
                            DateUtils.getRelativeTimeSpanString(it).toString().lowercase() + ")."
                    }
                    binding.emptyText.isVisible = !s.loading && s.error == null && s.items.isEmpty()
                    binding.errorGroup.isVisible = s.error != null && s.items.isEmpty()
                    binding.errorText.text = s.error
                }
            }
        }
        if (savedInstanceState == null) viewModel.load()
    }

    fun scrollToEvent(eventKey: String) {
        pendingScrollKey = eventKey
        if (_binding != null) scrollToPendingEvent()
    }

    private fun scrollToPendingEvent() {
        val key = pendingScrollKey ?: return
        val pos = adapter.positionOf(key)
        if (pos >= 0) {
            (binding.list.layoutManager as LinearLayoutManager).scrollToPositionWithOffset(pos, 0)
            pendingScrollKey = null
            (adapter.currentList[pos] as? CalendarItem.EventRow)?.let { showDetail(it.event) }
        }
    }

    private fun showDetail(event: CalendarEvent) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(event.name)
            .setMessage(buildString {
                append("Fecha: ").append(event.displayDate)
                if (event.description.isNotBlank()) append("\n\n").append(event.description)
            })
            .setPositiveButton("Cerrar", null)
            .show()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "calendario"
        private const val ARG_EVENT_KEY = "event_key"

        fun newInstance(eventKey: String? = null) = CalendarioFragment().apply {
            arguments = bundleOf(ARG_EVENT_KEY to eventKey)
        }
    }
}
