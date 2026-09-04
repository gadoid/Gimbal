<!--
  StrategyForm.vue — 单条策略的通用表单(plate 策略语法 dim 驱动)

  数据来自 strategy-catalog 代理(plate /api/strategy/{kind}/full):
  detail.fields 是该 kind 的业务字段描述符,交给 FieldForm 渲染;
  base_fields(StrategyBase 公共字段)第一版不渲染,默认值生效。

  词汇适配:StrategyFieldDescView 无 source_kind(值来源语义对策略
  无意义),本组件补 independent 默认值以复用 FieldForm,不改其本体。

  变异语义:FieldForm @update:body 直接替换 props.strategy 引用对象
  的字段(与 Canvas 现有 extract 行为一致的直接变异模式)。

  折叠交互:头行常显(badge + kind + 单行摘要 + 箭头),字段区 v-show。
  新添加的策略默认展开引导填写;预填/加载的默认折叠降噪。

  base_fields 特例露出(onFailure 之后的第二个):order 执行顺序 ——
  引擎 dispatch_phase 按 phase 过滤后以 order 升序稳定排序,全缺省(0)
  时执行序=数组序;显式设置(导入/手编)后卡头 #N 角标可见,卡身可改,
  清空输入删 key 回缺省(不把 0 写进 payload)。
-->
<template>
  <div class="strategy-form" :class="`ph-${detail.phase}`">
    <div class="sf-head" @click="toggle">
      <span class="sf-badge" :class="`ph-${detail.phase}`">{{ detail.label }}</span>
      <span class="sf-kind">{{ tagLabel ?? detail.kind }}</span>
      <span
        v-if="orderChip !== null"
        class="sf-order"
        :title="`执行顺序 order=${orderChip}(同 phase 内升序,缺省 0 按列表序)`"
      >#{{ orderChip }}</span>
      <span class="sf-summary" :title="summary">{{ summary }}</span>
      <button type="button" class="sf-toggle" title="展开/折叠">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ open: expanded }"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <button type="button" class="sf-del" title="删除这条策略" @click.stop="emit('remove')">×</button>
    </div>
    <div v-show="expanded" class="sf-body">
      <FieldForm
        :bindings="fieldBindings"
        :body="strategy"
        :candidates="candidates"
        @update:body="onUpdateBody"
      />
      <!-- order 入口:同 phase 内执行顺序(base_fields 特例露出,同 onFailure 模式);
           清空 = 删 key 回缺省 0(数组序),不写 0 进 payload -->
      <div v-if="orderBinding" class="sf-order-row">
        <label class="sf-order-label">
          执行顺序 (order)
          <span class="sf-onfail-hint">同 phase 内按 order 升序执行;缺省 0 相同则按列表序,清空恢复缺省</span>
        </label>
        <input
          type="number"
          class="sf-order-input"
          :value="orderInput"
          :placeholder="String(orderBinding.default ?? 0)"
          @change="onOrderChange"
        >
      </div>
      <!-- onFailure 入口(#2):base_fields 第一版整体不渲染,但失败处理
           是编排高频诉求 → 单独露出这一个;其余 base 字段仍走默认值 -->
      <div v-if="onFailureBinding" class="sf-onfail">
        <label class="sf-onfail-label">
          失败处理 (onFailure)
          <span class="sf-onfail-hint">策略失败时的行为 — 默认 abort 中止本 step</span>
        </label>
        <select
          class="sf-onfail-select"
          :value="(strategy as any).onFailure ?? onFailureBinding.default ?? 'abort'"
          @change="e => onUpdateBody({ ...props.strategy, onFailure: (e.target as HTMLSelectElement).value })"
        >
          <option v-for="o in onFailureBinding.enum || []" :key="String(o)" :value="String(o)">
            {{ o }}{{ ON_FAILURE_LABELS[String(o)] ? ` — ${ON_FAILURE_LABELS[String(o)]}` : '' }}
          </option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FieldForm from './FieldForm.vue'
import type { StrategyView, StrategyKindDetailView, StrategyFieldDescView, IOFieldBinding } from '@/types/plate'

const props = defineProps<{
  strategy: StrategyView
  detail: StrategyKindDetailView
  /** 新添加的策略引导填写 → 初始展开;预填/加载的默认折叠降噪 */
  startExpanded?: boolean
  /**
   * 候选值映射(#2):断言 target / extract expression 的下拉候选,
   * 由 Canvas 从 step 的 endpoint 响应契约推导后传入;缺省无候选按钮。
   */
  candidates?: Record<string, string[]>
  /** 角标跳转脉冲(需求1):false→true 沿触发展开(定位被折叠的策略卡) */
  expandWhen?: boolean
  /** 头部 kind 标文本(Canvas 传编号形态 extract_2,与字段行角标对应) */
  tagLabel?: string
}>()
const emit = defineEmits<{
  remove: []
}>()

const expanded = ref(!!props.startExpanded)
function toggle() { expanded.value = !expanded.value }
watch(() => props.expandWhen, (v) => { if (v) expanded.value = true })

/** onFailure 的字段描述符(plate base_fields 内省产物;无则不渲染入口) */
const onFailureBinding = computed(() =>
  props.detail.base_fields.find((f: StrategyFieldDescView) => f.name === 'onFailure')
)

/** order 的字段描述符(同 onFailure 模式;无则编辑行不渲染,卡头角标独立判断) */
const orderBinding = computed(() =>
  props.detail.base_fields.find((f: StrategyFieldDescView) => f.name === 'order')
)

/** 卡头 #N 角标:显式设置(数字)才显示 —— 平台新增骨架不含 order,缺省 0 零噪音 */
const orderChip = computed<number | null>(() => {
  const v = (props.strategy as any).order
  return typeof v === 'number' && Number.isInteger(v) ? v : null
})

/** 输入框受控值:未设置 → 空(placeholder 显示缺省),不把 0 预填进框 */
const orderInput = computed<string>(() => {
  const v = (props.strategy as any).order
  return typeof v === 'number' && Number.isInteger(v) ? String(v) : ''
})

function onOrderChange(e: Event) {
  const el = e.target as HTMLInputElement
  const raw = el.value.trim()
  if (raw === '') {
    // 清空 → 回缺省:删 key 让默认值生效,不写 0 进 payload
    delete (props.strategy as any).order
    return
  }
  const n = Number(raw)
  if (!Number.isInteger(n)) {
    el.value = orderInput.value   // 非整数回滚显示,不写入
    return
  }
  ;(props.strategy as any).order = n
}

const ON_FAILURE_LABELS: Record<string, string> = {
  abort: '中止本 step',
  continue: '记录错误继续',
  warn: '仅警告',
  retry: '配合重试',
}

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

/**
 * 头行单行摘要:按 kind 取最有辨识度的 1-3 个值拼一句。
 * 空/折叠态显示占位。截断由 CSS ellipsis 兜底。
 */
const summary = computed<string>(() => {
  const s = props.strategy as any
  switch (props.detail.kind) {
    case 'extract':
      return [s.target, s.expression].filter(Boolean).join(' ← ') || '未配置'
    case 'assign':
      return [s.target, s.source].filter((v) => v !== undefined && v !== null && v !== '').join(' = ') || '未配置'
    case 'assertion': {
      const parts = [s.target, s.operator, s.expected]
        .filter((v: unknown) => v !== undefined && v !== null && v !== '')
        .map(String)
      if (!parts.length) return '未配置'
      const msg = s.message ? ` · ${s.message}` : ''
      return parts.join(' ') + msg
    }
    default:
      // 未知 kind:退化为前两个非 kind 字段的 k=v
      const kv = Object.entries(s)
        .filter(([k, v]) => k !== 'kind' && v !== null && v !== undefined && v !== '')
        .slice(0, 2)
        .map(([k, v]) => `${k}=${String(v)}`)
      return kv.join(' ') || props.detail.kind
  }
})
</script>

<style scoped>
.strategy-form {
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
  padding: 7px 10px;
  cursor: pointer;
  user-select: none;
  min-width: 0; /* 摘要 ellipsis 生效的前提 */
}
.sf-head:hover { background: #f1f5f9; }

.sf-badge {
  flex-shrink: 0;
  font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 4px;
}
.sf-badge.ph-before_request { background: #fef3c7; color: #92400e; }
.sf-badge.ph-after_request  { background: #d1fae5; color: #065f46; }
.sf-badge.ph-verifying      { background: #f3e8ff; color: #6b21a8; }

.sf-kind {
  flex-shrink: 0;
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8; background: #f1f5f9;
  padding: 1px 5px; border-radius: 3px;
}

/* 卡头 order 角标:显式设置的执行顺序,折叠态也可见 */
.sf-order {
  flex-shrink: 0;
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  color: #4f46e5; background: #eef2ff;
  padding: 1px 5px; border-radius: 3px;
}

/* 单行摘要: 吸收剩余宽度, 溢出 ellipsis */
.sf-summary {
  flex: 1; min-width: 0;
  font-family: var(--font-mono); font-size: 11px;
  color: #64748b;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.sf-toggle {
  flex-shrink: 0;
  width: 20px; height: 20px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 4px;
  background: transparent; color: #94a3b8;
  cursor: pointer; padding: 0;
}
.sf-toggle svg { transition: transform 0.15s; }
.sf-toggle svg.open { transform: rotate(180deg); }
.sf-toggle:hover { background: #e2e8f0; color: #475569; }

.sf-del {
  flex-shrink: 0;
  width: 20px; height: 20px;
  border: none; border-radius: 4px;
  background: transparent; color: #94a3b8;
  font-size: 14px; line-height: 1; cursor: pointer;
}
.sf-del:hover { background: #fee2e2; color: #dc2626; }

/* 展开的字段区: 内衬底色与头行分隔 */
.sf-body {
  padding: 8px 10px 10px;
  border-top: 1px dashed #e6e8ec;
}

/* 角标跳转定位闪烁(需求1):1.2s 靛蓝光环渐隐 */
@keyframes sf-flash { from { box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.35); } to { box-shadow: 0 0 0 3px rgba(79, 70, 229, 0); } }
.strategy-form.sf-flash { animation: sf-flash 1.2s ease-out; }

/* onFailure 入口(#2):字段区底部一行,label + select 紧凑排 */
.sf-onfail {
  display: flex; align-items: center; gap: 10px;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed #e6e8ec;
}

/* order 入口:同 onFailure 行形态,number 输入窄列 */
.sf-order-row {
  display: flex; align-items: center; gap: 10px;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed #e6e8ec;
}
.sf-order-label {
  display: flex; flex-direction: column; gap: 1px;
  font-size: 11px; font-weight: 600; color: #475569;
  flex-shrink: 0;
}
.sf-order-input {
  width: 110px; flex-shrink: 0; box-sizing: border-box;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  padding: 6px 10px; font-size: 12px; color: #1a1d24;
  outline: none;
}
.sf-order-input:focus { border-color: #4f46e5; background: #fff; }
.sf-onfail-label {
  display: flex; flex-direction: column; gap: 1px;
  font-size: 11px; font-weight: 600; color: #475569;
  flex-shrink: 0;
}
.sf-onfail-hint { font-size: 10px; font-weight: 400; color: #94a3b8; }
.sf-onfail-select {
  flex: 1; box-sizing: border-box;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  padding: 6px 10px; font-size: 12px; color: #1a1d24;
  outline: none;
}
.sf-onfail-select:focus { border-color: #4f46e5; background: #fff; }
</style>
