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
</style>
