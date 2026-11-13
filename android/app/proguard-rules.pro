# DTOs serializados con Gson
-keep class com.unab.chatbot.network.dto.** { *; }
-keepattributes Signature, *Annotation*
# Retrofit
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
