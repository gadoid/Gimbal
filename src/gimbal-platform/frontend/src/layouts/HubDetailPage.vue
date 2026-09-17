<!-- HubDetailPage.vue — 骨架 B·枢纽/详情页(F-templates:题头(粗线) →
     摘要 → 章节式正文)。当前唯一场景:场景详情 /scenarios/:id/detail
     (枢纽页,向编排/方案/断言/数据集辐射)。chrome 由 App.vue 统一供。 -->
<template>
  <div class="mx-auto max-w-[1200px] px-4 py-6">
    <header>
      <div class="flex items-center justify-between gap-3">
        <h1 class="m-0 text-display font-bold text-signal-ink">{{ title }}</h1>
        <div class="flex items-center gap-2"><slot name="actions" /></div>
      </div>
      <div class="summary mt-2 border-b-2 border-signal pb-3"><slot name="summary" /></div>
    </header>

    <section class="mt-4 flex flex-col gap-4">
      <slot />
    </section>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>
