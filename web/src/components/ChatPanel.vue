<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { renderMarkdown } from '@/utils/markdown'
import { createSkill } from '@/api/http'

const store = useSessionStore()
const input = ref('')
const listRef = ref<HTMLDivElement | null>(null)
const reportExpanded = ref<Record<string, boolean>>({})
const showCompletionReview = ref(false)
const reviewSessionId = ref<string | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

function toggleReport(msgId: string) {
  reportExpanded.value[msgId] = !reportExpanded.value[msgId]
}

function getActionLogForReview(): Array<{ action_type: string; tool_name: string; description: string; weight?: number }> {
  const session = store.activeSession
  if (!session) return []
  return session.action_log ?? []
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.messages.map((m) => m.content), scrollToBottom, { deep: true })

function handleSend() {
  if (!input.value.trim() || store.isLoading) return
  store.postMessage(input.value)
  input.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function bubbleClass(role: string, eventType?: string): string {
  if (role === 'user') return 'bubble-user'
  if (eventType === 'error') return 'bubble-error'
  if (eventType === 'thinking') return 'bubble-thinking'
  return 'bubble-assistant'
}

function handleCompleteDiagnosis() {
  const sessionId = store.activeSessionId
  if (!sessionId) return
  reviewSessionId.value = sessionId
  showCompletionReview.value = true
}

async function handleSaveSkillFromReview() {
  const sessionId = reviewSessionId.value
  if (!sessionId) return
  try {
    const data = await store.fetchSkillSummary(sessionId)
    const name = prompt('技能名称:', data.suggested_name)
    if (name) {
      await createSkill(name, data.content)
      window.dispatchEvent(new CustomEvent('skill-saved'))
      showCompletionReview.value = false
      await store.markSessionComplete()
    }
  } catch (err) {
    alert(`保存技能失败: ${(err as Error).message}`)
  }
}

async function handleSkipSave() {
  showCompletionReview.value = false
  await store.markSessionComplete()
}

function handleClearMessages() {
  if (confirm('确定要清除当前对话的所有消息吗？')) {
    store.clearMessages()
  }
}

function formatActionLabel(action: { action_type: string; tool_name: string; description: string; weight?: number }): string {
  switch (action.action_type) {
    case 'exclude':
      return `排除${action.tool_name}`
    case 'include':
      return `恢复${action.tool_name}`
    case 'recheck':
      return `复查${action.tool_name}`
    case 'adjust_weight':
      return `调整权重：${action.tool_name} ${action.weight ?? ''}`
    case 'modify_report':
      return `修改报告：${action.description || action.tool_name}`
    case 'complete':
      return '完成诊断'
    default:
      return `${action.action_type}${action.tool_name ? ': ' + action.tool_name : ''}`
  }
}
</script>

<template>
  <section class="chat-panel">
    <div ref="listRef" class="message-list">
      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="message-row"
        :class="msg.role"
      >
        <div class="bubble" :class="bubbleClass(msg.role, msg.eventType)">
          <!-- Start / Loading state -->
          <div
            v-if="msg.role === 'assistant' && msg.eventType === 'start'"
            class="thinking"
          >
            <span class="spinner"></span>
            <span>诊断中...</span>
          </div>

          <!-- Thinking state -->
          <div
            v-else-if="msg.role === 'assistant' && msg.eventType === 'thinking'"
            class="thinking"
          >
            <span class="spinner"></span>
            <span>诊断中...</span>
          </div>

          <!-- Complete state with summary card -->
          <div v-else-if="msg.role === 'assistant' && msg.summary" class="summary-card">
            <div class="summary-header">诊断完成</div>
            <div class="summary-body">
              <div v-if="msg.summary.voltage_level" class="summary-row">
                <span class="summary-label">电压等级</span>
                <span class="summary-value">{{ msg.summary.voltage_level }}</span>
              </div>
              <div v-if="msg.summary.line_name" class="summary-row">
                <span class="summary-label">线路名称</span>
                <span class="summary-value">{{ msg.summary.line_name }}</span>
              </div>
              <div v-if="msg.summary.fault_time" class="summary-row">
                <span class="summary-label">故障时间</span>
                <span class="summary-value">{{ msg.summary.fault_time }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">故障类型</span>
                <span class="summary-value">{{ msg.summary.fault_type }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">置信度</span>
                <span class="summary-value">{{ Math.round(msg.summary.confidence * 100) }}%</span>
              </div>
            </div>
            <div v-if="msg.summary?.action_log?.length || store.activeSession?.action_log?.length" class="action-log">
              <div class="action-log-label">操作记录</div>
              <div class="action-log-items">
                <span
                  v-for="(action, idx) in (msg.summary?.action_log ?? store.activeSession?.action_log ?? [])"
                  :key="idx"
                  class="action-tag"
                >
                  {{ formatActionLabel(action) }}
                </span>
              </div>
            </div>
            <div v-if="msg.report" class="report-section">
              <button class="view-report-btn" @click="toggleReport(msg.id)">
                {{ reportExpanded[msg.id] ? '收起报告' : '查看报告' }}
              </button>
              <div v-if="reportExpanded[msg.id]" class="report-content markdown-body" v-html="renderMarkdown(msg.report)"></div>
            </div>
            <div class="summary-actions">
              <button
                v-if="store.activeSession?.status === 'modifying' || store.activeSession?.status === 'excluded'"
                class="complete-btn"
                @click="handleCompleteDiagnosis"
                :disabled="store.isLoading"
              >
                完成诊断
              </button>
            </div>
          </div>

          <!-- Regular assistant message -->
          <div v-else-if="msg.role === 'assistant'">
            <div v-if="!msg.content && store.isLoading" class="thinking">
              <span class="spinner"></span>
              <span>诊断中...</span>
            </div>
            <div
              v-if="msg.content"
              class="markdown-body"
              v-html="renderMarkdown(msg.content)"
            ></div>
          </div>

          <!-- User message -->
          <div v-else>{{ msg.content }}</div>
        </div>
        <div class="msg-time">
          {{ new Date(msg.timestamp).toLocaleTimeString() }}
        </div>
      </div>

      <div v-if="store.messages.length === 0" class="welcome">
        <h1>输电线路故障综合诊断智能体</h1>
        <p>请输入线路信息开始诊断</p>
      </div>

      <!-- Completion review panel -->
      <div v-if="showCompletionReview" class="completion-review">
        <div class="review-header">诊断完成 — 操作回顾</div>
        <div class="review-body">
          <div v-if="getActionLogForReview().length > 0" class="review-actions-list">
            <div class="review-label">本次诊断中您执行了以下操作：</div>
            <div class="review-tags">
              <span
                v-for="(action, idx) in getActionLogForReview()"
                :key="idx"
                class="review-tag"
              >
                {{ formatActionLabel(action) }}
              </span>
            </div>
          </div>
          <div v-else class="review-no-actions">
            本次诊断未进行修改操作。
          </div>
          <div class="review-prompt">是否将该诊断策略保存为新技能？</div>
          <div class="review-buttons">
            <button class="save-skill-btn" @click="handleSaveSkillFromReview">保存技能</button>
            <button class="skip-save-btn" @click="handleSkipSave">不保存</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="store.messages.length > 0" class="chat-toolbar">
      <span class="msg-count">
        {{ store.messages.filter(m => m.role === 'user').length }} 轮对话
      </span>
      <button class="clear-btn" @click="handleClearMessages">
        清除对话
      </button>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        rows="2"
        placeholder="输入消息..."
        @keydown="handleKeydown"
        :disabled="store.isLoading"
      ></textarea>
      <button
        class="send-btn"
        :disabled="!input.trim() || store.isLoading"
        @click="handleSend"
      >
        发送
      </button>
    </div>

    <div v-if="store.error" class="error-bar">
      {{ store.error }}
    </div>
  </section>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  min-width: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message-row {
  display: flex;
  flex-direction: column;
  max-width: 80%;
}

.message-row.user {
  align-self: flex-end;
  align-items: flex-end;
}

.message-row.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.bubble {
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.9375rem;
  line-height: 1.6;
  word-break: break-word;
}

.bubble-user {
  background: #0f172a;
  color: #fff;
  border-bottom-right-radius: 0.25rem;
}

.bubble-assistant {
  background: #fff;
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 0.25rem;
}

.bubble-thinking {
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
  border-bottom-left-radius: 0.25rem;
}

.bubble-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
  border-bottom-left-radius: 0.25rem;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-style: italic;
}

.spinner {
  display: inline-block;
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid #fbbf24;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.thinking-block {
  margin-bottom: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background: #f8fafc;
  overflow: hidden;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  width: 100%;
  padding: 0.375rem 0.625rem;
  background: transparent;
  border: none;
  font-size: 0.8125rem;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s;
}

.thinking-toggle:hover {
  background: #f1f5f9;
}

.toggle-icon {
  display: inline-block;
  font-size: 0.625rem;
  transition: transform 0.2s;
}

.toggle-icon.collapsed {
  transform: rotate(-90deg);
}

.thinking-content {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid #e2e8f0;
}

.thinking-content pre {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.msg-time {
  font-size: 0.6875rem;
  color: #94a3b8;
  margin-top: 0.25rem;
}

.welcome {
  margin: auto;
  text-align: center;
  color: #64748b;
}

.welcome h1 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 0.5rem;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 2rem;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  font-size: 0.8125rem;
}

.msg-count {
  color: #64748b;
}

.clear-btn {
  background: transparent;
  color: #ef4444;
  border: 1px solid #fecaca;
  border-radius: 0.375rem;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.clear-btn:hover {
  background: #fef2f2;
  border-color: #ef4444;
}

.input-area {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 2rem;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.input-area textarea {
  flex: 1;
  resize: none;
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  padding: 0.625rem 0.875rem;
  font-size: 0.9375rem;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.15s;
}

.input-area textarea:focus {
  border-color: #0f172a;
}

.input-area textarea:disabled {
  background: #f1f5f9;
  cursor: not-allowed;
}

.send-btn {
  align-self: flex-end;
  background: #0f172a;
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  padding: 0.625rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.error-bar {
  padding: 0.75rem 2rem;
  background: #fef2f2;
  color: #991b1b;
  font-size: 0.875rem;
  border-top: 1px solid #fecaca;
}

/* Summary card styles */
.summary-card {
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 0.75rem;
  padding: 1rem;
  min-width: 240px;
}

.summary-header {
  font-weight: 600;
  font-size: 1rem;
  color: #14532d;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #86efac;
}

.summary-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
}

.summary-label {
  color: #166534;
}

.summary-value {
  font-weight: 600;
  color: #14532d;
}

.summary-actions {
  display: flex;
  gap: 0.5rem;
}

.action-log {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #86efac;
}

.action-log-label {
  font-size: 0.75rem;
  color: #166534;
  margin-bottom: 0.375rem;
}

.action-log-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.action-tag {
  display: inline-block;
  background: #fff;
  color: #14532d;
  border: 1px solid #86efac;
  border-radius: 0.25rem;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
}

.view-report-btn {
  background: #fff;
  color: #166534;
  border: 1px solid #86efac;
  border-radius: 0.375rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.view-report-btn:hover {
  background: #f0fdf4;
  border-color: #22c55e;
}

.complete-btn {
  background: #10b981;
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.complete-btn:hover:not(:disabled) {
  background: #059669;
}

.complete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Completion review panel */
.completion-review {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  padding: 1.25rem;
  margin-top: 1rem;
  max-width: 480px;
  align-self: flex-start;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.review-header {
  font-weight: 600;
  font-size: 1rem;
  color: #0f172a;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.review-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.review-label {
  font-size: 0.875rem;
  color: #475569;
  margin-bottom: 0.375rem;
}

.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.review-tag {
  display: inline-block;
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #e2e8f0;
  border-radius: 0.25rem;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.review-no-actions {
  font-size: 0.875rem;
  color: #94a3b8;
  font-style: italic;
}

.review-prompt {
  font-size: 0.9375rem;
  font-weight: 500;
  color: #0f172a;
  margin-top: 0.5rem;
}

.review-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.save-skill-btn {
  background: #0f172a;
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.save-skill-btn:hover {
  opacity: 0.9;
}

.skip-save-btn {
  background: #fff;
  color: #64748b;
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.skip-save-btn:hover {
  background: #f8fafc;
  border-color: #94a3b8;
}

/* Report section in summary card */
.report-section {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #86efac;
}

.report-content {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
}
</style>

<style>
.markdown-body p {
  margin: 0 0 0.5rem;
}

.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body pre {
  background: #f1f5f9;
  padding: 0.75rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  font-size: 0.8125rem;
}

.markdown-body code {
  background: #f1f5f9;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
}

.markdown-body pre code {
  background: transparent;
  padding: 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: 0.75rem 0 0.5rem;
  font-weight: 600;
}

.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.8125rem;
  margin: 0.5rem 0;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 0.375rem 0.5rem;
  text-align: left;
}

.markdown-body th {
  background: #f1f5f9;
  font-weight: 600;
}
</style>
