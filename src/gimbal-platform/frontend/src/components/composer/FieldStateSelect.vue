<!--
  FieldStateSelect.vue — 字段状态控制(2026-09-05 spec §5.4)

  字段行尾的状态下拉:form(直接渲染)/ collapse(折叠区)/ carry
  (传递面,值表注入)。选择即上抛 change —— 由 Canvas 落地为
  step.field_states 稀疏增量(§3.1:添加字段 = 增量[path]=form/collapse,
  移除 = 增量[path]=carry);↺ 重置 = 清除该条增量,回落目录共识默认。

  状态回写与值回写两通路分离(§5.4):本组件只管状态,值控件在
  FieldForm 本体。搜索框是定位手段不是添加机制 — 挂账不做。
-->
<template>
  <span class="fss">
    <select
      class="fss-sel"
      :class="`s-${state}`"
      :value="state"
      title="字段状态:form 表单 / collapse 折叠 / carry 传递(写 step.field_states 增量)"
      @change="e => emit('change', (e.target as HTMLSelectElement).value as FieldState)"
    >
      <option value="form">form</option>
      <option value="collapse">collapse</option>
      <option value="carry">carry</option>
    </select>
    <button
      v-if="overlay"
      type="button"
      class="fss-reset"
      title="清除该条增量 — 重置回目录共识默认"
      @click.stop="emit('reset')"
    >↺</button>
  </span>
</template>

<script setup lang="ts">
import type { FieldState } from '@/types/plate'

defineProps<{
  /** 解析态(增量 × 目录默认合成后,buildTree 节点携带) */
  state: FieldState
  /** 该条目存在显式覆盖(显示 ↺ 重置入口) */
  overlay?: boolean
}>()
const emit = defineEmits<{
  /** 选择状态(写增量);值 = 目标态 */
  'change': [state: FieldState]
  /** 重置(清增量,回落共识默认) */
  'reset': []
}>()
</script>

<style scoped>
.fss { display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0; }
.fss-sel {
  font-family: var(--font-mono); font-size: 9.5px; font-weight: 700;
  padding: 1px 3px; border-radius: 3px; cursor: pointer;
  border: 1px solid #e2e8f0; background: #f8fafc; color: #475569;
  outline: none;
}
.fss-sel:hover { border-color: #94a3b8; }
.fss-sel:focus { border-color: #6366f1; }
/* 解析态色语:form 中性 / collapse 靛 / carry 青(值表传递) */
.fss-sel.s-form { background: #f1f5f9; color: #475569; }
.fss-sel.s-collapse { background: #eef2ff; color: #4f46e5; }
.fss-sel.s-carry { background: #f0fdfa; color: #0f766e; border-color: #99f6e4; }
.fss-reset {
  width: 16px; height: 16px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px dashed #cbd5e1; border-radius: 4px;
  background: transparent; color: #94a3b8;
  font-size: 10px; line-height: 1; cursor: pointer; transition: all 0.15s;
}
.fss-reset:hover { border-color: #6ee7b7; color: #0f766e; background: #f0fdfa; }
</style>
