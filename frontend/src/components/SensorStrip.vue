<template>
  <section class="sensor-section" aria-label="三路气体传感器">
    <div class="section-heading"><div><span class="section-index">01</span><h2>气体传感器实时监测</h2><span class="pill" :class="fresh ? 'success' : 'neutral'">{{ fresh ? '实测数据' : '等待更新' }}</span></div><el-tooltip content="刷新传感器数据"><el-button :icon="Refresh" circle :loading="refreshing" aria-label="刷新传感器数据" @click="refresh" /></el-tooltip></div>
    <div class="sensor-grid">
      <article v-for="sensor in sensors" :key="sensor.key" class="sensor-card" :class="{ 'sensor-alert': reading?.[sensor.key] === 1, 'sensor-stale': !fresh }">
        <div class="sensor-card-top"><span class="sensor-channel">{{ sensor.channel }}</span><span class="sensor-glyph"><el-icon><Odometer /></el-icon></span></div>
        <div class="sensor-title"><h3>{{ sensor.name }}</h3><span>{{ sensor.label }}</span></div>
        <div class="sensor-result"><span class="status-dot" :class="!fresh ? 'muted' : (reading?.[sensor.key] === 1 ? 'red' : 'green')"></span><strong>{{ stateLabel(sensor) }}</strong><span class="sensor-do">DO {{ reading?.[sensor.key] === 1 ? 'LOW' : reading?.[sensor.key] === 0 ? 'HIGH' : '--' }}</span></div>
        <div class="sensor-bottom"><span>数字量 · 阈值检测</span><span>{{ fresh ? '实时' : reading ? '最近记录' : '未接入' }}</span></div>
      </article>
    </div>
    <div class="sensor-receipt"><span class="receipt-status"><i class="status-dot" :class="fresh ? 'green' : 'amber'"></i>{{ apiError ? '数据接口暂不可用' : fresh ? 'LoRa 数据持续接收' : reading ? '上报超时，显示最近记录' : '等待 LoRa 设备上报' }}</span><span>设备 {{ reading ? String(reading.device_id).padStart(2, '0') : '--' }}</span><span class="frame-sequence">帧序号：{{ reading?.sequence ?? '--' }}</span><span class="mq-received">最近接收 {{ formatTime(reading?.created_at, true) }}</span></div>
  </section>
</template>
<script setup>
import { Refresh, Odometer } from '@element-plus/icons-vue'
import { useTelemetry, sensors } from '../composables/useTelemetry'
import { formatTime } from '../utils/format'
const { reading, fresh, apiError, refresh, refreshing } = useTelemetry()
function stateLabel(sensor) {
  if (!reading.value || ![0, 1].includes(reading.value[sensor.key])) return '等待数据'
  return reading.value[sensor.key] === 1 ? '超过设定阈值' : '未超过设定阈值'
}
</script>
