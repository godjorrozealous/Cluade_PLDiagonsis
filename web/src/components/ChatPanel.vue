<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { renderMarkdown } from '@/utils/markdown'

const store = useSessionStore()
const input = ref('')
const listRef = ref<HTMLDivElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
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
          <div
            v-if="msg.role === 'assistant' && msg.eventType === 'thinking'"
            class="thinking"
          >
            <span class="spinner"></span>
            <span>{{ msg.content }}</span>
          </div>
          <div
            v-else-if="msg.role === 'assistant'"
            class="markdown-body"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <div v-else>{{ msg.content }}</div>
        </div>
        <div class="msg-time">
          {{ new Date(msg.timestamp).toLocaleTimeString() }}
        </div>
      </div>

      <div v-if="store.messages.length === 0" class="welcome">
        <h1>输电线路故障诊断智能体</h1>
        <p>请输入线路信息开始诊断</p>
      </div>
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
