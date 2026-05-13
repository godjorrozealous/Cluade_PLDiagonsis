<script setup lang="ts">
import { useSessionStore } from '@/stores/sessionStore'
import { onMounted } from 'vue'

const store = useSessionStore()

onMounted(() => {
  store.loadSessions()
})

function statusClass(status: string): string {
  switch (status) {
    case 'pending':
      return 'status-pending'
    case 'diagnosing':
      return 'status-diagnosing'
    case 'modifying':
      return 'status-modifying'
    case 'completed':
      return 'status-completed'
    case 'excluded':
      return 'status-excluded'
    case 'rechecking':
      return 'status-rechecking'
    default:
      return ''
  }
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    diagnosing: '诊断中',
    modifying: '修改中',
    completed: '已完成',
    excluded: '已排除',
    rechecking: '复查中',
  }
  return map[status] ?? status
}
</script>

<template>
  <aside class="sidebar">
    <header class="sidebar-header">
      <h2>诊断列表</h2>
      <button class="refresh-btn" @click="store.loadSessions" title="刷新">
        &#x21bb;
      </button>
    </header>

    <ul class="session-list">
      <li
        v-for="session in store.sessions"
        :key="session.session_id"
        class="session-item"
        :class="{ active: store.activeSessionId === session.session_id }"
        @click="store.selectSession(session.session_id)"
      >
        <div class="session-row">
          <span class="line-name">{{ session.line_name }}</span>
          <span class="status-badge" :class="statusClass(session.status)">
            {{ statusLabel(session.status) }}
          </span>
        </div>
        <div class="session-meta">
          {{ new Date(session.updated_at).toLocaleString() }}
        </div>
      </li>
    </ul>

    <div v-if="store.sessions.length === 0" class="empty">
      暂无会话
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 280px;
  min-width: 280px;
  background: #0f172a;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #1e293b;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #1e293b;
}

.sidebar-header h2 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.refresh-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.refresh-btn:hover {
  color: #e2e8f0;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0.5rem;
  overflow-y: auto;
  flex: 1;
}

.session-item {
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 0.25rem;
}

.session-item:hover {
  background: #1e293b;
}

.session-item.active {
  background: #334155;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.line-name {
  font-weight: 500;
  font-size: 0.875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.15rem 0.4rem;
  border-radius: 9999px;
  white-space: nowrap;
  flex-shrink: 0;
}

.status-pending {
  background: #475569;
  color: #f1f5f9;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-diagnosing {
  background: #f59e0b;
  color: #fff;
  animation: pulse 1.5s ease-in-out infinite;
}

.status-modifying {
  background: #3b82f6;
  color: #fff;
}

.status-completed {
  background: #10b981;
  color: #fff;
}

.status-excluded {
  background: #ef4444;
  color: #fff;
}

.status-rechecking {
  background: #8b5cf6;
  color: #fff;
}

.session-meta {
  font-size: 0.7rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.875rem;
}
</style>
