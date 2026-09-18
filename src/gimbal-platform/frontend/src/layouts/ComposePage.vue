<!-- ComposePage.vue — 骨架 C·编排/表单页(F-templates:用例编排四步 /
     方案工作台;已确认收起侧边栏)。收拢顶条(品牌信号点 + 统一面包屑)
     由 App.vue 按 meta.chromeMode='collapsed' 供,本组件只管内容区:
     页头(title/actions)→ 步骤条区(steps slot)+ 主体 + 底部操作条
     (footer slot)。规范禁止自带返回发明。
     容器双档(样式归一):standard=1200(默认)/ wide=1480,取代旧 1100 单档。 -->
<template>
  <div
    class="mx-auto flex min-h-[calc(100vh-48px)] w-full flex-col px-4 pb-6 pt-5"
    :class="width === 'wide' ? 'max-w-[min(1480px,100%)]' : 'max-w-[min(1200px,100%)]'"
  >
    <header v-if="title || $slots.actions" class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h1 v-if="title" class="m-0 text-display font-semibold text-signal-ink">{{ title }}</h1>
      <div v-if="$slots.actions" class="flex items-center gap-2"><slot name="actions" /></div>
    </header>

    <div v-if="$slots.steps" class="mb-4"><slot name="steps" /></div>

    <div class="min-w-0 flex-1"><slot /></div>

    <footer v-if="$slots.footer" class="mt-4 flex items-center justify-between gap-3 border-t border-signal-line pt-3">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /** 页头标题(缺省则不渲染页头,兼容纯步骤流页) */
  title?: string
  /** 容器档位:standard=1200(默认)/ wide=1480(宽表格页) */
  width?: 'standard' | 'wide'
}>()
</script>
