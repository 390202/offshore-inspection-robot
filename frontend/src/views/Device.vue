<template>
  <Workspace title="设备状态与运维" eyebrow="ASSETS & MAINTENANCE" subtitle="巡检装备 · 部件状态 · 能源补给">
    <template #actions><router-link to="/track"><el-button :icon="Location">查看运动历程</el-button></router-link></template>
    <div class="asset-profile"><div class="robot-image"><img src="/robot-platform.png" alt="ArmPi Pro 麦轮机械臂小车参考原型" /><span>ArmPi Pro 底盘原型</span></div><div class="asset-profile-copy"><div class="eyebrow">INSPECTION UNIT / A</div><h2>巡检小车 A</h2><p>麦轮底盘 · 机械臂 · 三路气体检测</p><span class="pill" :class="fresh ? 'success' : 'neutral'">{{ fresh ? '气体采集节点数据在线' : '等待采集节点上报' }}</span><dl class="asset-meta"><div><dt>采集控制器</dt><dd>STM32F103C8T6</dd></div><div><dt>无线通信</dt><dd>DX-LR22-D</dd></div><div><dt>气体传感器</dt><dd>MQ-5 / MQ-6 / MQ-8</dd></div><div><dt>设备编号</dt><dd>{{ reading?.device_id ?? '--' }}</dd></div></dl></div><div class="asset-energy"><span class="tiny-label">ENERGY STATUS</span><el-icon><Lightning /></el-icon><strong>电量待接入</strong><span>充电状态 --</span><div class="energy-line"></div><span>剩余续航 --</span></div></div>
    <div class="section-heading"><div><span class="section-index">01</span><h2>部件接入与健康状态</h2></div><span class="subtle">健康评级以设备实测为准</span></div><div class="health-table"><el-table :data="components"><el-table-column label="部件" min-width="180"><template #default="{ row }"><div class="component-name"><el-icon><component :is="row.icon" /></el-icon>{{ row.name }}</div></template></el-table-column><el-table-column prop="items" label="监测项" min-width="240" /><el-table-column label="接入状态" min-width="140"><template #default="{ row }"><span class="pill" :class="row.active && fresh ? 'success' : 'neutral'">{{ row.active ? (fresh ? '数据在线' : '等待上报') : '待接入' }}</span></template></el-table-column><el-table-column prop="result" label="当前记录" min-width="180" /></el-table></div>
    <div class="device-bottom"><section><div class="section-heading"><div><span class="section-index">02</span><h2>双机轮换与充电</h2></div></div><div class="fleet-row"><span class="fleet-icon"><el-icon><Van /></el-icon></span><div><strong>巡检小车 B</strong><span>接替巡检 · 待机与轮换</span></div><span class="pill neutral">待接入</span></div><div class="fleet-row"><span class="fleet-icon"><el-icon><Lightning /></el-icon></span><div><strong>无线充电基站</strong><span>停靠对位 · 补能与记录</span></div><span class="pill neutral">待接入</span></div></section><section><div class="section-heading"><div><span class="section-index">03</span><h2>维护与版本记录</h2></div></div><dl class="detail-list"><div><dt>设备故障记录</dt><dd>待接入</dd></div><div><dt>车载固件版本</dt><dd>待设备上报</dd></div><div><dt>监控界面版本</dt><dd>2026.10.11</dd></div><div><dt>最近传感器记录</dt><dd>{{ formatTime(reading?.created_at, true) }}</dd></div></dl></section></div>
  </Workspace>
</template>
<script setup>
import { computed, markRaw } from 'vue'
import { Location, Lightning, Van, Odometer, VideoCamera, Cpu, Connection, SetUp } from '@element-plus/icons-vue'
import Workspace from '../components/Workspace.vue'
import { useTelemetry } from '../composables/useTelemetry'
import { formatTime } from '../utils/format'
const { fresh, reading } = useTelemetry()
const components = computed(() => [
  { name: '三路气体传感器', icon: Odometer, items: 'MQ-5 / MQ-6 / MQ-8 数字量阈值状态', active: true, result: reading.value ? '最近帧 #' + reading.value.sequence : '--' },
  { name: 'LoRa 通信链路', icon: Connection, items: '数据上报时间、设备编号、帧序号', active: true, result: 'RSSI / SNR 待接入' },
  { name: '底盘与编码器', icon: Van, items: '四轮转动反馈、运动速度、累计里程', result: '--' },
  { name: '双光检测模组', icon: VideoCamera, items: '可见光、红外、融合分割结果', result: '--' },
  { name: '边缘计算节点', icon: Cpu, items: '推理状态、时延、温度、存储余量', result: '--' },
  { name: '机械臂与执行机构', icon: SetUp, items: '动作反馈、关节状态、处置结果', result: '--' }
].map(item => ({ ...item, icon: markRaw(item.icon) })))
</script>
