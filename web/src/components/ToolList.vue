<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getTools, type ToolInfo } from '@/api/http'

const tools = ref<ToolInfo[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    electrical: '电气',
    environmental: '环境',
    biological: '生物',
    test: '测试',
  }
  return map[cat] ?? cat
}

async function loadTools() {
  loading.value = true
  error.value = null
  try {
    const data = await getTools()
    tools.value = data.tools
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTools()
})
</script>

<template>
  <section class="tool-panel">
    <header class="tool-header">
      <h3>诊断工具</h3>
      <button class="refresh-btn" @click="loadTools" title="刷新">&#x21bb;</button>
    </header>

    <ul v-if="tools.length > 0" class="tool-list">
      <li v-for="t in tools" :key="t.name" class="tool-item">
        <div class="tool-row">
          <span class="tool-name">{{ t.display_name }}</span>
          <span class="tool-category">{{ categoryLabel(t.category) }}</span>
        </div>
        <div class="tool-desc">{{ t.description }}</div>
      </li>
    </ul>

    <div v-else-if="loading" class="tool-empty">加载中...</div>
    <div v-else-if="error" class="tool-error">{{ error }}</div>
    <div v-else class="tool-empty">暂无工具</div>
  </section>
</template>

<style scoped>
.tool-panel {
  width: 260px;
  min-width: 260px;
  background: #fff;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.tool-header h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #0f172a;
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
  color: #0f172a;
}

.tool-list {
  list-style: none;
  margin: 0;
  padding: 0.75rem;
  overflow-y: auto;
  flex: 1;
}

.tool-item {
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
}

.tool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.tool-name {
  font-weight: 500;
  font-size: 0.875rem;
  color: #0f172a;
}

.tool-category {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.15rem 0.4rem;
  border-radius: 9999px;
  background: #f1f5f9;
  color: #64748b;
  white-space: nowrap;
}

.tool-desc {
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
  line-height: 1.4;
}

.tool-empty,
.tool-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  font-size: 0.875rem;
  color: #94a3b8;
}

.tool-error {
  color: #ef4444;
}
</style>
