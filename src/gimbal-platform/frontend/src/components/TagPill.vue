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
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 2px 8px;
  overflow: hidden;
  color: #5b21b6;
  font-size: 10.5px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
  text-overflow: ellipsis;
  background: #ede9fe;
  border-radius: 12px;
}

.tag-pill.accent {
  color: var(--accent);
  background: var(--accent-soft);
}
</style>
