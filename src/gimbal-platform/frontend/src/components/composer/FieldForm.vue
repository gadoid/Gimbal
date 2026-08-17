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
        <input
          v-if="f.ui_kind === 'text' || f.ui_kind === 'unknown'"
          type="text"
          class="ctl"
          :value="getValue(f) as string"
          :placeholder="placeholderFor(f)"
          @input="e => setValue(f, (e.target as HTMLInputElement).value)"
        />

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
        <textarea
          v-else-if="f.ui_kind === 'textarea'"
          class="ctl ctl-area"
          rows="3"
          :value="getValue(f) as string"
          :placeholder="placeholderFor(f)"
          @input="e => setValue(f, (e.target as HTMLTextAreaElement).value)"
        />

        <!-- json (dark code editor) -->
        <textarea
          v-else-if="f.ui_kind === 'json'"
          class="ctl ctl-code"
          rows="4"
          :value="formatJson(getValue(f))"
          placeholder="JSON object"
          @input="e => setValue(f, parseJson((e.target as HTMLTextAreaElement).value))"
        />

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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { IOFieldBinding } from '@/types/plate'
import { getByPath, setByPath } from '@/utils/jsonpath'

const props = defineProps<{
  bindings: IOFieldBinding[]
  body: any
}>()
const emit = defineEmits<{
  'update:body': [any]
}>()

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
</script>

<style scoped>
.field-form {
  display: flex; flex-direction: column; gap: 14px;
}
.field { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.field.required .label-text { color: #1a1d24; }

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
