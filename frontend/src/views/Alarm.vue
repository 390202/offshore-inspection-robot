<template>
  <Workspace title="泄漏监测与告警" eyebrow="DETECTION & RESPONSE" subtitle="阈值状态 · 复检确认 · 处置记录">
    <template #actions><el-button :icon="Refresh" :loading="refreshing" @click="refresh">刷新记录</el-button></template>
    <SensorStrip />
    <div class="toolbar"><div class="toolbar-fields"><el-input v-model="query" :prefix-icon="Search" placeholder="搜索位置或告警 ID" clearable style="width:240px" /><el-select v-model="status" placeholder="全部状态" clearable style="width:150px"><el-option v-for="item in ['未处置','已确认','处置中','已归档']" :key="item" :label="item" :value="item" /></el-select></div><span class="subtle">共 {{ filtered.length }} 条记录</span></div>
    <div class="alarm-layout"><section class="alarm-records"><div class="section-heading"><div><h2>告警记录</h2></div><span class="tiny-label">LATEST FIRST</span></div><div v-if="!filtered.length" class="empty-state"><el-icon><DocumentChecked /></el-icon><strong>{{ alarms.length ? '未找到匹配记录' : '暂无告警记录' }}</strong></div><button v-for="item in filtered" :key="item.id" class="alarm-record" :class="{ selected: selected?.id === item.id }" @click="selectedId = item.id"><div><span class="pill" :class="item.status === '未处置' ? 'danger' : 'neutral'">{{ item.level }}</span><time>{{ item.time }}</time></div><strong>{{ item.location || '位置待确认' }}</strong><span>#{{ item.id }}<span>{{ item.status }}</span></span></button></section><section class="alarm-detail"><div class="section-heading"><div><h2>告警详情</h2></div><el-button :icon="Download" :disabled="!selected" @click="exportAlarm">导出记录</el-button></div><template v-if="selected"><div class="alarm-detail-title"><div><span class="eyebrow">ALARM #{{ selected.id }}</span><h3>{{ selected.location || '位置待确认' }}</h3></div><span class="pill" :class="selected.status === '未处置' ? 'danger' : 'success'">{{ selected.status }}</span></div><dl class="detail-list two-column"><div><dt>发生时间</dt><dd>{{ selected.time }}</dd></div><div><dt>分级结果</dt><dd>{{ selected.level }}</dd></div><div><dt>确认坐标</dt><dd>{{ selected.x_m != null && selected.y_m != null ? selected.x_m + ', ' + selected.y_m + ' m' : '待定位确认' }}</dd></div><div><dt>检测置信度</dt><dd>{{ selected.confidence != null ? selected.confidence + '%' : '--' }}</dd></div></dl><EvidencePanel index="" :images="selected.images || []" /><div class="subsection-heading">处置流程</div><div class="response-steps"><div v-for="(step, i) in ['记录生成','人工确认','复检与处置','结果归档']" :key="step" :class="{ complete: i <= currentStep }"><span>{{ String(i + 1).padStart(2,'0') }}</span><strong>{{ step }}</strong></div></div><div class="action-bar"><el-button :icon="Check" type="primary" :disabled="readOnly || selected.status !== '未处置' || !connected || busy" @click="act('confirm')">确认告警</el-button><el-button :icon="Promotion" :disabled="readOnly || selected.status !== '已确认' || !connected || busy" @click="act('dispatch')">提交处置任务</el-button><span class="subtle">{{ readOnly ? '当前角色只读' : '处置执行状态以现场反馈为准' }}</span></div></template><div v-else class="empty-state"><el-icon><Warning /></el-icon><strong>暂无可查看的告警</strong><span>保留确认、复检及现场证据记录</span></div></section></div>
  </Workspace>
</template>
<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, DocumentChecked, Download, Check, Promotion, Warning } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import SensorStrip from '../components/SensorStrip.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import { useTelemetry } from '../composables/useTelemetry'
import { downloadCsv } from '../utils/format'
import socket from '../utils/socket'
const { alarms, refresh, refreshing, connected } = useTelemetry()
const query = ref(''), status = ref(''), selectedId = ref(null), busy = ref(false)
const readOnly = localStorage.getItem('role') === '陆地指挥中心'
const filtered = computed(() => alarms.value.filter(a => (!status.value || a.status === status.value) && `${a.id} ${a.location}`.includes(query.value)))
const selected = computed(() => filtered.value.find(a => a.id === selectedId.value) || filtered.value[0])
const currentStep = computed(() => ['未处置', '已确认', '处置中', '已归档'].indexOf(selected.value?.status))
let timer
function act(action) {
  if (!selected.value || readOnly || !connected.value || busy.value) return
  busy.value = true
  socket.emit('handle_alarm', { alarmId: selected.value.id, action, username: localStorage.getItem('username') })
  ElMessage.info(action === 'confirm' ? '确认请求已提交' : '处置请求已提交，等待状态更新')
  timer = setTimeout(() => { busy.value = false; refresh() }, 2000)
}
function exportAlarm() { if (selected.value) downloadCsv('告警记录_' + selected.value.id, ['ID','时间','位置描述','等级','状态','置信度'], [[selected.value.id, selected.value.time, selected.value.location, selected.value.level, selected.value.status, selected.value.confidence]]) }
onBeforeUnmount(() => clearTimeout(timer))
</script>
