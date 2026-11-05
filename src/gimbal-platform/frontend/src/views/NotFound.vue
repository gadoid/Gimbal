<!-- NotFound.vue — 路由兜底 404(2026-11-05 前端评审 P2-5)。
     此前任何坏深链(如后端通知里拼错的地址)都落空白页,用户无从判断
     是加载中还是走错了;兜底路由给出明确说法 + 回工作台出口,并把
     原始路径带出来方便反馈。 -->
<template>
  <ListPage title="页面不存在" icon="globe">
    <div class="flex flex-col items-center gap-4 py-16 text-center">
      <p class="m-0 text-body text-signal-ink/70">
        地址 <code class="rounded bg-signal-card px-1.5 py-0.5 font-mono text-[12px]">{{ path }}</code>
        没有对应的页面 — 可能是失效的链接,或路径输入有误。
      </p>
      <RouterLink
        to="/home"
        class="rounded-md border border-signal-line bg-signal-card px-4 py-1.5 text-body text-signal no-underline hover:bg-[#E7EFFF]"
      >回工作台</RouterLink>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'

const route = useRoute()
const path = computed(() => route.fullPath)
</script>
