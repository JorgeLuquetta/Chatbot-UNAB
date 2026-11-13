package com.unab.chatbot.academic

import android.os.Bundle
import android.text.format.DateUtils
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.recyclerview.widget.LinearLayoutManager
import com.unab.chatbot.ServiceLocator
import com.unab.chatbot.databinding.FragmentRutaAcademicaBinding
import kotlinx.coroutines.launch

class RutaAcademicaFragment : Fragment() {

    private var _binding: FragmentRutaAcademicaBinding? = null
    private val binding get() = _binding!!
    private val adapter = RouteAdapter()

    private val viewModel: RutaAcademicaViewModel by viewModels {
        viewModelFactory { initializer { RutaAcademicaViewModel(ServiceLocator.academicRepository) } }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentRutaAcademicaBinding.inflate(inflater, container, false)
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
                    adapter.submitList(s.items)
                    binding.progressBar.progress = s.progress
                    binding.progressText.text = "Avance de la carrera: ${s.progress}%"
                    binding.progressGroup.isVisible = s.items.isNotEmpty()
                    binding.staleBanner.isVisible = s.staleSince != null
                    s.staleSince?.let {
                        binding.staleBanner.text = "Sin conexión. Mostrando datos guardados " +
                            DateUtils.getRelativeTimeSpanString(it).toString().lowercase() + "."
                    }
                    binding.errorGroup.isVisible = s.error != null && s.items.isEmpty()
                    binding.errorText.text = s.error
                }
            }
        }
        if (savedInstanceState == null) viewModel.load()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "ruta"
    }
}
