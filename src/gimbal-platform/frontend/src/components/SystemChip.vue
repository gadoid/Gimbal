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
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  border-radius: 4px;
}

.tone-fin    { color: #4338ca; background: #eef2ff; border: 0.5px solid #c7d2fe; }
.tone-logi   { color: #b45309; background: #fef3c7; border: 0.5px solid #fbbf24; }
.tone-wms    { color: #15803d; background: #dcfce7; border: 0.5px solid #22c55e; }
.tone-mall   { color: #0e7490; background: #cffafe; border: 0.5px solid #06b6d4; }
.tone-common { color: #64748b; background: #f8fafc; border: 0.5px solid #e2e8f0; }
</style>
