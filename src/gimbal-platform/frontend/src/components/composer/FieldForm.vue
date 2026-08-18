<!--
  FieldForm.vue — 根据 IOFieldBinding 动态渲染表单字段 (PRD §5.4 三类型策略)

  Type A: 完整 IOFieldBinding → 渲染对应 ui_kind 的表单控件
  Type B: 仅 ui_kind=unknown → 降级为通用 text
  Type C: 仅在 schema 出现但无 binding → 隐藏, 但运行时携带

  path 字段是 JSONPath (如 "$.customer_id") — 表单值通过 path 写入 body
  valueGetter/setter 通过 JSONPath util 双向转换
-->
<template>
  <div class="field-form">
    <div v-for="f in visibleFields" :key="f.name" class="field" :class="['sk-' + f.source_kind, { required: f.required }]">
      <label class="field-label">
        <span class="label-text">{{ f.name }}</span>
        <span v-if="f.required" class="req-mark">*</span>
        <span class="field-path">{{ f.path }}</span>
        <span class="ui-tag" :class="`k-${f.ui_kind}`">{{ f.ui_kind }}</span>
        <span class="src-tag" :class="`s-${f.source_kind}`">
          <template v-if="f.source_kind === 'independent'">literal</template>
          <template v-else-if="f.source_kind === 'lookup'">static · ${ var }</template>
          <template v-else-if="f.source_kind === 'generated'">dynamic · Assign</template>
          <template v-else>{{ f.source_kind }}</template>
        </span>
      </label>
      <div class="field-control">
        <!-- text / unknown (Type B fallback) -->
        <div v-if="f.ui_kind === 'text' || f.ui_kind === 'unknown'" class="ctl-with-var">
          <div class="ctl-cand-wrap">
            <input
              type="text"
              class="ctl"
              :value="getValue(f) as string"
              :placeholder="placeholderFor(f)"
              @input="e => setValue(f, (e.target as HTMLInputElement).value)"
            />
            <!-- 候选下拉(#2 策略改造):assertion.target / extract.expression
                 从响应字段选 JSONPath,不手打。候选由调用方按字段名映射传入 -->
            <button
              v-if="candidatesFor(f).length"
              type="button"
              class="cand-btn"
              title="从候选值选择"
              @click="candOpenField = candOpenField === f ? null : f"
            >▾</button>
            <div v-if="candOpenField === f" class="cand-list">
              <button
                v-for="c in candidatesFor(f)"
                :key="c"
                type="button"
                class="cand-item"
                @click="applyCandidate(f, c)"
              >
                <code>{{ c }}</code>
              </button>
            </div>
          </div>
          <button
            v-if="varEntries.length"
            type="button"
            class="var-btn"
            title="插入变量引用 ${var.<name>}"
            @click="openVarPicker(f)"
          >Ⓥ</button>
        </div>

        <!-- number -->
        <input
          v-else-if="f.ui_kind === 'number'"
          type="number"
          class="ctl"
          :value="getValue(f) as number | string"
          :placeholder="placeholderFor(f)"
          @input="e => setValue(f, Number((e.target as HTMLInputElement).value))"
        />

        <!-- boolean -->
        <label v-else-if="f.ui_kind === 'boolean'" class="ctl-bool">
          <input
            type="checkbox"
            :checked="Boolean(getValue(f))"
            @change="e => setValue(f, (e.target as HTMLInputElement).checked)"
          />
          <span>{{ getValue(f) ? 'true' : 'false' }}</span>
        </label>

        <!-- select -->
        <select
          v-else-if="f.ui_kind === 'select' && f.enum"
          class="ctl"
          :value="getValue(f) as string"
          @change="e => setValue(f, (e.target as HTMLSelectElement).value)"
        >
          <option value="">— select —</option>
          <option v-for="opt in f.enum" :key="String(opt)" :value="String(opt)">{{ String(opt) }}</option>
        </select>

        <!-- textarea -->
        <div v-else-if="f.ui_kind === 'textarea'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-area"
            rows="3"
            :value="getValue(f) as string"
            :placeholder="placeholderFor(f)"
            @input="e => setValue(f, (e.target as HTMLTextAreaElement).value)"
          />
          <button
            v-if="varEntries.length"
            type="button"
            class="var-btn"
            title="插入变量引用 ${var.<name>}"
            @click="openVarPicker(f)"
          >Ⓥ</button>
        </div>

        <!-- json (dark code editor) -->
        <div v-else-if="f.ui_kind === 'json'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-code"
            rows="4"
            :value="formatJson(getValue(f))"
            placeholder="JSON object"
            @input="e => setValue(f, parseJson((e.target as HTMLTextAreaElement).value))"
          />
          <button
            v-if="varEntries.length"
            type="button"
            class="var-btn dark"
            title="插入变量引用 ${var.<name>}"
            @click="openVarPicker(f)"
          >Ⓥ</button>
        </div>

        <!-- file (placeholder) -->
        <div v-else-if="f.ui_kind === 'file' || f.ui_kind === 'binary'" class="ctl-file">
          <span class="file-tag">{{ f.ui_kind }}</span>
          <span class="file-hint">文件上传 — TODO</span>
        </div>

        <!-- unknown (Type B) — text fallback -->
        <input
          v-else
          type="text"
          class="ctl"
          :value="getValue(f) as string"
          :placeholder="placeholderFor(f)"
          @input="e => setValue(f, (e.target as HTMLInputElement).value)"
        />
      </div>
      <p v-if="f.description" class="field-desc">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        {{ f.description }}
      </p>
    </div>

    <!-- Ⓥ 变量选择 popover(text/textarea/json 控件插入 ${var.<name>},#3) -->
    <el-popover
      :visible="varPickerField === f"
      placement="right"
      :width="280"
      trigger="manual"
    >
      <template #reference>
        <span />
      </template>
      <div class="var-pop">
        <p class="var-pop-title">选择变量 → 插入 var 引用</p>
        <div v-if="!varEntries.length" class="var-pop-empty">注册表为空</div>
        <button
          v-for="e in varEntries"
          :key="e.name"
          type="button"
          class="var-pop-item"
          @click="insertVarRef(e)"
        >
          <span class="var-pop-name">{{ e.name }}</span>
          <span class="var-pop-badge" :class="e.origin">{{ e.origin }}</span>
          <span class="var-pop-src">
            <template v-if="e.origin === 'config'">共享变量</template>
            <template v-else>步骤 {{ (e.stepIdx ?? 0) + 1 }}</template>
          </span>
        </button>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { IOFieldBinding } from '@/types/plate'
import type { VarEntry } from '@/utils/var-registry'
import { getByPath, setByPath } from '@/utils/jsonpath'

const props = defineProps<{
  bindings: IOFieldBinding[]
  body: any
  /** 变量注册表(#3):Ⓥ 插入 ${var.<name>};缺省不渲染 Ⓥ */
  varEntries?: VarEntry[]
  /**
   * 候选值映射(#2 策略改造):字段名 → 候选 JSONPath 列表。
   * 策略表单场景:assertion.target / extract.expression 从响应
   * assertable_fields 选,不手打;缺省无候选按钮。
   */
  candidates?: Record<string, string[]>
}>()
const emit = defineEmits<{
  'update:body': [any]
}>()

const varEntries = computed(() => props.varEntries ?? [])

/** 候选下拉开合状态(同屏至多一个) */
const candOpenField = ref<IOFieldBinding | null>(null)
function candidatesFor(f: IOFieldBinding): string[] {
  return props.candidates?.[f.name] ?? []
}
function applyCandidate(f: IOFieldBinding, c: string) {
  setValue(f, c)
  candOpenField.value = null
}

// Type A + Type B: 有 binding 的都显示; Type C (无 binding 的 schema 字段) 走 hiddenFields 不在此显示
const visibleFields = computed(() => props.bindings)

function getValue(f: IOFieldBinding): unknown {
  if (!props.body) return f.default ?? f.example ?? ''
  return getByPath(props.body, f.path.replace(/^\$\./, '')) ?? f.default ?? f.example ?? ''
}

function setValue(f: IOFieldBinding, val: unknown) {
  const next = { ...(props.body || {}) }
  setByPath(next, f.path.replace(/^\$\./, ''), val)
  emit('update:body', next)
}

function placeholderFor(f: IOFieldBinding): string {
  const ex = f.example
  if (ex !== null && ex !== undefined) return String(ex)
  if (f.description) return f.description
  return f.required ? `${f.name} (必填)` : f.name
}

function formatJson(v: unknown): string {
  if (v === null || v === undefined || v === '') return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v, null, 2)
}

function parseJson(s: string): unknown {
  if (!s || !s.trim()) return null
  try { return JSON.parse(s) } catch { return s }
}

// ── Ⓥ 变量插入(#3):追加到当前值尾(不覆盖已输入内容) ─────────────
const varPickerField = ref<IOFieldBinding | null>(null)
function openVarPicker(f: IOFieldBinding) {
  varPickerField.value = varPickerField.value === f ? null : f
}
function insertVarRef(e: VarEntry) {
  const f = varPickerField.value
  if (!f) return
  const cur = String(getValue(f) ?? '')
  setValue(f, cur + `\${var.${e.name}}`)
  varPickerField.value = null
}
</script>

<style scoped>
.field-form {
  display: flex; flex-direction: column; gap: 14px;
}
.field { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.field.required .label-text { color: #1a1d24; }

/* 控件 + Ⓥ 按钮同排(text)/叠排(textarea/json) */
.ctl-with-var { display: flex; gap: 6px; align-items: stretch; }
.ctl-with-var .ctl { flex: 1; min-width: 0; }
.ctl-with-var.col { flex-direction: column; align-items: flex-end; }
.var-btn {
  flex-shrink: 0;
  width: 30px;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  color: #047857; cursor: pointer; font-size: 13px;
  transition: all 0.15s;
}
.ctl-with-var.col .var-btn { width: 30px; height: 24px; font-size: 11px; }
.var-btn:hover { border-color: #6ee7b7; background: #d1fae5; }
.var-btn.dark { background: #313244; border-color: #45475a; color: #a6e3a1; }
.var-btn.dark:hover { border-color: #6ee7b7; }

/* 候选下拉(#2):输入框内嵌 ▾ + 绝对定位候选列表 */
.ctl-cand-wrap { position: relative; flex: 1; min-width: 0; display: flex; }
.ctl-cand-wrap .ctl { flex: 1; }
.cand-btn {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  width: 20px; height: 20px;
  border: none; border-radius: 4px; background: transparent;
  color: #94a3b8; cursor: pointer; font-size: 10px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
}
.cand-btn:hover { background: #e2e8f0; color: #475569; }
.cand-list {
  position: absolute; top: calc(100% + 2px); left: 0; right: 0;
  z-index: 30;
  max-height: 200px; overflow-y: auto;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
  padding: 3px;
}
.cand-item {
  display: block; width: 100%; text-align: left;
  padding: 5px 8px; border: none; border-radius: 4px;
  background: transparent; cursor: pointer;
}
.cand-item:hover { background: #f1f5f9; }
.cand-item code {
  font-family: var(--font-mono); font-size: 11px; color: #334155;
}

/* Ⓥ 变量 popover 列表 */
.var-pop { display: flex; flex-direction: column; gap: 3px; }
.var-pop-title {
  margin: 0 0 6px; font-size: 11px; color: #64748b;
  font-family: var(--font-mono);
}
.var-pop-empty { font-size: 12px; color: #94a3b8; padding: 6px 0; }
.var-pop-item {
  display: grid; grid-template-columns: 1.2fr 56px 64px; gap: 6px;
  align-items: center; text-align: left;
  padding: 5px 8px; border: 1px solid transparent; border-radius: 6px;
  background: transparent; cursor: pointer; font-size: 12px;
}
.var-pop-item:hover { background: #f1f5f9; border-color: #e2e8f0; }
.var-pop-name {
  font-family: var(--font-mono); font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.var-pop-badge {
  padding: 1px 5px; border-radius: 4px; text-align: center;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
}
.var-pop-badge.extract { background: #d1fae5; color: #065f46; }
.var-pop-badge.config { background: #eef2ff; color: #4338ca; }
.var-pop-src { font-size: 10px; color: #94a3b8; }

.field-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 500;
}
.label-text { color: #1a1d24; font-weight: 600; }
.req-mark { color: #ef4444; font-weight: 700; }
.field-path {
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8; background: #f1f5f9; padding: 1px 4px; border-radius: 3px;
}
.ui-tag {
  font-size: 9px; font-weight: 700; text-transform: uppercase;
  padding: 1px 4px; border-radius: 3px;
  background: #eef2ff; color: #4f46e5;
}
.ui-tag.k-number { background: #fef3c7; color: #92400e; }
.ui-tag.k-boolean { background: #d1fae5; color: #065f46; }
.ui-tag.k-select { background: #f3e8ff; color: #6b21a8; }
.ui-tag.k-textarea { background: #fce7f3; color: #9d174d; }
.ui-tag.k-json { background: #1e1e2e; color: #a6e3a1; }
.ui-tag.k-file, .ui-tag.k-binary { background: #f1f5f9; color: #475569; }
.ui-tag.k-unknown { background: #fee2e2; color: #991b1b; }
/* PRD §5.6 4 色 source_kind 视觉区分 (literal / static / dynamic / auto) */
.src-tag {
  font-size: 9px; font-weight: 600;
  padding: 1px 6px; border-radius: 3px;
  background: #f1f5f9; color: #475569;        /* literal 灰 */
}
.src-tag.s-lookup { background: #faf5ff; color: #7c3aed; }   /* static 紫 */
.src-tag.s-generated { background: #ede9fe; color: #7c3aed; } /* dynamic 紫 */
/* 字段行 4 色左边框 */
.field.sk-independent { border-left: 3px solid #cbd5e1; }    /* literal 灰 */
.field.sk-lookup { border-left: 3px solid #7c3aed; }            /* static 紫 */
.field.sk-generated { border-left: 3px solid #f59e0b; }         /* dynamic 橙 (auto-extract 提示色) */

.ctl {
  width: 100%;
  /* border-box: content-box 下 100% + padding + 边框会超出策略卡/字段行容器 */
  box-sizing: border-box;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  padding: 7px 10px;
  font-size: 13px; color: #1a1d24; font-family: inherit;
  transition: all 0.15s;
  outline: none;
}
.ctl:hover { border-color: #c7d2fe; }
.ctl:focus { background: #fff; border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15); }
.ctl::placeholder { color: #cbd5e1; }

.ctl-area { resize: vertical; min-height: 60px; }
.ctl-code {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1; border-color: #313244;
}
.ctl-code:focus { background: #1e1e2e; color: #a6e3a1; border-color: #6366f1; }

.ctl-bool {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; cursor: pointer;
}
.ctl-bool input { width: 16px; height: 16px; accent-color: #4f46e5; }

.ctl-file {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; background: #fafbfc; border: 1.5px dashed #cbd5e1; border-radius: 8px;
  color: #5a6273; font-size: 12px;
}
.file-tag { font-weight: 700; color: #475569; }
.file-hint { font-size: 11px; }

.field-desc {
  display: flex; align-items: flex-start; gap: 5px;
  margin: 1px 0 0;
  font-size: 11.5px; color: #64748b; line-height: 1.5;
}
.field-desc svg { flex-shrink: 0; margin-top: 2px; color: #94a3b8; }
</style>
