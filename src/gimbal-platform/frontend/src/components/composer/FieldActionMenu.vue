<!--
  FieldActionMenu.vue — 字段动作菜单 (#4/#5 变量工作台迁移)

  FieldForm 每个字段控件尾部的 ☰ 菜单(fieldActions 门控开启时渲染):
    ├─ 引用共享变量 (Reference)     → 子列表 config 出身 → 插 ${var.x} 文本
    ├─ 从响应提取 (Extract)         → emit fieldExtract(快捷 extract 策略)
    ├─ 注入响应变量 (DynamicAssign) → 子列表 extract 出身 → emit fieldAssign
    └─ 断言该字段 (Assertion)       → emit fieldAssert(快捷断言策略)

  措辞对齐 plate _KIND_LABELS;数据全部由调用方传入,零 IO。
  子列表用就地展开(非 el-dropdown 嵌套子菜单 — 测试与 a11y 都更稳)。
-->
<template>
  <div class="fa-menu" @click.stop>
    <!-- 主菜单(未展开子列表时) -->
    <template v-if="!subOpen">
      <button v-if="domain !== 'response'" type="button" class="fa-item" @click="subOpen = 'ref'">
        <span class="fa-label">引用共享变量</span><span class="fa-note">Reference</span>
      </button>
      <button type="button" class="fa-item" @click="emitExtract">
        <span class="fa-label">从响应提取</span><span class="fa-note">Extract</span>
      </button>
      <button v-if="domain !== 'response'" type="button" class="fa-item" @click="subOpen = 'inject'">
        <span class="fa-label">注入响应变量</span><span class="fa-note">DynamicAssign</span>
      </button>
      <button type="button" class="fa-item" @click="emitAssert">
        <span class="fa-label">断言该字段</span><span class="fa-note">Assertion</span>
      </button>
    </template>

    <!-- 引用子列表:config 出身 → 插 ${var.x} -->
    <template v-else-if="subOpen === 'ref'">
      <p class="fa-sub-title">引用共享变量 → 插入 ${var.x}</p>
      <p v-if="!varChoices.length" class="fa-empty">没有可用变量</p>
      <button
        v-for="e in varChoices"
        :key="e.name"
        type="button"
        class="fa-item fa-var-item"
        @click="emit('varInsert', e.name)"
      >
        <span class="fa-name">{{ e.name }}</span>
        <span class="fa-badge" :class="e.origin">{{ e.origin }}</span>
        <span class="fa-src">共享变量</span>
      </button>
      <p v-if="varChoices.length" class="fa-ds-hint">数据集列运行期注入,不在列表</p>
      <button type="button" class="fa-back" @click="subOpen = null">‹ 返回</button>
    </template>

    <!-- 注入子列表:extract 出身(时序门控 disabled)→ 建 assign 策略 -->
    <template v-else>
      <p class="fa-sub-title">注入响应变量 → 建赋值策略</p>
      <p v-if="!injectChoices.length" class="fa-empty">没有可用变量</p>
      <button
        v-for="e in injectChoices"
        :key="e.name"
        type="button"
        class="fa-item fa-var-item"
        :class="{ disabled: e.disabled }"
        :disabled="e.disabled"
        :title="e.disabled ? `步骤 ${(e.stepIdx ?? 0) + 1} 才产出` : undefined"
        @click="!e.disabled && emit('fieldAssign', field, e.name)"
      >
        <span class="fa-name">{{ e.name }}</span>
        <span class="fa-badge" :class="e.origin">{{ e.origin }}</span>
        <span class="fa-src">
          <template v-if="e.disabled">步骤 {{ (e.stepIdx ?? 0) + 1 }} 才产出</template>
          <template v-else>步骤 {{ (e.stepIdx ?? 0) + 1 }}</template>
        </span>
      </button>
      <button type="button" class="fa-back" @click="subOpen = null">‹ 返回</button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { IOFieldBinding } from '@/types/plate'
import type { VarEntry } from '@/utils/var-registry'

const props = defineProps<{
  /** 当前字段(提取/断言/注入事件的载体) */
  field: IOFieldBinding
  /** 当前字段值(预留给引用插入位置的上下文;菜单本身不改值) */
  value?: string
  /** 引用子列表:config 出身 */
  varChoices: VarEntry[]
  /** 注入子列表:extract 出身 + 时序门控 disabled */
  injectChoices: Array<VarEntry & { disabled?: boolean }>
  /**
   * 字段域(IO 双签卡片):'request'(默认,四项菜单)|
   * 'response'(契约参考,仅 提取/断言 两项 — 无值可插、无 request_body 可写)
   */
  domain?: 'request' | 'response'
}>()

const emit = defineEmits<{
  'close': []
  /** 插入 ${var.<name>}(FieldForm 在本组件外完成值追加) */
  'varInsert': [name: string]
  'fieldExtract': [field: IOFieldBinding]
  'fieldAssign': [field: IOFieldBinding, varName: string]
  'fieldAssert': [field: IOFieldBinding]
}>()

/** 子列表开合:null=主菜单 / 'ref'=引用 / 'inject'=注入 */
const subOpen = ref<null | 'ref' | 'inject'>(null)

function emitExtract() { emit('fieldExtract', props.field); emit('close') }
function emitAssert() { emit('fieldAssert', props.field); emit('close') }
</script>

<style scoped>
/* 就地浮层(与 FieldForm cand-list 同模式:绝对定位 + 阴影) */
.fa-menu {
  position: absolute; top: calc(100% + 2px); right: 0;
  z-index: 40; min-width: 230px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.14);
  padding: 4px;
  display: flex; flex-direction: column; gap: 1px;
}
.fa-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border: none; border-radius: 6px;
  background: transparent; cursor: pointer; font-size: 12px;
  text-align: left; color: #1a1d24;
}
.fa-item:hover { background: #f1f5f9; }
.fa-item.disabled { opacity: 0.45; cursor: not-allowed; }
.fa-item.disabled:hover { background: transparent; }
.fa-label { font-weight: 600; flex: 1; }
.fa-note {
  font-family: var(--font-mono); font-size: 9px; color: #94a3b8;
}
.fa-sub-title {
  margin: 2px 4px 4px; font-size: 11px; color: #64748b;
  font-family: var(--font-mono);
}
.fa-empty { font-size: 12px; color: #94a3b8; padding: 6px 10px; margin: 0; }
.fa-var-item { display: grid; grid-template-columns: 1.2fr 56px 72px; gap: 6px; }
.fa-name {
  font-family: var(--font-mono); font-weight: 600; font-size: 12px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fa-badge {
  padding: 1px 5px; border-radius: 4px; text-align: center;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
}
.fa-badge.extract { background: #d1fae5; color: #065f46; }
.fa-badge.config { background: #eef2ff; color: #4338ca; }
.fa-src { font-size: 10px; color: #94a3b8; }
.fa-ds-hint {
  margin: 2px 4px; font-size: 10px; color: #b45309;
}
.fa-back {
  border: none; background: transparent; cursor: pointer;
  padding: 5px 8px; font-size: 11px; color: #64748b; text-align: left;
  border-top: 1px dashed #e2e8f0; border-radius: 0 0 6px 6px;
}
.fa-back:hover { color: #3730a3; }
</style>
