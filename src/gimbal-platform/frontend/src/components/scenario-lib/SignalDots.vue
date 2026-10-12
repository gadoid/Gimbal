<!-- SignalDots.vue — 执行健康趋势:近 5 次成功/失败小圆点。
     runs 由父级按「默认方案 / 公共原件」口径过滤后传入(旧→新)。
     W21:pins(与 runs 同口径的修订钉定签名)非空时,相邻两次签名
     不同处的小圆点带「修订切换」环标 + title 说明。 -->
<template>
  <span v-if="runs.length" class="signal-dots" :title="title">
    <i v-for="(r, i) in runs" :key="i" :class="[tone(r), { switch: isSwitch(i) }]" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  runs: string[]
  /** 与 runs 同口径、同序的修订钉定签名(null = 该次未钉) */
  pins?: (string | null)[]
}>()

const title = computed(() => {
  const n = props.runs.length
  const switches = props.runs
    .map((_, i) => i).filter((i) => isSwitch(i)).length
  return switches
    ? `近 ${n} 次执行 · ${switches} 处修订切换`
    : `近 ${n} 次执行`
})

function tone(status: string): string {
  if (status === 'done') return 'ok'
  if (status === 'failed') return 'bad'
  return 'run'
}

/** 切换点 = 本次与上次钉定签名不同且本次已钉(窗首不标 — 无前次可比)。 */
function isSwitch(i: number): boolean {
  if (!props.pins || i === 0) return false
  const cur = props.pins[i] ?? null
  const prev = props.pins[i - 1] ?? null
  return cur !== prev && cur !== null
}
</script>

<style scoped>
/* W21 修订切换点:小圆点外圈蓝环 */
.signal-dots i.switch { box-shadow: 0 0 0 2px #3b82f6; }
</style>
