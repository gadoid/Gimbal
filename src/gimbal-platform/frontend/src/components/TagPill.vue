<template>
  <span :class="`tag-pill ${tone}`">{{ label }}</span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    tone?: 'default' | 'accent'
  }>(),
  {
    tone: 'default',
  },
)
</script>

<style scoped>
.tag-pill {
  @apply text-micro;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 0.125rem 0.5rem;
  overflow: hidden;
  color: #5b21b6;
  white-space: nowrap;
  text-overflow: ellipsis;
  background: #ede9fe;
  border-radius: 0.75rem;
}

.tag-pill.accent {
  color: var(--accent);
  background: var(--accent-soft);
}
</style>
