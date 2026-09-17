<!-- ListPage.vue — 骨架 A·列表页(F-templates:标题+工具条 → Tabs → 表格)。
     适用于场景库 / 执行历史 / 认证管理 / 传递字段 / 用户管理等。
     Phase 2 各批次迁移视图时采用;chrome(侧边栏)由 App.vue 统一供,
     本组件只管内容区分区,不自带头部导航/返回。 -->
<template>
  <div class="mx-auto max-w-[1200px] px-4 py-6">
    <header>
      <div class="flex items-center justify-between gap-3">
        <h1 class="m-0 text-display font-semibold text-signal-ink">{{ title }}</h1>
        <div class="flex items-center gap-2"><slot name="actions" /></div>
      </div>
      <p v-if="subtitle || $slots.subtitle" class="mb-0 mt-1 text-caption text-muted-foreground">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </header>

    <div v-if="$slots.tabs" class="mt-4"><slot name="tabs" /></div>
    <div v-if="$slots.toolbar" class="mt-3 flex flex-wrap items-center gap-2"><slot name="toolbar" /></div>

    <div class="mt-3"><slot /></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>
