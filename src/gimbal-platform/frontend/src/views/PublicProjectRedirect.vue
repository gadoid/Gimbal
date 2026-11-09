<!-- PublicProjectRedirect.vue — M2a S7.1:旧「公共场景/公共用例集」
     深链兜底 —— 公共项目 id 是运行时数据,重定向组件挂载后解析再
     replace 到 /projects/:id?tab=…;解析失败回落项目列表(公共项目
     恒置顶)。路由 meta.tab 区分目标页签。 -->
<template>
  <p class="redirecting">正在跳转…</p>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listProjects } from '@/api/projects'

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  let target = '/projects'
  try {
    const pub = (await listProjects()).find((p) => p.kind === 'public')
    if (pub) {
      const tab = String(route.meta.tab ?? 'scenarios')
      // S7.3:/carry-config 退役 → 公共项目「配置」页签;?path= 深链
      // (键详情「默认值」来源 chip 的落点)原样透传
      const path = typeof route.query.path === 'string' ? route.query.path : ''
      target = `/projects/${pub.id}?tab=${tab}${path ? `&path=${encodeURIComponent(path)}` : ''}`
    }
  } catch { /* 回落项目列表 */ }
  await router.replace(target)
})
</script>

<style scoped>
.redirecting { padding: 2rem 1.5rem; color: #94a3b8; }
</style>
