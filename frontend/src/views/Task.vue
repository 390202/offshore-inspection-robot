<template>
  <Workspace title="巡检任务与配置" eyebrow="MISSION PLANNING" subtitle="巡检排期 · 路线分配 · 双机轮换">
    <template #actions><span class="pill neutral">{{ readOnly ? '陆地指挥中心 · 只读' : '本机任务草稿' }}</span><el-button type="primary" :icon="Plus" :disabled="readOnly" @click="dialog = true">新建任务</el-button></template>
    <div class="mission-banner"><el-icon><List /></el-icon><div><strong>巡检任务队列</strong><span>任务下发至中控服务，车辆实际执行结果待车载反馈接入</span></div><span>{{ tasks.length }} 项任务</span></div>
    <div class="table-section"><el-table :data="tasks" empty-text="暂无任务，等待创建巡检排期"><el-table-column prop="id" label="任务编号" min-width="150" /><el-table-column prop="route" label="巡检路线" min-width="160" /><el-table-column prop="car" label="分配小车" min-width="100" /><el-table-column label="计划时间" min-width="180"><template #default="{ row }">{{ row.scheduled ? formatTime(row.scheduled, true) : '手动下发' }}</template></el-table-column><el-table-column label="服务端状态" min-width="160"><template #default="{ row }"><span class="pill" :class="row.status === '服务端已接收' ? 'success' : 'neutral'">{{ row.status }}</span></template></el-table-column><el-table-column label="操作" width="110"><template #default="{ row }"><el-button text type="primary" :icon="Promotion" :disabled="readOnly || !connected || row.status === '等待服务端确认' || row.status === '服务端已接收'" @click="dispatch(row)">下发</el-button></template></el-table-column></el-table></div>
    <div class="task-config-layout"><section><div class="section-heading"><div><span class="section-index">01</span><h2>巡检参数草稿</h2></div><span class="pill neutral">仅保存至本机</span></div><el-form label-position="top" class="config-form"><el-form-item label="双光复检置信度阈值"><div class="slider-field"><el-slider v-model="config.confidence" :min="50" :max="100" :disabled="readOnly" /><span>{{ config.confidence }}%</span></div></el-form-item><el-form-item label="返航补能电量阈值"><el-input-number v-model="config.batteryThreshold" :min="10" :max="50" :disabled="readOnly" /><span class="field-unit">%</span></el-form-item><el-form-item label="轮换调度"><el-switch v-model="config.rotation" :disabled="readOnly" /><span class="field-unit">{{ config.rotation ? '启用计划' : '关闭计划' }}</span></el-form-item><el-button :icon="Check" :disabled="readOnly" @click="saveConfig">保存参数草稿</el-button></el-form></section><section><div class="section-heading"><div><span class="section-index">02</span><h2>通信与现场阈值</h2></div></div><dl class="detail-list"><div><dt>当前气体采集方式</dt><dd>三路数字量 DO</dd></div><div><dt>气体触发阈值</dt><dd>传感器模块电位器设定</dd></div><div><dt>LoRa 串口</dt><dd>9600 / 8N1</dd></div><div><dt>空中通信参数</dt><dd>由 LoRa 模块配置</dd></div><div><dt>轮换与回充执行反馈</dt><dd>待接入</dd></div></dl></section></div>
    <el-dialog v-model="dialog" title="新建巡检任务" width="480px" :close-on-click-modal="false"><el-form label-position="top"><el-form-item label="巡检路线"><el-select v-model="draft.route" placeholder="选择巡检路线" style="width:100%"><el-option label="主管道 A 段" value="主管道 A 段" /><el-option label="支线 B 段" value="支线 B 段" /></el-select></el-form-item><el-form-item label="执行小车"><el-select v-model="draft.car" placeholder="选择小车" style="width:100%"><el-option label="小车 A" value="小车 A" /><el-option label="小车 B" value="小车 B" /></el-select></el-form-item><el-form-item label="计划时间"><el-date-picker v-model="draft.scheduled" type="datetime" placeholder="留空为手动下发" style="width:100%" /></el-form-item></el-form><template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" :icon="Plus" @click="createTask">创建草稿</el-button></template></el-dialog>
  </Workspace>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, List, Promotion, Check } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import { useTelemetry } from '../composables/useTelemetry'
import { formatTime } from '../utils/format'
import socket from '../utils/socket'
const { connected } = useTelemetry()
const readOnly = localStorage.getItem('role') === '陆地指挥中心'
const owner = localStorage.getItem('username') || 'operator'
const taskKey = 'offshore-tasks-v1:' + owner, configKey = 'offshore-config-v1:' + owner
function stored(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) || fallback } catch { return fallback } }
const savedTasks = stored(taskKey, [])
const tasks = ref(Array.isArray(savedTasks) ? savedTasks : [])
const config = ref({ confidence: 85, batteryThreshold: 20, rotation: false, ...stored(configKey, {}) })
const dialog = ref(false), draft = ref({ route: '', car: '', scheduled: null })
const timers = new Map()
function persist() { localStorage.setItem(taskKey, JSON.stringify(tasks.value)) }
function createTask() {
  if (readOnly) return
  if (!draft.value.route || !draft.value.car) return ElMessage.warning('请选择路线和执行小车')
  tasks.value.push({ ...draft.value, id: 'T-' + Date.now().toString(36).toUpperCase(), status: '待下发' })
  persist(); dialog.value = false; draft.value = { route: '', car: '', scheduled: null }
  ElMessage.success('任务草稿已保存至本机')
}
function dispatch(row) {
  if (readOnly || !connected.value) return
  row.status = '等待服务端确认'; persist()
  socket.emit('dispatch_task', { taskId: row.id, route: row.route, car: row.car, username: owner })
  timers.set(row.id, setTimeout(() => { if (row.status === '等待服务端确认') { row.status = '未收到确认'; persist() } timers.delete(row.id) }, 10000))
}
function updateTask(data) {
  const row = tasks.value.find(t => t.id === data.taskId)
  if (row) { clearTimeout(timers.get(row.id)); timers.delete(row.id); row.status = '服务端已接收'; persist(); ElMessage.success('中控服务已接收任务') }
}
function saveConfig() { if (readOnly) return; localStorage.setItem(configKey, JSON.stringify(config.value)); ElMessage.success('参数草稿已保存至本机，尚未下发设备') }
onMounted(() => { for (const task of tasks.value) if (task.status === '等待服务端确认') task.status = '确认状态未知'; socket.on('task_status_update', updateTask) })
onBeforeUnmount(() => { socket.off('task_status_update', updateTask); for (const timer of timers.values()) clearTimeout(timer) })
</script>
