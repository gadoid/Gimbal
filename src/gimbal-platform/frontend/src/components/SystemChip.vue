<!-- SystemChip.vue — 系统标签 chip
     fin/logi/wms/mall/common 五种颜色,与主题色系一致。
-->
<template>
  <span class="sys-chip" :class="`tone-${tone}`">{{ label || sys }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ sys: string; label?: string }>()

const tone = computed(() => {
  switch (props.sys) {
    case 'fin':    return 'fin'
    case 'logi':   return 'logi'
    case 'wms':    return 'wms'
    case 'mall':   return 'mall'
    case 'common': return 'common'
    default:       return 'common'
  }
})
</script>

<style scoped>
.sys-chip {
  @apply text-micro font-semibold;
  display: inline-flex;
  align-items: center;
  padding: 0.125rem 0.5rem;
  font-family: var(--font-mono, monospace);
  border-radius: 0.25rem;
}

.tone-fin    { color: var(--accent); background: #eef2ff; border: 0.5px solid #c7d2fe; }
.tone-logi   { color: var(--sl-warn); background: #fef3c7; border: 0.5px solid #fbbf24; }
.tone-wms    { color: var(--sl-ok); background: #dcfce7; border: 0.5px solid #22c55e; }
.tone-mall   { color: #0e7490; background: #cffafe; border: 0.5px solid #06b6d4; }
.tone-common { color: var(--color-text-secondary); background: var(--surface-raised); border: 0.5px solid var(--color-border-tertiary); }

/* 夜面:fin/logi/wms/mall 四个色调是「白底硬编码 + 令牌文字」—— 文字
   在夜间翻成亮色,配白底看不清(framework 文章:服务卡片徽章、场景列表
   系统列均中招)。夜面底色换 dual-theme 软底同款深色调性底,文字提亮
   同色相、边框换深色同档,色相保持辨识"哪个系统"。common 全走令牌,
   自动翻转,无需覆写。 */
html[data-theme="dark"] .tone-fin    { color: #a5b4fc; background: #232329; border-color: #3a3a4a; }
html[data-theme="dark"] .tone-logi   { color: #fbbf24; background: #2d2210; border-color: #644f11; }
html[data-theme="dark"] .tone-wms    { color: #4ade80; background: #12291a; border-color: #1a4b2d; }
html[data-theme="dark"] .tone-mall   { color: #22d3ee; background: #0f2f38; border-color: #155e75; }
</style>
