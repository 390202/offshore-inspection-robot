<template>
  <section class="evidence-section">
    <div class="section-heading"><div><span class="section-index">{{ index }}</span><h2>双光检测证据</h2></div><span class="subtle">{{ images.length ? '现场抓图' : '图像通道待接入' }}</span></div>
    <div class="evidence-grid"><div v-for="item in channels" :key="item.key" class="evidence-frame"><div class="evidence-label"><span>{{ item.name }}</span><span class="tiny-label">{{ item.code }}</span></div><div class="evidence-image"><img v-if="imageFor(item.key)" :src="imageFor(item.key)" :alt="item.name + '现场抓图'" /><div v-else class="evidence-empty"><el-icon><Picture /></el-icon><span>暂无现场图像</span></div></div></div></div>
  </section>
</template>
<script setup>
import { Picture } from '@element-plus/icons-vue'
const props = defineProps({ index: { type: String, default: '04' }, images: { type: Array, default: () => [] } })
const channels = [{ key: 'visible', name: '可见光', code: 'VISIBLE' }, { key: 'infrared', name: '红外', code: 'INFRARED' }, { key: 'fusion', name: '融合与分割掩膜', code: 'FUSION' }]
const imageFor = key => {
  const url = props.images.find(item => item.channel === key)?.url
  if (typeof url !== 'string') return null
  return /^(https?:\/\/|\/(?!\/))/.test(url) ? url : null
}
</script>
