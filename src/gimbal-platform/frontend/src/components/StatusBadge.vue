<!-- StatusBadge.vue — PASS/FAIL/SKIP 三态徽章 -->
<template>
  <span class="badge" :class="`tone-${tone}`">
    <span class="dot" :class="`tone-${tone}`" />
    {{ status }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: 'PASS' | 'FAIL' | 'SKIP' | string }>()
const tone = computed(() => {
  switch (props.status) {
    case 'PASS': return 'green'
    case 'FAIL': return 'red'
    case 'SKIP': return 'amber'
    default:     return 'gray'
  }
})
</script>

<style scoped>
.badge {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  border-radius: 4px;
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}
.tone-green  { color: #15803d; background: #dcfce7; }
.tone-green .dot  { background: #15803d; }
.tone-red    { color: #b91c1c; background: #fce7e7; }
.tone-red .dot    { background: #b91c1c; }
.tone-amber  { color: #b45309; background: #fef3c7; }
.tone-amber .dot  { background: #b45309; }
.tone-gray   { color: #64748b; background: #f1f5f9; }
.tone-gray .dot   { background: #94a3b8; }
</style>
