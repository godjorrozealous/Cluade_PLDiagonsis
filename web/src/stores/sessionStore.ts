import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DiagnosisSession, ChatMessage } from '@/types'
import { getSessions, switchSession } from '@/api/http'
import { sendMessage } from '@/api/sse'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<DiagnosisSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const activeSession = computed(() =>
    sessions.value.find((s) => s.session_id === activeSessionId.value) ?? null
  )

  async function loadSessions() {
    try {
      error.value = null
      const data = await getSessions()
      sessions.value = data.sessions
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function selectSession(sessionId: string) {
    try {
      error.value = null
      const data = await switchSession(sessionId)
      if (data.success) {
        activeSessionId.value = sessionId
        messages.value = []
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function postMessage(text: string) {
    if (!text.trim() || isLoading.value) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)
    isLoading.value = true
    error.value = null

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      eventType: 'start',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(assistantMsg)

    try {
      for await (const event of sendMessage(text.trim())) {
        assistantMsg.eventType = event.event_type

        if (event.event_type === 'thinking') {
          assistantMsg.content = event.payload?.message ?? '思考中...'
        } else if (event.event_type === 'result' || event.event_type === 'content') {
          assistantMsg.content += event.payload?.content ?? ''
        } else if (event.event_type === 'complete') {
          assistantMsg.content = event.payload?.report ?? assistantMsg.content
        } else if (event.event_type === 'error') {
          assistantMsg.content = `错误: ${event.payload?.message ?? '未知错误'}`
          error.value = assistantMsg.content
        }

        if (event.session_id && activeSessionId.value !== event.session_id) {
          activeSessionId.value = event.session_id
        }
      }
    } catch (err) {
      const msg = `错误: ${(err as Error).message}`
      assistantMsg.content = msg
      assistantMsg.eventType = 'error'
      error.value = msg
    } finally {
      isLoading.value = false
      assistantMsg.timestamp = new Date().toISOString()
    }
  }

  function clearMessages() {
    messages.value = []
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    error,
    loadSessions,
    selectSession,
    postMessage,
    clearMessages,
  }
})
