<!-- ListPage.vue — 骨架 A·列表页(F-templates:标题+工具条 → Tabs → 表格)。
     适用于场景库 / 执行历史 / 认证管理 / 传递字段 / 用户管理等。
     Phase 2 各批次迁移视图时采用;chrome(侧边栏)由 App.vue 统一供,
     本组件只管内容区分区,不自带头部导航/返回。
     容器双档(样式归一):standard=1200(默认)/ wide=1480,流式
     max-w-[min(Npx,100%)];lead = 标题下、tabs 上的整宽导语区。 -->
<template>
  <div
    class="mx-auto w-full px-4 pb-6 pt-4"
    :class="width === 'wide' ? 'max-w-[min(1480px,100%)]' : 'max-w-[min(1200px,100%)]'"
  >
    <header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="m-0 text-display font-semibold text-signal-ink">{{ title }}</h1>
        <div class="flex items-center gap-2"><slot name="actions" /></div>
      </div>
      <p v-if="subtitle || $slots.subtitle" class="mb-0 mt-1 text-caption text-muted-foreground">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
      <div v-if="$slots.lead" class="mt-3"><slot name="lead" /></div>
    </header>

    <div v-if="$slots.tabs" class="mt-4"><slot name="tabs" /></div>
    <div v-if="$slots.toolbar" class="mt-3 flex flex-wrap items-center gap-2"><slot name="toolbar" /></div>

    <div class="mt-3"><slot /></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
  /** 容器档位:standard=1200(默认)/ wide=1480(宽表格页) */
  width?: 'standard' | 'wide'
}>()
</script>
