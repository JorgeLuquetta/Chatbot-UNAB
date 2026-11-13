package com.unab.chatbot

import androidx.fragment.app.testing.launchFragmentInContainer
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.unab.chatbot.auth.AuthErrorMapper
import com.unab.chatbot.auth.LoginFragment
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LoginFragmentTest {

    @Test
    fun loginVacioMuestraMensajeSinLlamarAlBackend() {
        launchFragmentInContainer<LoginFragment>(themeResId = R.style.Theme_UnabChatbot)
        onView(withId(R.id.loginButton)).perform(click())
        onView(withId(R.id.errorText)).check(matches(isDisplayed()))
        onView(withId(R.id.errorText)).check(matches(withText(AuthErrorMapper.MISSING_FIELDS)))
    }
}
