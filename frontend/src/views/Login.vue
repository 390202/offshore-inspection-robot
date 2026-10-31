<template>
  <div class="login-page"><header class="login-header"><span class="brand-symbol"><el-icon><Compass /></el-icon></span><strong>海上平台巡检</strong><span>本地监控中心</span></header><main class="login-main"><div class="login-intro"><div class="eyebrow">OFFSHORE INSPECTION</div><h1>海上平台智能巡检系统</h1><p>燃油管道泄漏监测与巡检作业</p></div><div class="login-form"><div class="login-form-title"><h2>{{ register ? '创建运维账号' : '登录监控工作台' }}</h2><span class="pill neutral">本地部署</span></div><form @submit.prevent="submit"><label for="username">用户名</label><el-input id="username" v-model="username" :prefix-icon="User" placeholder="请输入用户名" autocomplete="username" size="large" /><label for="password">密码</label><el-input id="password" v-model="password" :prefix-icon="Lock" placeholder="请输入密码" type="password" show-password :autocomplete="register ? 'new-password' : 'current-password'" size="large" /><template v-if="register"><label for="confirm-password">确认密码</label><el-input id="confirm-password" v-model="confirm" :prefix-icon="Lock" placeholder="请再次输入密码" type="password" show-password autocomplete="new-password" size="large" /></template><el-button type="primary" native-type="submit" :loading="loading" class="login-submit">{{ register ? '注册账号' : '登录' }}<el-icon><ArrowRight /></el-icon></el-button></form><button class="login-toggle" @click="toggle">{{ register ? '已有账号，返回登录' : '创建运维账号' }}</button></div></main><footer class="login-footer"><span>现场感知 / 巡检定位 / 应急处置</span><span>海上平台 · 中控监控平台</span></footer></div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Compass, User, Lock, ArrowRight } from '@element-plus/icons-vue'
import socket from '../utils/socket'
const username = ref(''), password = ref(''), confirm = ref(''), register = ref(false), loading = ref(false)
const router = useRouter()
function toggle() { register.value = !register.value; password.value = ''; confirm.value = '' }
async function submit() {
  if (loading.value) return
  if (!username.value.trim() || !password.value) return ElMessage.warning('请输入用户名和密码')
  if (register.value && confirm.value !== password.value) return ElMessage.warning('两次输入的密码不一致')
  loading.value = true
  try {
    const response = await fetch(register.value ? '/api/register' : '/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }), signal: AbortSignal.timeout(10000)
    })
    const result = await response.json()
    if (!response.ok || result.code !== 200) throw new Error(result.message || '请求失败')
    if (register.value) { ElMessage.success('注册成功，请登录'); register.value = false; password.value = ''; confirm.value = ''; return }
    for (const key of ['token', 'username', 'role']) localStorage.setItem(key, result.data[key])
    socket.connect(); router.push('/dashboard')
  } catch (error) { ElMessage.error(error.message === 'Failed to fetch' ? '无法连接本地服务器' : error.message) }
  finally { loading.value = false }
}
</script>
