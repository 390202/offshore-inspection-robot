<template>
  <Workspace title="运行总览" eyebrow="LIVE OPERATIONS" subtitle="燃油管道巡检 · 现场感知与运行态势">
    <template #actions><span class="pill" :class="fresh ? 'success' : 'neutral'"><i class="status-dot" :class="fresh ? 'green' : 'muted'"></i>{{ fresh ? '现场数据在线' : '等待现场数据' }}</span><el-button :icon="Download" @click="exportSnapshot">导出快照</el-button></template>
    <div class="overview-metrics"><div><span>气体阈值状态</span><strong :class="thresholdCount ? 'text-red' : ''">{{ reading ? thresholdCount : '--' }}<small>/ 3 路超阈值</small></strong></div><div><span>待归档告警</span><strong>{{ openAlarms.length }}<small>条记录</small></strong></div><div><span>定位采样点</span><strong>{{ points.length || '--' }}<small>{{ points.length ? '本次接收' : '待定位接入' }}</small></strong></div><div><span>双机协同</span><strong class="metric-label">待接入<small>备用车 / 充电基站</small></strong></div></div>
    <SensorStrip />
    <div class="overview-primary"><TrajectoryPanel :points="points" compact /><section class="alarm-overview"><div class="section-heading"><div><span class="section-index">03</span><h2>告警动态</h2></div><router-link to="/alarm" class="text-link">全部<el-icon><ArrowRight /></el-icon></router-link></div><div class="threshold-note" :class="{ danger: thresholdCount && fresh }"><el-icon><Warning v-if="thresholdCount && fresh" /><CircleCheck v-else-if="fresh" /><Clock v-else /></el-icon><div><strong>{{ !fresh ? '等待新的现场上报' : thresholdCount ? thresholdCount + ' 路传感器超过设定阈值' : '三路传感器均未超过设定阈值' }}</strong><span>{{ fresh ? '传感器阈值状态不等同于泄漏确认' : '最近记录保留供查阅' }}</span></div></div><div v-if="!alarms.length" class="empty-state small"><el-icon><DocumentChecked /></el-icon><strong>暂无告警记录</strong><span>现场告警将在此汇总</span></div><router-link v-for="alarm in alarms.slice(0, 4)" :key="alarm.id" to="/alarm" class="alarm-summary"><div><span class="pill" :class="alarm.status === '未处置' ? 'danger' : 'neutral'">{{ alarm.level }}</span><time>{{ alarm.time }}</time></div><strong>{{ alarm.location || '位置待确认' }}</strong><span>{{ alarm.status }}<el-icon><ArrowRight /></el-icon></span></router-link><div class="data-note">告警确认 · 复检 · 处置 · 留痕归档</div></section></div>
    <div class="overview-secondary"><EvidencePanel /><section class="fleet-overview"><div class="section-heading"><div><span class="section-index">05</span><h2>巡检装备</h2></div><router-link to="/device" class="text-link">设备详情<el-icon><ArrowRight /></el-icon></router-link></div><div class="fleet-row"><span class="fleet-icon"><el-icon><Van /></el-icon></span><div><strong>巡检小车 A</strong><span>气体采集节点</span></div><span class="pill" :class="fresh ? 'success' : 'neutral'">{{ fresh ? '数据在线' : '等待上报' }}</span></div><div class="fleet-row"><span class="fleet-icon"><el-icon><Van /></el-icon></span><div><strong>巡检小车 B</strong><span>双机轮换单元</span></div><span class="pill neutral">待接入</span></div><div class="fleet-row"><span class="fleet-icon"><el-icon><Lightning /></el-icon></span><div><strong>无线充电基站</strong><span>能源与补给</span></div><span class="pill neutral">待接入</span></div></section></div>
  </Workspace>
</template>
<script setup>
import { computed } from 'vue'
import { Download, ArrowRight, Warning, CircleCheck, Clock, DocumentChecked, Van, Lightning } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import SensorStrip from '../components/SensorStrip.vue'
import TrajectoryPanel from '../components/TrajectoryPanel.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import { useTelemetry, sensors } from '../composables/useTelemetry'
import { downloadCsv } from '../utils/format'
const { reading, fresh, thresholdCount, openAlarms, alarms, history } = useTelemetry()
const points = computed(() => {
  const latest = history.value.findLast(p => p.device_id === 1)
  return history.value.filter(p => p.device_id === 1 && p.frame_id === latest?.frame_id)
})
function exportSnapshot() {
  downloadCsv('现场传感器快照', ['传感器', '设备ID', '帧序号', '阈值状态', '接收时间', '数据时效'], sensors.map(sensor => [sensor.name, reading.value?.device_id, reading.value?.sequence, reading.value?.[sensor.key] === 1 ? '超阈值' : reading.value?.[sensor.key] === 0 ? '未超阈值' : '未接入', reading.value?.created_at, fresh.value ? '实时' : '非实时']))
}
</script>
