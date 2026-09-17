<!-- ComposePage.vue — 骨架 C·编排/表单页(F-templates:用例编排四步 /
     方案工作台;已确认收起侧边栏)。收拢顶条(品牌信号点 + 统一面包屑)
     由 App.vue 按 meta.chromeMode='collapsed' 供,本组件只管内容区:
     步骤条区(steps slot)+ 主体 + 底部操作条(footer slot)。批次 6
     迁移编排器/方案工作台/断言注册表时采用;规范禁止自带返回发明。 -->
<template>
  <div class="mx-auto flex min-h-[calc(100vh-48px)] max-w-[1100px] flex-col px-4 pb-6 pt-5">
    <div v-if="$slots.steps" class="mb-4"><slot name="steps" /></div>

    <div class="min-w-0 flex-1"><slot /></div>

    <footer v-if="$slots.footer" class="mt-4 flex items-center justify-between gap-3 border-t border-signal-line pt-3">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script setup lang="ts"></script>
