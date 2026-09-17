<!-- ListPage.vue — 骨架 A·列表页(F-templates:标题+工具条 → Tabs → 表格)。
     适用于场景库 / 执行历史 / 认证管理 / 传递字段 / 用户管理等。
     Phase 2 各批次迁移视图时采用;chrome(侧边栏)由 App.vue 统一供,
     本组件只管内容区分区,不自带头部导航/返回。 -->
<template>
  <div class="list-page">
    <header class="lp-head">
      <div class="lp-title-row">
        <h1 class="lp-title">{{ title }}</h1>
        <div class="lp-actions"><slot name="actions" /></div>
      </div>
      <p v-if="$slots.subtitle" class="lp-subtitle"><slot name="subtitle" /></p>
    </header>

    <div v-if="$slots.tabs" class="lp-tabs"><slot name="tabs" /></div>
    <div v-if="$slots.toolbar" class="lp-toolbar"><slot name="toolbar" /></div>

    <div class="lp-body"><slot /></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<style scoped>
.list-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.lp-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.lp-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #10151c;
}

.lp-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.lp-tabs {
  margin-top: 16px;
}

.lp-toolbar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.lp-body {
  margin-top: 12px;
}
</style>
