<!--
  StrategyForm.vue — 单条策略的通用表单(plate 策略语法 dim 驱动)

  数据来自 strategy-catalog 代理(plate /api/strategy/{kind}/full):
  detail.fields 是该 kind 的业务字段描述符,交给 FieldForm 渲染;
  base_fields(StrategyBase 公共字段)第一版不渲染,默认值生效。

  词汇适配:StrategyFieldDescView 无 source_kind(值来源语义对策略
  无意义),本组件补 independent 默认值以复用 FieldForm,不改其本体。

  变异语义:FieldForm @update:body 直接替换 props.strategy 引用对象
  的字段(与 Canvas 现有 extract 行为一致的直接变异模式)。
-->
<template>
  <div class="strategy-form" :class="`ph-${detail.phase}`">
    <div class="sf-head">
      <span class="sf-badge" :class="`ph-${detail.phase}`">{{ detail.label }}</span>
      <span class="sf-kind">{{ detail.kind }}</span>
      <button class="sf-del" title="删除这条策略" @click="emit('remove')">×</button>
    </div>
    <FieldForm
      :bindings="fieldBindings"
      :body="strategy"
      @update:body="onUpdateBody"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FieldForm from './FieldForm.vue'
import type { StrategyView, StrategyKindDetailView, StrategyFieldDescView, IOFieldBinding } from '@/types/plate'

const props = defineProps<{
  strategy: StrategyView
  detail: StrategyKindDetailView
}>()
const emit = defineEmits<{
  remove: []
}>()

/** 词汇适配:StrategyFieldDescView → FieldForm 需要的 IOFieldBinding 形状 */
const fieldBindings = computed<IOFieldBinding[]>(() =>
  props.detail.fields.map((f: StrategyFieldDescView) => ({
    ...f,
    example: null,
    source_kind: 'independent' as const,
  }))
)

function onUpdateBody(next: any) {
  // 直接变异 props.strategy 引用的对象(Canvas local reactive 数组的
  // 元素)—— 与 extract 行一致的既定模式;watch deep 会向上传播。
  Object.keys(next).forEach((k) => {
    ;(props.strategy as any)[k] = next[k]
  })
}
</script>

<style scoped>
.strategy-form {
  padding: 8px 10px;
  background: #fafbfc;
  border: 1.5px solid #e6e8ec;
  border-left-width: 3px;
  border-radius: 8px;
  margin-bottom: 6px;
}
/* phase 4 色左边框: before_request 橙 / after_request 绿 / verifying 紫 */
.strategy-form.ph-before_request { border-left-color: #f59e0b; }
.strategy-form.ph-after_request  { border-left-color: #10b981; }
.strategy-form.ph-verifying      { border-left-color: #7c3aed; }

.sf-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px;
}
.sf-badge {
  font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 4px;
}
.sf-badge.ph-before_request { background: #fef3c7; color: #92400e; }
.sf-badge.ph-after_request  { background: #d1fae5; color: #065f46; }
.sf-badge.ph-verifying      { background: #f3e8ff; color: #6b21a8; }

.sf-kind {
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8; background: #f1f5f9;
  padding: 1px 5px; border-radius: 3px;
}
.sf-del {
  margin-left: auto;
  width: 20px; height: 20px;
  border: none; border-radius: 4px;
  background: transparent; color: #94a3b8;
  font-size: 14px; line-height: 1; cursor: pointer;
}
.sf-del:hover { background: #fee2e2; color: #dc2626; }
</style>
