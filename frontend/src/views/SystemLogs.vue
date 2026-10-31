<template>
  <Workspace title="系统操作日志" eyebrow="AUDIT TRAIL" subtitle="操作记录 · 任务提交 · 运行留痕">
    <template #actions><el-button :icon="Download" :disabled="!filtered.length" @click="exportLogs">导出记录</el-button><el-button :icon="Refresh" :loading="loading" @click="fetchLogs">刷新日志</el-button></template>
    <div class="toolbar"><div class="toolbar-fields"><el-input v-model="query" :prefix-icon="Search" placeholder="搜索操作人或详情" clearable style="width:260px" /><el-select v-model="action" clearable placeholder="全部操作类型" style="width:170px"><el-option v-for="value in actions" :key="value" :label="value" :value="value" /></el-select></div><span class="subtle">最近 100 条 · 匹配 {{ filtered.length }} 条</span></div>
    <el-alert v-if="error" title="日志读取失败，请稍后刷新" type="error" show-icon :closable="false" />
    <div class="table-section"><el-table v-loading="loading" :data="filtered" empty-text="暂无匹配的操作记录"><el-table-column prop="id" label="记录编号" width="100" /><el-table-column label="操作时间" min-width="190"><template #default="{ row }">{{ formatTime(row.created_at, true) }}</template></el-table-column><el-table-column prop="username" label="操作人" min-width="130" /><el-table-column label="操作类型" min-width="140"><template #default="{ row }"><span class="pill neutral">{{ row.action }}</span></template></el-table-column><el-table-column prop="details" label="操作详情" min-width="300" /></el-table></div>
  </Workspace>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import { formatTime, downloadCsv } from '../utils/format'
const logs = ref([]), loading = ref(false), error = ref(false), query = ref(''), action = ref('')
let disposed = false
const actions = computed(() => [...new Set(logs.value.map(item => item.action))])
const filtered = computed(() => logs.value.filter(item => (!action.value || item.action === action.value) && `${item.username} ${item.details}`.includes(query.value)))
async function fetchLogs() {
  if (loading.value) return
  loading.value = true; error.value = false
  try {
    const response = await fetch('/api/logs', { signal: AbortSignal.timeout(5000) })
    if (!response.ok) throw new Error('logs')
    const result = await response.json()
    if (!Array.isArray(result.data)) throw new Error('format')
    if (!disposed) logs.value = result.data
  } catch { if (!disposed) error.value = true }
  finally { loading.value = false }
}
function exportLogs() { downloadCsv('系统操作日志', ['ID','时间','操作人','类型','详情'], filtered.value.map(item => [item.id, item.created_at, item.username, item.action, item.details])) }
onMounted(fetchLogs)
onBeforeUnmount(() => { disposed = true })
</script>
