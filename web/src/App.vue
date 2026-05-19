<script setup lang="ts">
import { ref } from 'vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ToolList from '@/components/ToolList.vue'
import StrategyManager from '@/components/StrategyManager.vue'
import ReportHistory from '@/components/ReportHistory.vue'

const currentView = ref<'chat' | 'reports'>('chat')

function switchView(view: 'chat' | 'reports') {
  currentView.value = view
}
</script>

<template>
  <div class="app-layout">
    <SessionSidebar :current-view="currentView" @switch-view="switchView" />
    <template v-if="currentView === 'chat'">
      <ChatPanel />
      <ToolList />
      <StrategyManager />
    </template>
    <ReportHistory v-else />
  </div>
</template>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    sans-serif;
  color: #1e293b;
  background: #f8fafc;
}

* {
  box-sizing: border-box;
}

.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}
</style>
