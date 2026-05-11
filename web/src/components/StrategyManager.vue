<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getStrategies, activateStrategy, deleteStrategy, resetStrategies } from '@/api/http'
import type { StrategyInfo } from '@/api/http'

const strategies = ref<StrategyInfo[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const activeName = ref<string | null>(null)

async function loadStrategies() {
  loading.value = true
  error.value = null
  try {
    const data = await getStrategies()
    strategies.value = data.strategies
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

async function handleActivate(name: string) {
  try {
    error.value = null
    await activateStrategy(name)
    activeName.value = name
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function handleDelete(name: string) {
  if (!confirm(`确定删除策略 "${name}" 吗？`)) return
  try {
    error.value = null
    await deleteStrategy(name)
    if (activeName.value === name) activeName.value = null
    await loadStrategies()
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function handleReset() {
  try {
    error.value = null
    await resetStrategies()
    activeName.value = null
  } catch (err) {
    error.value = (err as Error).message
  }
}

onMounted(() => {
  loadStrategies()
})
</script>

<template>
  <section class="strategy-panel">
    <header class="strategy-header">
      <h3>策略管理</h3>
      <div class="strategy-actions">
        <button class="icon-btn" @click="loadStrategies" title="刷新">&#x21bb;</button>
        <button class="icon-btn" @click="handleReset" title="重置为默认">&#x21ba;</button>
      </div>
    </header>

    <ul v-if="strategies.length > 0" class="strategy-list">
      <li
        v-for="s in strategies"
        :key="s.name"
        class="strategy-item"
        :class="{ active: activeName === s.name }"
      >
        <div class="strategy-info">
          <div class="strategy-name">{{ s.name }}</div>
          <div class="strategy-desc">{{ s.description || '无描述' }}</div>
        </div>
        <div class="strategy-actions">
          <button
            class="activate-btn"
            :class="{ activated: activeName === s.name }"
            @click="handleActivate(s.name)"
          >
            {{ activeName === s.name ? '已激活' : '激活' }}
          </button>
          <button class="delete-btn" @click="handleDelete(s.name)" title="删除">&times;</button>
        </div>
      </li>
    </ul>

    <div v-else-if="loading" class="strategy-empty">加载中...</div>
    <div v-else-if="error" class="strategy-error">{{ error }}</div>
    <div v-else class="strategy-empty">
      暂无策略
      <p class="hint">在对话中输入"保存策略 [名称]"来创建</p>
    </div>
  </section>
</template>

<style scoped>
.strategy-panel {
  width: 280px;
  min-width: 280px;
  background: #fff;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.strategy-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.strategy-header h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #0f172a;
}

.strategy-actions {
  display: flex;
  gap: 0.25rem;
}

.icon-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.icon-btn:hover {
  color: #0f172a;
}

.strategy-list {
  list-style: none;
  margin: 0;
  padding: 0.75rem;
  overflow-y: auto;
  flex: 1;
}

.strategy-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
  transition: border-color 0.15s;
}

.strategy-item.active {
  border-color: #0f172a;
  background: #f8fafc;
}

.strategy-name {
  font-weight: 500;
  font-size: 0.875rem;
  color: #0f172a;
}

.strategy-desc {
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
  line-height: 1.4;
}

.activate-btn {
  flex-shrink: 0;
  background: #f1f5f9;
  color: #64748b;
  border: none;
  border-radius: 0.375rem;
  padding: 0.375rem 0.625rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.activate-btn:hover {
  background: #e2e8f0;
}

.activate-btn.activated {
  background: #0f172a;
  color: #fff;
}

.delete-btn {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.delete-btn:hover {
  color: #ef4444;
}

.strategy-empty,
.strategy-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  font-size: 0.875rem;
  color: #94a3b8;
  text-align: center;
}

.strategy-error {
  color: #ef4444;
}

.hint {
  font-size: 0.75rem;
  color: #cbd5e1;
  margin-top: 0.5rem;
}
</style>
