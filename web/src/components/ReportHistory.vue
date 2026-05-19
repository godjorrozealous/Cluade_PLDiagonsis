<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getReports } from '@/api/http'
import { renderMarkdown } from '@/utils/markdown'
import type { ReportItem } from '@/api/http'

const reports = ref<ReportItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const viewingReport = ref<ReportItem | null>(null)

async function loadReports() {
  loading.value = true
  error.value = null
  try {
    const data = await getReports()
    reports.value = data.reports
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

function handleView(report: ReportItem) {
  viewingReport.value = report
}

function handleClose() {
  viewingReport.value = null
}

function formatDate(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function confidenceClass(c: number): string {
  if (c >= 0.7) return 'confidence-high'
  if (c >= 0.4) return 'confidence-medium'
  return 'confidence-low'
}

onMounted(() => {
  loadReports()
})
</script>

<template>
  <section class="report-history">
    <header class="history-header">
      <h2>诊断报告历史</h2>
      <button class="refresh-btn" @click="loadReports" title="刷新">
        &#x21bb;
      </button>
    </header>

    <div v-if="loading" class="history-empty">加载中...</div>
    <div v-else-if="error" class="history-error">{{ error }}</div>
    <div v-else-if="reports.length === 0" class="history-empty">
      暂无诊断报告
    </div>

    <table v-else class="history-table">
      <thead>
        <tr>
          <th>线路名称</th>
          <th>故障类型</th>
          <th>置信度</th>
          <th>故障时间</th>
          <th>诊断时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in reports" :key="r.session_id">
          <td>{{ r.line_name }}</td>
          <td>{{ r.fault_type }}</td>
          <td>
            <span class="confidence-badge" :class="confidenceClass(r.confidence)">
              {{ Math.round(r.confidence * 100) }}%
            </span>
          </td>
          <td>{{ formatDate(r.fault_time) }}</td>
          <td>{{ formatDate(r.created_at) }}</td>
          <td>
            <button class="view-btn" @click="handleView(r)">查看报告</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Report detail modal -->
    <div v-if="viewingReport" class="report-overlay" @click.self="handleClose">
      <div class="report-detail">
        <header class="detail-header">
          <h3>{{ viewingReport.line_name }} - 诊断报告</h3>
          <button class="close-btn" @click="handleClose">&times;</button>
        </header>
        <div class="detail-body markdown-body" v-html="renderMarkdown(viewingReport.report)"></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.report-history {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  padding: 1.5rem 2rem;
  overflow-y: auto;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.history-header h2 {
  margin: 0;
  font-size: 1.25rem;
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
}

.refresh-btn:hover {
  color: #0f172a;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.history-table th,
.history-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  font-size: 0.875rem;
  border-bottom: 1px solid #e2e8f0;
}

.history-table th {
  background: #f1f5f9;
  font-weight: 600;
  color: #475569;
}

.history-table tr:hover {
  background: #f8fafc;
}

.confidence-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.confidence-high {
  background: #dcfce7;
  color: #166534;
}

.confidence-medium {
  background: #fef9c3;
  color: #854d0e;
}

.confidence-low {
  background: #fee2e2;
  color: #991b1b;
}

.view-btn {
  background: #0f172a;
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  cursor: pointer;
}

.view-btn:hover {
  opacity: 0.9;
}

.history-empty,
.history-error {
  text-align: center;
  padding: 3rem;
  color: #94a3b8;
}

.history-error {
  color: #ef4444;
}

.report-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 2rem;
}

.report-detail {
  background: #fff;
  border-radius: 0.75rem;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.detail-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  color: #94a3b8;
  cursor: pointer;
}

.close-btn:hover {
  color: #0f172a;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  font-size: 0.875rem;
  line-height: 1.7;
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
