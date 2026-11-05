<!-- ListPage.vue — 骨架 A·列表页(F-templates:标题+工具条 → Tabs → 表格)。
     适用于场景库 / 执行历史 / 认证管理 / 传递字段 / 用户管理等。
     Phase 2 各批次迁移视图时采用;chrome(侧边栏)由 App.vue 统一供,
     本组件只管内容区分区,不自带头部导航/返回。
     容器双档(样式归一):standard=1200(默认)/ wide=1480,流式
     max-w-[min(Npx,100%)];lead = 标题下、tabs 上的整宽导语区。
     2026-11-05 说明统一轮(与 scenario-lib/PageHead 同口径):页面说明
     文字(subtitle)收进标题旁圆圈问号的悬浮提示(.slib-q),不常驻;
     随数据变化的状态/计数走 meta(常驻 caption)。 -->
<template>
  <div
    class="mx-auto w-full px-4 pb-6 pt-14"
    :class="width === 'wide' ? 'max-w-[min(1480px,100%)]' : 'max-w-[min(1200px,100%)]'"
  >
    <header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2.5">
          <span v-if="icon" class="icon-badge" aria-hidden="true">
            <SlibIcon :name="icon" :size="15" />
          </span>
          <h1 class="m-0 text-display font-semibold text-signal-ink">{{ title }}</h1>
          <span v-if="subtitle" class="slib-q" :title="subtitle">?</span>
        </div>
        <div class="flex items-center gap-2"><slot name="actions" /></div>
      </div>
      <p v-if="meta" class="mb-0 mt-1 text-caption text-muted-foreground">{{ meta }}</p>
      <div v-if="$slots.lead" class="mt-3"><slot name="lead" /></div>
    </header>

    <div v-if="$slots.tabs" class="mt-4"><slot name="tabs" /></div>
    <div v-if="$slots.toolbar" class="mt-3 flex flex-wrap items-center gap-2"><slot name="toolbar" /></div>

    <div class="mt-3"><slot /></div>
  </div>
</template>

<script setup lang="ts">
import SlibIcon, { type SlibIconName } from '@/components/scenario-lib/SlibIcon.vue'

defineProps<{
  title: string
  /** 页面说明文字:圆圈问号悬浮展示,不常驻 */
  subtitle?: string
  /** 常驻状态行(统计 / 计数等随数据变化的信息),原副标位置 */
  meta?: string
  /** 页头图标(与侧栏同一颗;风格整理轮:每页一图标不重复)。 */
  icon?: SlibIconName
  /** 容器档位:standard=1200(默认)/ wide=1480(宽表格页) */
  width?: 'standard' | 'wide'
}>()
</script>
