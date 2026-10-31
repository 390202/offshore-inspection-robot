<template>
  <Workspace title="运动历程与定位" eyebrow="VEHICLE TRAJECTORY" subtitle="平面坐标 · 实际行驶轨迹 · 巡检记录">
    <template #actions><el-button :icon="Download" :disabled="!filtered.length" @click="exportTrack">导出轨迹</el-button></template>
    <div class="toolbar"><div class="toolbar-fields"><label>巡检小车<el-select v-model="deviceId" aria-label="选择巡检小车" style="width:150px"><el-option label="小车 A · 01" :value="1" /><el-option label="小车 B · 02" :value="2" /></el-select></label><label>记录日期<el-date-picker v-model="date" type="date" value-format="YYYY-MM-DD" placeholder="全部接收记录" style="width:170px" /></label></div><el-radio-group v-model="mode" @change="stopPlayback"><el-radio-button value="live">实时历程</el-radio-button><el-radio-button value="history">历史回放</el-radio-button></el-radio-group></div>
    <div class="track-layout"><div><TrajectoryPanel :points="filtered" :cursor="mode === 'history' ? cursor : -1" /><div class="playback-toolbar"><el-tooltip :content="playing ? '暂停回放' : '播放回放'"><el-button :icon="playing ? VideoPause : VideoPlay" circle :disabled="mode !== 'history' || filtered.length < 2" :aria-label="playing ? '暂停回放' : '播放回放'" @click="togglePlay" /></el-tooltip><el-slider v-model="cursor" :min="0" :max="Math.max(1, filtered.length - 1)" :disabled="mode !== 'history' || !filtered.length" :show-tooltip="false" aria-label="轨迹回放进度" /><span>{{ filtered.length ? formatTime(filtered[mode === 'history' ? cursor : filtered.length - 1]?.timestamp) : '--:--:--' }}</span><el-select v-model="playbackRate" aria-label="回放速度" style="width:85px" :disabled="mode !== 'history'"><el-option v-for="rate in [1, 2, 4]" :key="rate" :label="rate + '×'" :value="rate" /></el-select></div></div><aside class="track-details"><div class="section-heading"><div><h2>运动记录</h2></div><span class="tiny-label">SESSION</span></div><dl class="detail-list"><div><dt>定位来源</dt><dd>{{ sourceLabels[last?.source] || '待接入' }}</dd></div><div><dt>坐标系</dt><dd>{{ last?.frame_id || '--' }}</dd></div><div><dt>运动速度</dt><dd>{{ last?.speed_mps != null ? last.speed_mps.toFixed(2) + ' m/s' : '--' }}</dd></div><div><dt>轨迹点数</dt><dd>{{ filtered.length || '--' }}</dd></div><div><dt>最近位置时间</dt><dd>{{ formatTime(last?.timestamp) }}</dd></div><div><dt>数据范围</dt><dd>当前浏览会话</dd></div></dl><div class="subsection-heading">最近位置采样</div><div v-if="!filtered.length" class="empty-state small"><el-icon><Location /></el-icon><strong>暂无实测轨迹</strong><span>位置采集尚未接入</span></div><button v-for="point in filtered.slice(-5).reverse()" :key="point.t" class="position-record" @click="selectPoint(point)"><span>{{ formatTime(point.timestamp) }}</span><strong>{{ point.x_m.toFixed(2) }}, {{ point.y_m.toFixed(2) }} <small>m</small></strong><el-icon><ArrowRight /></el-icon></button></aside></div>
    <div class="section-heading"><div><span class="section-index">03</span><h2>检查点与检测留痕</h2></div><span class="subtle">检查点数据待接入</span></div><div class="checkpoint-empty"><el-icon><DocumentChecked /></el-icon><span>暂无带位置的检查点记录</span><span class="subtle">点位 · 时间 · 判定结果 · 现场证据</span></div>
    <EvidencePanel />
  </Workspace>
</template>
<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { Download, VideoPlay, VideoPause, Location, ArrowRight, DocumentChecked } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import TrajectoryPanel from '../components/TrajectoryPanel.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import { useTelemetry } from '../composables/useTelemetry'
import { formatTime, downloadCsv } from '../utils/format'
const { history } = useTelemetry()
const deviceId = ref(1), date = ref(null), mode = ref('live'), cursor = ref(0), playing = ref(false), playbackRate = ref(1)
const sourceLabels = { encoder_imu: '编码器 + IMU', uwb: 'UWB', visual: '视觉定位', gnss: 'GNSS' }
const filtered = computed(() => {
  const latest = history.value.findLast(p => p.device_id === deviceId.value)
  return history.value.filter(p => p.device_id === deviceId.value && p.frame_id === latest?.frame_id && (!date.value || localDate(p.t) === date.value))
})
const last = computed(() => filtered.value.at(-1))
let timer
function localDate(t) { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function stopPlayback() { clearTimeout(timer); playing.value = false }
function tick() {
  if (!playing.value) return
  if (cursor.value >= filtered.value.length - 1) return stopPlayback()
  const delta = filtered.value[cursor.value + 1].t - filtered.value[cursor.value].t
  timer = setTimeout(() => { cursor.value++; tick() }, Math.max(100, Math.min(3000, delta / playbackRate.value)))
}
function togglePlay() {
  if (playing.value) return stopPlayback()
  if (cursor.value >= filtered.value.length - 1) cursor.value = 0
  playing.value = true; tick()
}
function selectPoint(point) { stopPlayback(); mode.value = 'history'; cursor.value = filtered.value.findIndex(p => p.t === point.t) }
function exportTrack() { downloadCsv('小车实测轨迹', ['设备ID', '时间', 'X(m)', 'Y(m)', '朝向(度)', '速度(m/s)', '来源', '坐标系'], filtered.value.map(p => [p.device_id, p.timestamp, p.x_m, p.y_m, p.heading_deg, p.speed_mps, p.source, p.frame_id])) }
watch([deviceId, date], () => { stopPlayback(); cursor.value = 0 })
watch(filtered, () => { cursor.value = Math.min(cursor.value, Math.max(0, filtered.value.length - 1)) })
onBeforeUnmount(stopPlayback)
</script>
