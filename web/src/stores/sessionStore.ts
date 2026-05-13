import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DiagnosisSession, ChatMessage, DiagnosisSummary } from '@/types'
import { getSessions, getSession, switchSession, completeSession, getSkillSummary } from '@/api/http'
import { sendMessage } from '@/api/sse'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<DiagnosisSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const reportModalVisible = ref(false)
  const currentReport = ref<string>('')

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

        const sessionData = await getSession(sessionId)
        const summary = sessionData.latest_summary
        if (summary) {
          const syntheticMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: summary.report
              ? `诊断完成：${summary.fault_type}（置信度 ${Math.round(summary.confidence * 100)}%）`
              : '诊断完成',
            eventType: 'complete',
            timestamp: new Date().toISOString(),
            summary: {
              fault_type: summary.fault_type,
              confidence: summary.confidence,
            },
            report: summary.report ?? undefined,
          }
          messages.value.push(syntheticMsg)
        }
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
          const msg = event.payload?.message ?? '思考中...'
          assistantMsg.content = msg
          assistantMsg.thinking = msg
        } else if (event.event_type === 'result' || event.event_type === 'content') {
          assistantMsg.content += event.payload?.content ?? ''
        } else if (event.event_type === 'status') {
          const payloadStatus = event.payload?.status
          const validStatuses: DiagnosisSession['status'][] = ['pending', 'diagnosing', 'modifying', 'completed', 'excluded', 'rechecking']
          const newStatus = validStatuses.includes(payloadStatus) ? payloadStatus : undefined
          if (newStatus && activeSessionId.value) {
            const idx = sessions.value.findIndex(
              (s) => s.session_id === activeSessionId.value
            )
            if (idx !== -1) {
              sessions.value[idx] = { ...sessions.value[idx], status: newStatus }
            }
          }
        } else if (event.event_type === 'complete') {
          assistantMsg.content = event.payload?.message ?? '诊断完成'
          if (event.payload?.thinking) {
            assistantMsg.thinking = event.payload.thinking
          }
          if (event.payload?.summary) {
            assistantMsg.summary = event.payload.summary as DiagnosisSummary
          }
          if (event.payload?.report) {
            assistantMsg.report = event.payload.report as string
          }
        } else if (event.event_type === 'error') {
          assistantMsg.content = `错误: ${event.payload?.message ?? '未知错误'}`
          error.value = assistantMsg.content
        }

        if (event.session_id) {
          if (activeSessionId.value !== event.session_id) {
            activeSessionId.value = event.session_id
          }
          // Add new session to list if not present
          const existingIdx = sessions.value.findIndex(
            (s) => s.session_id === event.session_id
          )
          if (existingIdx === -1) {
            const lineName = event.payload?.line_name ?? '新会话'
            sessions.value.push({
              session_id: event.session_id,
              line_name: lineName,
              status: event.payload?.status ?? 'pending',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
          }
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

  async function markSessionComplete() {
    const sessionId = activeSessionId.value
    if (!sessionId) return
    try {
      error.value = null
      const data = await completeSession(sessionId)
      if (data.success) {
        const idx = sessions.value.findIndex((s) => s.session_id === sessionId)
        if (idx !== -1) {
          sessions.value[idx] = { ...sessions.value[idx], status: 'completed' }
        }
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function fetchSkillSummary(sessionId: string) {
    try {
      error.value = null
      return await getSkillSummary(sessionId)
    } catch (err) {
      error.value = (err as Error).message
      throw err
    }
  }

  function openReport(report: string) {
    currentReport.value = report
    reportModalVisible.value = true
  }

  function closeReport() {
    reportModalVisible.value = false
    currentReport.value = ''
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    error,
    reportModalVisible,
    currentReport,
    loadSessions,
    selectSession,
    postMessage,
    clearMessages,
    markSessionComplete,
    fetchSkillSummary,
    openReport,
    closeReport,
  }
})
