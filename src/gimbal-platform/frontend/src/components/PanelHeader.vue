<!-- PanelHeader.vue — card-stack tab 的小标题 (4 tab 共用). -->
<template>
  <div class="panel-header">
    <span class="icon" :aria-hidden="true">{{ icon }}</span>
    <div class="meta">
      <div class="eyebrow">{{ title }}</div>
      <div class="subtitle">{{ subtitle }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.panel-header {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-bottom: 10px;
  margin-bottom: 14px;
  border-bottom: 0.5px solid #e2e8f0;
}

.icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-size: 16px;
  background: #dbeafe;
  border-radius: 8px;
}

.eyebrow {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.subtitle {
  margin-top: 1px;
  color: var(--color-text-primary);
  font-size: 17px;
  font-weight: 500;
}
</style>