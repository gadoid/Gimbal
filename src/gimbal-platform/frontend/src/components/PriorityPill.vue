<!-- PriorityPill.vue — P0/P1/P2/P3 优先级药丸 -->
<template>
  <span v-if="priority !== null && priority !== undefined" class="pill" :class="`p${priority}`">P{{ priority }}</span>
  <span v-else class="muted">—</span>
</template>

<script setup lang="ts">
defineProps<{ priority: number | null | undefined }>()
</script>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 31px;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  border-radius: 10px;
}
.p0 { color: #b91c1c; background: #fee2e2; }
.p1 { color: #b45309; background: #fef3c7; }
.p2 { color: #475569; background: #f1f5f9; }
.p3 { color: #94a3b8; background: #f8fafc; }
.muted { color: var(--color-text-secondary); font-size: 11px; }
</style>
