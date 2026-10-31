<template>
  <div class="workspace">
    <aside class="sidebar">
      <router-link to="/dashboard" class="brand"><span class="brand-symbol"><el-icon><Compass /></el-icon></span><span><strong>海上平台巡检</strong><small>OFFSHORE OPERATIONS</small></span></router-link>
      <div class="site-label"><span class="status-dot" :class="fresh ? 'green' : 'muted'"></span>本地监控中心<span class="site-code">LOCAL</span></div>
      <div class="navigation-label">巡检工作空间</div>
      <nav aria-label="主导航">
        <router-link v-for="item in navigation" :key="item.path" :to="item.path" class="nav-link"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><el-icon class="nav-arrow"><ArrowRight /></el-icon></router-link>
      </nav>
      <div class="sidebar-bottom"><div class="comm-status" :class="{ offline: !connected }"><span class="status-dot" :class="connected ? 'green' : 'amber'"></span>{{ connected ? '实时通道已连接' : '实时通道重连中' }}</div><div class="sidebar-version">海上平台 · 燃油管道巡检</div><button class="logout" @click="logout"><el-icon><SwitchButton /></el-icon>退出登录</button></div>
    </aside>
    <main class="workspace-main">
      <header class="workspace-header"><div class="breadcrumb">监控中心<el-icon><ArrowRight /></el-icon><span>{{ title }}</span></div><div class="header-right"><span class="header-date">{{ formatTime(now, true) }}</span><span class="user-avatar"><el-icon><User /></el-icon></span><div class="user-info"><strong>{{ username }}</strong><small>{{ role }}</small></div></div></header>
      <div class="page-body"><div class="page-heading"><div><div class="eyebrow">{{ eyebrow }}</div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div><div class="heading-actions"><slot name="actions" /></div></div><slot /></div>
      <footer class="workspace-footer"><span>海上平台智能巡检系统</span><span><i class="status-dot" :class="fresh ? 'green' : 'muted'"></i>{{ fresh ? '传感器数据更新中' : '等待设备上报' }}<span class="footer-separator">/</span>本地部署</span></footer>
    </main>
  </div>
</template>
<script setup>
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Compass, DataAnalysis, Warning, Setting, Location, List, Document, SwitchButton, ArrowRight, User } from '@element-plus/icons-vue'
import { useTelemetry } from '../composables/useTelemetry'
import { formatTime } from '../utils/format'
import socket from '../utils/socket'
defineProps({ title: String, subtitle: String, eyebrow: { type: String, default: 'OPERATIONS WORKSPACE' } })
const { now, connected, fresh } = useTelemetry()
const router = useRouter()
const username = localStorage.getItem('username') || '运维人员'
const role = localStorage.getItem('role') || '运维人员'
const navigation = [
  { path: '/dashboard', label: '运行总览', icon: DataAnalysis },
  { path: '/alarm', label: '泄漏监测与告警', icon: Warning },
  { path: '/track', label: '运动历程与定位', icon: Location },
  { path: '/device', label: '设备状态与运维', icon: Setting },
  { path: '/task', label: '巡检任务与配置', icon: List },
  { path: '/logs', label: '系统操作日志', icon: Document }
]
async function logout() {
  try {
    await ElMessageBox.confirm('确定退出当前监控工作台？', '退出登录', { confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning' })
    socket.disconnect()
    for (const key of ['token', 'username', 'role']) localStorage.removeItem(key)
    router.push('/')
  } catch { /* Cancel leaves the current session open. */ }
}
</script>
