import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import socket from '../utils/socket'

const now = ref(Date.now())
const connected = ref(socket.connected)
const reading = ref(null)
const alarms = ref([])
const apiError = ref(false)
const refreshing = ref(false)
const history = ref([])
let users = 0
let clock, poll, pending
let generation = 0

export const sensors = [
  { name: 'MQ-5', key: 'mq5_state', label: '可燃气体通道', channel: 'CH.01' },
  { name: 'MQ-6', key: 'mq6_state', label: '液化气体通道', channel: 'CH.02' },
  { name: 'MQ-8', key: 'mq8_state', label: '氢气通道', channel: 'CH.03' }
]

function receiveReading(data) {
  if (!data || !Number.isFinite(Number(data.id))) return
  if (reading.value && Number(data.id) < Number(reading.value.id)) return
  reading.value = { ...data, mq5_state: data.mq5_state ?? data.mq3_state }
}

// Only measured position messages enter the trajectory; device_update is a simulator.
export function receivePosition(data) {
  const sources = ['encoder_imu', 'uwb', 'visual', 'gnss']
  if (!data || data.valid !== true || !sources.includes(data.source) ||
      typeof data.frame_id !== 'string' || !data.frame_id.trim() ||
      !Number.isFinite(data.x_m) || !Number.isFinite(data.y_m) ||
      !Number.isInteger(data.device_id) || data.device_id < 0 || data.device_id > 255) return
  const timestamp = Date.parse(data.timestamp)
  if (!Number.isFinite(timestamp) || timestamp > Date.now() + 5000) return
  const last = history.value.findLast(point => point.device_id === data.device_id)
  if (last && timestamp <= last.t) return
  history.value = [...history.value, {
    ...data, t: timestamp,
    heading_deg: Number.isFinite(data.heading_deg) ? data.heading_deg : null,
    speed_mps: Number.isFinite(data.speed_mps) && data.speed_mps >= 0 ? data.speed_mps : null
  }].slice(-2000)
}

async function refresh() {
  if (pending) return pending
  const current = generation
  refreshing.value = true
  pending = Promise.allSettled([
    fetch('/api/lora/latest', { cache: 'no-store', signal: AbortSignal.timeout(5000) })
      .then(async response => {
        if (!response.ok) throw new Error('sensor request')
        const result = await response.json()
        if (result.code !== 200) throw new Error('sensor response')
        if (current === generation && users) { receiveReading(result.data); apiError.value = false }
      }).catch(() => { if (current === generation && users) apiError.value = true }),
    fetch('/api/alarms', { cache: 'no-store', signal: AbortSignal.timeout(5000) })
      .then(async response => {
        if (!response.ok) throw new Error('alarm request')
        const result = await response.json()
        if (current === generation && users && Array.isArray(result.data)) alarms.value = result.data.map(normalizeAlarm)
      })
  ]).finally(() => { pending = null; refreshing.value = false })
  return pending
}
const onConnect = () => { connected.value = true; refresh() }
const onDisconnect = () => { connected.value = false }
function normalizeAlarm(alarm) {
  return { ...alarm, status: ({ '未处理': '未处置', '已处理': '已归档' })[alarm.status] || alarm.status }
}
const onAlarm = data => {
  if (!alarms.value.some(item => item.id === data.id)) alarms.value.unshift(normalizeAlarm(data))
}
const onAlarmStatus = data => {
  const alarm = alarms.value.find(item => item.id === data.id)
  if (alarm) alarm.status = normalizeAlarm(data).status
}

export function useTelemetry() {
  const age = computed(() => reading.value ? Math.max(0, (now.value - Date.parse(reading.value.created_at)) / 1000) : Infinity)
  const fresh = computed(() => age.value < 15 && !apiError.value)
  const thresholdCount = computed(() => sensors.filter(sensor => reading.value?.[sensor.key] === 1).length)
  const openAlarms = computed(() => alarms.value.filter(item => item.status !== '已归档'))
  onMounted(() => {
    users++
    if (users > 1) return
    generation++
    now.value = Date.now()
    connected.value = socket.connected
    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('lora_update', receiveReading)
    socket.on('position_update', receivePosition)
    socket.on('new_alarm', onAlarm)
    socket.on('alarm_status_update', onAlarmStatus)
    clock = setInterval(() => { now.value = Date.now() }, 1000)
    poll = setInterval(refresh, 5000)
    refresh()
    if (!socket.connected) socket.connect()
  })
  onBeforeUnmount(() => {
    users--
    if (users) return
    generation++
    clearInterval(clock)
    clearInterval(poll)
    socket.off('connect', onConnect)
    socket.off('disconnect', onDisconnect)
    socket.off('lora_update', receiveReading)
    socket.off('position_update', receivePosition)
    socket.off('new_alarm', onAlarm)
    socket.off('alarm_status_update', onAlarmStatus)
  })
  return { now, connected, reading, alarms, history, age, fresh, thresholdCount, openAlarms, apiError, refreshing, refresh }
}

export function pathDistance(points) {
  return points.reduce((sum, point, index) => {
    const previous = points[index - 1]
    if (!previous || point.device_id !== previous.device_id || point.frame_id !== previous.frame_id || point.t - previous.t > 15000) return sum
    return sum + Math.hypot(point.x_m - previous.x_m, point.y_m - previous.y_m)
  }, 0)
}
