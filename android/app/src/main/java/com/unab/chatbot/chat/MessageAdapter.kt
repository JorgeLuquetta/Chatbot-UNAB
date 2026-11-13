package com.unab.chatbot.chat

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.unab.chatbot.R
import com.unab.chatbot.chat.model.Message
import com.unab.chatbot.chat.model.Sender
import com.unab.chatbot.databinding.ItemMessageBotBinding
import com.unab.chatbot.databinding.ItemMessageStudentBinding

/** Estilos visuales distintos para estudiante y chatbot (Requirement 2.1). */
class MessageAdapter : ListAdapter<Message, RecyclerView.ViewHolder>(DIFF) {

    class StudentVH(val b: ItemMessageStudentBinding) : RecyclerView.ViewHolder(b.root)
    class BotVH(val b: ItemMessageBotBinding) : RecyclerView.ViewHolder(b.root)

    override fun getItemViewType(position: Int) = if (getItem(position).sender == Sender.STUDENT) 0 else 1

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inf = LayoutInflater.from(parent.context)
        return if (viewType == 0) StudentVH(ItemMessageStudentBinding.inflate(inf, parent, false))
        else BotVH(ItemMessageBotBinding.inflate(inf, parent, false))
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val m = getItem(position)
        when (holder) {
            is StudentVH -> holder.b.text.text = m.text
            is BotVH -> {
                holder.b.text.text = m.text
                holder.b.bubble.setBackgroundResource(
                    if (m.sender == Sender.ERROR) R.drawable.bg_bubble_error else R.drawable.bg_bubble_bot)
            }
        }
    }

    companion object {
        private val DIFF = object : DiffUtil.ItemCallback<Message>() {
            override fun areItemsTheSame(a: Message, b: Message) = a.id == b.id
            override fun areContentsTheSame(a: Message, b: Message) = a == b
        }
    }
}
