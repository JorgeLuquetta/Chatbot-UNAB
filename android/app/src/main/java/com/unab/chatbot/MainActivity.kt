package com.unab.chatbot

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.fragment.app.commit
import androidx.fragment.app.commitNow
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.unab.chatbot.academic.CalendarioFragment
import com.unab.chatbot.academic.RutaAcademicaFragment
import com.unab.chatbot.auth.LoginFragment
import com.unab.chatbot.chat.ChatFragment
import com.unab.chatbot.databinding.ActivityMainBinding
import com.unab.chatbot.network.SessionEvents
import com.unab.chatbot.notifications.DeviceRegistrar
import com.unab.chatbot.notifications.NotificationHelper
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* el SO recuerda la decisión */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_chat -> showTab(ChatFragment.TAG)
                R.id.nav_ruta -> showTab(RutaAcademicaFragment.TAG)
                R.id.nav_calendario -> showTab(CalendarioFragment.TAG)
            }
            true
        }
        binding.toolbar.setOnMenuItemClickListener {
            if (it.itemId == R.id.action_logout) confirmLogout()
            true
        }

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                SessionEvents.expired.collect { showLogin() }
            }
        }

        if (savedInstanceState == null) {
            if (ServiceLocator.tokenStore.isLoggedIn()) onLoggedIn(intent) else showLogin()
        } else {
            val loggedIn = supportFragmentManager.findFragmentByTag(LoginFragment.TAG) == null
            binding.bottomNav.isVisible = loggedIn
            if (loggedIn) {
                binding.toolbar.inflateMenu(R.menu.main_menu)
                binding.toolbar.subtitle = ServiceLocator.tokenStore.fullName()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (ServiceLocator.tokenStore.isLoggedIn()) handleNotificationIntent(intent)
    }

    /** Llamado por LoginFragment tras autenticarse, o al abrir con una sesión vigente. */
    fun onLoggedIn(launchIntent: Intent? = null) {
        val fm = supportFragmentManager
        fm.commitNow { fm.fragments.forEach { remove(it) } }
        showTab(ChatFragment.TAG)
        binding.bottomNav.menu.findItem(R.id.nav_chat).isChecked = true
        binding.bottomNav.isVisible = true
        binding.toolbar.menu.clear()
        binding.toolbar.inflateMenu(R.menu.main_menu)
        binding.toolbar.subtitle = ServiceLocator.tokenStore.fullName()
        requestNotificationPermission()
        DeviceRegistrar.registerCurrentToken(this)
        launchIntent?.let { handleNotificationIntent(it) }
    }

    private fun showLogin() {
        val fm = supportFragmentManager
        if (fm.findFragmentByTag(LoginFragment.TAG) != null) return
        fm.commit {
            fm.fragments.forEach { remove(it) }
            add(R.id.container, LoginFragment(), LoginFragment.TAG)
        }
        binding.bottomNav.isVisible = false
        binding.toolbar.menu.clear()
        binding.toolbar.subtitle = null
    }

    /** Las pestañas se ocultan/muestran (no se destruyen) para conservar la conversación. */
    private fun showTab(tag: String, factory: () -> Fragment = { defaultFragment(tag) }): Fragment {
        val fm = supportFragmentManager
        var target = fm.findFragmentByTag(tag)
        fm.commit {
            setReorderingAllowed(true)
            listOf(ChatFragment.TAG, RutaAcademicaFragment.TAG, CalendarioFragment.TAG)
                .mapNotNull { fm.findFragmentByTag(it) }
                .forEach { hide(it) }
            if (target == null) {
                target = factory()
                add(R.id.container, target!!, tag)
            } else {
                show(target!!)
            }
        }
        return target!!
    }

    private fun defaultFragment(tag: String): Fragment = when (tag) {
        RutaAcademicaFragment.TAG -> RutaAcademicaFragment()
        CalendarioFragment.TAG -> CalendarioFragment.newInstance()
        else -> ChatFragment()
    }

    /** Requirement 14.3: al tocar la notificación se abre el Calendario en el evento. */
    private fun handleNotificationIntent(intent: Intent) {
        if (intent.getStringExtra(NotificationHelper.EXTRA_OPEN_SCREEN) != NotificationHelper.SCREEN_CALENDAR) return
        val key = intent.getStringExtra(NotificationHelper.EXTRA_EVENT_KEY)
        intent.removeExtra(NotificationHelper.EXTRA_OPEN_SCREEN)
        val existing = supportFragmentManager.findFragmentByTag(CalendarioFragment.TAG) as? CalendarioFragment
        // Si la pestaña no existe se crea con el evento como argumento; si existe, se desplaza a él.
        showTab(CalendarioFragment.TAG) { CalendarioFragment.newInstance(key) }
        binding.bottomNav.menu.findItem(R.id.nav_calendario).isChecked = true
        if (existing != null && key != null) existing.scrollToEvent(key)
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun confirmLogout() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.logout)
            .setMessage(R.string.logout_confirm)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.logout) { _, _ ->
                lifecycleScope.launch {
                    ServiceLocator.authRepository.logout()
                    showLogin()
                }
            }
            .show()
    }
}
