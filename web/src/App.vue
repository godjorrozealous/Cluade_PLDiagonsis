<script setup lang="ts">
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ToolList from '@/components/ToolList.vue'
import ReportPreview from '@/components/ReportPreview.vue'
import StrategyManager from '@/components/StrategyManager.vue'
</script>

<template>
  <div class="app-layout">
    <SessionSidebar />
    <ChatPanel />
    <ToolList />
    <ReportPreview />
    <StrategyManager />
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
