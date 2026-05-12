<script setup lang="ts">
import { useSessionStore } from '@/stores/sessionStore'
import { renderMarkdown } from '@/utils/markdown'

const store = useSessionStore()

function close() {
  store.closeReport()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.reportModalVisible" class="modal-overlay" @click="close">
      <div class="modal-content" @click.stop>
        <header class="modal-header">
          <h3>诊断报告</h3>
          <button class="close-btn" @click="close">&times;</button>
        </header>
        <div class="modal-body markdown-body" v-html="renderMarkdown(store.currentReport)" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
}

.modal-content {
  background: #fff;
  border-radius: 0.75rem;
  width: 100%;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.375rem;
  transition: all 0.15s;
}

.close-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  font-size: 0.9375rem;
  line-height: 1.7;
}
</style>

<style>
.modal-body.markdown-body p {
  margin: 0 0 0.75rem;
}

.modal-body.markdown-body p:last-child {
  margin-bottom: 0;
}

.modal-body.markdown-body pre {
  background: #f1f5f9;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.875rem;
}

.modal-body.markdown-body code {
  background: #f1f5f9;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.modal-body.markdown-body pre code {
  background: transparent;
  padding: 0;
}

.modal-body.markdown-body ul,
.modal-body.markdown-body ol {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}

.modal-body.markdown-body h1,
.modal-body.markdown-body h2,
.modal-body.markdown-body h3,
.modal-body.markdown-body h4 {
  margin: 1.25rem 0 0.75rem;
  font-weight: 600;
}

.modal-body.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.875rem;
  margin: 0.75rem 0;
}

.modal-body.markdown-body th,
.modal-body.markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 0.5rem 0.625rem;
  text-align: left;
}

.modal-body.markdown-body th {
  background: #f1f5f9;
  font-weight: 600;
}
</style>
