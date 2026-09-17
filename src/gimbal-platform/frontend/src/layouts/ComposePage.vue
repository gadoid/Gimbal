<!-- ComposePage.vue — 骨架 C·编排/表单页(F-templates:用例编排四步 /
     方案工作台;已确认收起侧边栏)。收拢顶条(品牌信号点 + 统一面包屑)
     由 App.vue 按 meta.chromeMode='collapsed' 供,本组件只管内容区:
     步骤条区(steps slot)+ 主体 + 底部操作条(footer slot)。批次 6
     迁移编排器/方案工作台/断言注册表时采用;规范禁止自带返回发明。 -->
<template>
  <div class="compose-page">
    <div v-if="$slots.steps" class="cp-steps"><slot name="steps" /></div>

    <div class="cp-body"><slot /></div>

    <footer v-if="$slots.footer" class="cp-footer">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.compose-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px 16px 24px;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 48px);
}

.cp-steps {
  margin-bottom: 16px;
}

.cp-body {
  flex: 1;
  min-width: 0;
}

.cp-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e1e5eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
