<template>
  <section class="trajectory-section">
    <div class="section-heading"><div><span class="section-index">02</span><h2>{{ compact ? '小车实际运动历程' : '平面运动轨迹' }}</h2><span class="pill" :class="live ? 'success' : 'neutral'">{{ points.length ? (live ? '位置更新中' : '最近轨迹') : '定位待接入' }}</span></div><div class="map-actions"><el-tooltip content="导入平台图纸"><el-button :icon="Upload" circle aria-label="导入平台图纸" @click="fileInput.click()" /></el-tooltip><el-tooltip content="适应轨迹范围"><el-button :icon="FullScreen" circle aria-label="适应轨迹范围" @click="fit" /></el-tooltip><router-link v-if="compact" to="/track" class="text-link">完整历程<el-icon><ArrowRight /></el-icon></router-link></div></div>
    <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="importMap" />
    <div class="map-status-line"><span><i class="line-key"></i>实测运动轨迹</span><span><i class="point-key"></i>最近位置</span><span class="map-reference">{{ mapImage ? '导入图纸 · 未标定' : '局部平面坐标' }}<span class="axis-unit">单位 m</span></span><el-button v-if="mapImage" text size="small" :icon="Close" @click="removeMap">移除图纸</el-button></div>
    <div class="map-stage" :class="{ compact }"><div ref="chartElement" class="trajectory-chart"></div><div v-if="!points.length" class="map-empty"><span class="empty-crosshair"><el-icon><Aim /></el-icon></span><strong>等待小车位置数据</strong><span>真实坐标接入后显示运动轨迹与里程</span><span class="empty-coordinate">X — &nbsp; / &nbsp; Y — &nbsp; / &nbsp; θ —</span></div><div class="map-north"><span>Y</span><el-icon><Top /></el-icon></div></div>
    <div class="trajectory-readout"><div><span>X 坐标</span><strong>{{ value(current?.x_m) }}<small>m</small></strong></div><div><span>Y 坐标</span><strong>{{ value(current?.y_m) }}<small>m</small></strong></div><div><span>车身朝向</span><strong>{{ value(current?.heading_deg, 1) }}<small>°</small></strong></div><div><span>本次接收里程</span><strong>{{ points.length > 1 ? distance.toFixed(2) : '--' }}<small>m</small></strong></div></div>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, GraphicComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { Upload, FullScreen, ArrowRight, Close, Aim, Top } from '@element-plus/icons-vue'
import { useTelemetry, pathDistance } from '../composables/useTelemetry'
echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, DataZoomComponent, GraphicComponent, CanvasRenderer])
const props = defineProps({ compact: Boolean, points: { type: Array, default: () => [] }, cursor: { type: Number, default: -1 } })
const { now } = useTelemetry()
const chartElement = ref(null), fileInput = ref(null), mapImage = ref('')
let chart, observer
const points = computed(() => props.points)
const current = computed(() => points.value[props.cursor >= 0 ? props.cursor : points.value.length - 1])
const live = computed(() => current.value && now.value - current.value.t < 15000)
const distance = computed(() => pathDistance(points.value))
const value = (number, places = 2) => Number.isFinite(number) ? number.toFixed(places) : '--'
function draw(reset = false) {
  if (!chart) return
  const data = props.cursor >= 0 ? points.value.slice(0, props.cursor + 1) : points.value
  const segments = []
  let segment = []
  data.forEach((point, index) => {
    const prev = data[index - 1]
    if (prev && (point.frame_id !== prev.frame_id || point.t - prev.t > 15000)) {
      segments.push(segment); segment = []
    }
    segment.push([point.x_m, point.y_m])
  })
  if (segment.length) segments.push(segment)
  const pad = values => {
    if (!values.length) return [-2, 12]
    const min = Math.min(...values), max = Math.max(...values)
    const margin = Math.max(1, (max - min) * 0.15)
    return [min - margin, max + margin]
  }
  const xs = pad(data.map(p => p.x_m)), ys = pad(data.map(p => p.y_m))
  const aspect = Math.max(1, chart.getWidth() - 84) / Math.max(1, chart.getHeight() - 78)
  const spanY = Math.max(ys[1] - ys[0], (xs[1] - xs[0]) / aspect)
  const midX = (xs[0] + xs[1]) / 2, midY = (ys[0] + ys[1]) / 2
  xs[0] = midX - spanY * aspect / 2; xs[1] = midX + spanY * aspect / 2
  ys[0] = midY - spanY / 2; ys[1] = midY + spanY / 2
  const zoom = reset ? [] : chart.getOption()?.dataZoom || []
  chart.setOption({
    animation: false,
    grid: { left: 54, right: 30, top: 30, bottom: 48, containLabel: false },
    tooltip: { trigger: 'item', formatter: params => `X: ${Number(params.value[0]).toFixed(2)} m<br/>Y: ${Number(params.value[1]).toFixed(2)} m` },
    xAxis: { type: 'value', name: 'X / m', nameLocation: 'middle', nameGap: 28, min: xs[0], max: xs[1], axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#85918f', fontSize: 10, showMinLabel: false, showMaxLabel: false, hideOverlap: true, formatter: value => Number(value.toFixed(2)).toString() }, splitLine: { lineStyle: { color: '#e4ebe8', type: 'dashed' } } },
    yAxis: { type: 'value', min: ys[0], max: ys[1], axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#85918f', fontSize: 10, showMinLabel: false, showMaxLabel: false, hideOverlap: true, formatter: value => Number(value.toFixed(2)).toString() }, splitLine: { lineStyle: { color: '#e4ebe8', type: 'dashed' } } },
    dataZoom: [{ type: 'inside', xAxisIndex: 0, filterMode: 'none', start: zoom[0]?.start ?? 0, end: zoom[0]?.end ?? 100 }, { type: 'inside', yAxisIndex: 0, filterMode: 'none', start: zoom[1]?.start ?? 0, end: zoom[1]?.end ?? 100 }],
    graphic: mapImage.value ? [{ id: 'drawing', type: 'image', left: 54, top: 30, z: -1, style: { image: mapImage.value, width: Math.max(1, chart.getWidth() - 84), height: Math.max(1, chart.getHeight() - 78), opacity: 0.3 } }] : [],
    series: [
      ...segments.map((part, i) => ({ id: 'path-' + i, type: 'line', showSymbol: false, data: part, lineStyle: { color: '#16836e', width: 3 } })),
      { id: 'current', type: 'scatter', data: current.value ? [[current.value.x_m, current.value.y_m]] : [], symbol: current.value?.heading_deg != null ? 'triangle' : 'circle', symbolRotate: (current.value?.heading_deg ?? 90) - 90, symbolSize: 17, itemStyle: { color: '#1b3c35', borderColor: '#fff', borderWidth: 2 }, z: 5 }
    ]
  }, { notMerge: true })
}
const fit = () => { chart?.dispatchAction({ type: 'dataZoom', start: 0, end: 100 }); draw(true) }
function removeMap() { if (mapImage.value) URL.revokeObjectURL(mapImage.value); mapImage.value = ''; draw() }
function importMap(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
    ElMessage.warning('请选择 10 MB 以内的 PNG、JPG 或 WebP 图纸'); event.target.value = ''; return
  }
  removeMap()
  mapImage.value = URL.createObjectURL(file)
  event.target.value = ''
  draw()
}
watch([points, () => props.cursor], () => draw(), { deep: true })
onMounted(() => {
  chart = echarts.init(chartElement.value)
  observer = new ResizeObserver(() => { chart.resize(); draw() })
  observer.observe(chartElement.value)
  draw()
})
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose(); if (mapImage.value) URL.revokeObjectURL(mapImage.value) })
</script>
