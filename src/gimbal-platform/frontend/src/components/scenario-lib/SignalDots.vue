<!-- SignalDots.vue — 执行健康趋势:近 5 次成功/失败小圆点。
     runs 由父级按「默认方案 / 公共原件」口径过滤后传入(旧→新)。 -->
<template>
  <span v-if="runs.length" class="signal-dots" :title="title">
    <i v-for="(r, i) in runs" :key="i" :class="tone(r)" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ runs: string[] }>()

const title = computed(() => `近 ${props.runs.length} 次执行`)

function tone(status: string): string {
  if (status === 'done') return 'ok'
  if (status === 'failed') return 'bad'
  return 'run'
}
</script>
