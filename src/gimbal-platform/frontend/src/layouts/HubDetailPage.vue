<!-- HubDetailPage.vue — 骨架 B·枢纽/详情页(F-templates:题头(粗线) →
     摘要 → 章节式正文)。当前唯一场景:场景详情 /scenarios/:id/detail
     (枢纽页,向编排/方案/断言/数据集辐射)。chrome 由 App.vue 统一供。 -->
<template>
  <div class="hub-page">
    <header class="hub-head">
      <div class="hub-title-row">
        <h1 class="hub-title">{{ title }}</h1>
        <div class="hub-actions"><slot name="actions" /></div>
      </div>
      <div class="hub-summary"><slot name="summary" /></div>
    </header>

    <section class="hub-body">
      <slot />
    </section>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<style scoped>
.hub-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.hub-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hub-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #10151c;
}

.hub-summary {
  margin-top: 8px;
  padding-bottom: 12px;
  border-bottom: 2px solid #2f6fed;
}

.hub-body {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
