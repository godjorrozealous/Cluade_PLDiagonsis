<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { renderMarkdown } from '@/utils/markdown'

const store = useSessionStore()

const reportContent = computed(() => {
  const last = store.messages
    .filter((m) => m.role === 'assistant' && m.eventType === 'complete')
    .pop()
  return last?.content ?? ''
})

const hasReport = computed(() => !!reportContent.value)
</script>

<template>
  <section class="report-panel">
    <header class="report-header">
      <h3>诊断报告</h3>
    </header>

    <div v-if="hasReport" class="report-body markdown-body" v-html="renderMarkdown(reportContent)"></div>
    <div v-else class="report-empty">
      暂无报告
    </div>
  </section>
</template>

<style scoped>
.report-panel {
  width: 320px;
  min-width: 320px;
  background: #fff;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.report-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.report-header h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #0f172a;
}

.report-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  font-size: 0.875rem;
  line-height: 1.7;
}

.report-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 0.875rem;
}
</style>

<style>
.report-body.markdown-body p {
  margin: 0 0 0.5rem;
}

.report-body.markdown-body p:last-child {
  margin-bottom: 0;
}

.report-body.markdown-body pre {
  background: #f1f5f9;
  padding: 0.75rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  font-size: 0.8125rem;
}

.report-body.markdown-body code {
  background: #f1f5f9;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
}

.report-body.markdown-body pre code {
  background: transparent;
  padding: 0;
}

.report-body.markdown-body ul,
.report-body.markdown-body ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}

.report-body.markdown-body h1,
.report-body.markdown-body h2,
.report-body.markdown-body h3,
.report-body.markdown-body h4 {
  margin: 0.75rem 0 0.5rem;
  font-weight: 600;
}

.report-body.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.8125rem;
  margin: 0.5rem 0;
}

.report-body.markdown-body th,
.report-body.markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 0.375rem 0.5rem;
  text-align: left;
}

.report-body.markdown-body th {
  background: #f1f5f9;
  font-weight: 600;
}
</style>
