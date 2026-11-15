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
  @apply text-micro font-bold;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.9375rem;
  padding: 0.125rem 0.375rem;
  font-family: var(--font-mono, monospace);
  border-radius: 0.625rem;
}
.p0 { color: #b91c1c; background: #fee2e2; }
.p1 { color: var(--sl-warn); background: #fef3c7; }
.p2 { color: var(--color-text-strong); background: var(--soft-neutral-bg); }
.p3 { color: var(--color-text-tertiary); background: var(--surface-raised); }

</style>
