<!-- PageBack.vue — 二级页返回链接的全站唯一形态(风格整理轮 2026-10-10)。
     12.5px 灰、hover 变 accent 且箭头左移 2px;此前 SuiteManage/SuiteCompose/
     DebugConsole 各写一份,字号/颜色/位移三处漂移。 -->
<template>
  <RouterLink :to="to" class="pgback" :data-testid="testid">
    <span class="pgback-arrow">←</span>{{ label }}
  </RouterLink>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

withDefaults(defineProps<{
  to: string
  label?: string
  testid?: string
}>(), { label: '返回' })
</script>

<style scoped>
.pgback {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12.5px; color: var(--color-text-secondary);
  text-decoration: none; white-space: nowrap; padding-top: 4px;
  transition: color .15s ease;
}
.pgback:hover { color: #4338ca; }
.pgback-arrow {
  display: inline-block; transition: transform .15s ease;
}
.pgback:hover .pgback-arrow { transform: translateX(-2px); }
</style>
