<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'

const store = useSessionStore()

const statusColor = computed(() => {
  const map: Record<string, string> = {
    diagnosing: 'var(--status-diagnosing)',
    modifying: 'var(--status-modifying)',
    completed: 'var(--status-completed)',
  }
  return map[store.activeSession?.status || ''] || 'var(--status-pending)'
})

const isBreathing = computed(() => {
  const status = store.activeSession?.status
  return status === 'diagnosing' || status === 'modifying'
})
</script>

<template>
  <header class="app-header">
    <div class="header-brand">
      <span class="header-icon">&#9889;</span>
      <div>
        <div class="header-title">输电线路故障综合诊断智能体</div>
        <div class="header-subtitle">Power Line Fault Comprehensive Diagnosis Agent</div>
      </div>
    </div>
    <div class="status-indicator">
      <span
        class="status-dot"
        :class="{ breathing: isBreathing }"
        :style="{ background: statusColor, color: statusColor }"
      />
      <span>{{ store.activeSession?.status || '就绪' }}</span>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  background: rgba(6, 11, 20, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%, var(--color-primary) 20%,
    var(--color-accent) 50%, var(--color-primary) 80%, transparent 100%
  );
  opacity: 0.6;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.25rem;
  animation: pulse-glow 3s ease-in-out infinite;
}

.header-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

.header-subtitle {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 4px currentColor;
}

.status-dot.breathing {
  animation: breathing 2s ease-in-out infinite;
}
</style>
