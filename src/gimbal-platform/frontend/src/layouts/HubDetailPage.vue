<!-- HubDetailPage.vue — 骨架 B·枢纽/详情页(F-templates:题头(粗线) →
     摘要 → 章节式正文)。目标场景:执行详情 / 适配批次详情 / 场景详情
     (枢纽页,向编排/方案/断言/数据集辐射)。chrome 由 App.vue 统一供。
     容器双档(样式归一):standard=1200(默认)/ wide=1480;meta =
     题头 h1 下、粗线摘要上的小字行(时间对/endpoint·版本行)。 -->
<template>
  <div
    class="mx-auto w-full px-4 pb-6 pt-14"
    :class="width === 'wide' ? 'max-w-[min(1480px,100%)]' : 'max-w-[min(1200px,100%)]'"
  >
    <header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="m-0 text-display font-semibold text-signal-ink">{{ title }}</h1>
        <div class="flex items-center gap-2"><slot name="actions" /></div>
      </div>
      <div v-if="$slots.meta" class="mt-1 text-caption text-muted-foreground"><slot name="meta" /></div>
      <div class="summary mt-2 border-b-2 border-signal pb-3"><slot name="summary" /></div>
    </header>

    <section class="mt-4 flex flex-col gap-4">
      <slot />
    </section>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  /** 容器档位:standard=1200(默认)/ wide=1480(宽表格页) */
  width?: 'standard' | 'wide'
}>()
</script>
