<!--
  FieldForm.vue — 根据 IOFieldBinding 动态渲染表单字段 (PRD §5.4 三类型策略)

  Type A: 完整 IOFieldBinding → 渲染对应 ui_kind 的表单控件
  Type B: 仅 ui_kind=unknown → 降级为通用 text
  Type C: 仅在 schema 出现但无 binding → 隐藏, 但运行时携带

  path 字段是 JSONPath (如 "$.customer_id") — 表单值通过 path 写入 body
  valueGetter/setter 通过 JSONPath util 双向转换

  typed 字段(number/boolean/select)的模板值支持:值为 ${var.x} 串时控件
  降级为 text 输入 — 浏览器 number input 拒显非数字、checkbox/select 无法
  承载串值;运行期引擎对整串模板按变量原类型解析,前端只需可见可编辑。
-->
<template>
  <div class="field-form">
    <div v-for="f in visibleFields" :key="f.name" class="field" :class="['sk-' + f.source_kind, { required: f.required }]">
      <label class="field-label">
        <span class="label-text">{{ f.name }}</span>
        <span v-if="f.required" class="req-mark">*</span>
        <span class="field-path">{{ f.path }}</span>
        <span class="ui-tag" :class="`k-${f.ui_kind}`">{{ f.ui_kind }}</span>
        <span v-if="assertable?.includes(f.path)" class="assertable-mark" title="可断言字段">✓</span>
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
              :disabled="readonly"
              @input="e => setValue(f, (e.target as HTMLInputElement).value)"
            />
            <!-- 候选下拉(#2 策略改造):assertion.target / extract.expression
                 从响应字段选 JSONPath,不手打。候选由调用方按字段名映射传入 -->
            <button
              v-if="candidatesFor(f).length"
              type="button"
              class="cand-btn"
              title="从候选值选择"
              @click="candOpenField = candOpenField === f.name ? null : f.name"
            >▾</button>
            <!-- 字段动作菜单(#4/#5 变量工作台):引用/提取/注入/断言。
                 fieldActions 门控 — 仅 Canvas 请求体场景传 -->
            <div v-if="candOpenField === f.name" class="cand-list">
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
            <FieldActionMenu
              v-if="fieldActions"
              :field="f"
              :value="String(getValue(f) ?? '')"
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :open="menuField === f.name"
              @toggle="toggleMenu(f)"
              @close="menuField = null"
              @var-insert="(name) => onMenuVarInsert(f, name)"
              @field-extract="(field) => emit('fieldExtract', field)"
              @field-assign="(field, name) => emit('fieldAssign', field, name)"
              @field-promote="(field) => onFieldPromote(field)"
              @field-assert="(field) => emit('fieldAssert', field)"
            />
          </div>
        </div>

        <!-- number(值为模板串 → 降级 text 输入,见文件头注释) -->
        <div v-else-if="f.ui_kind === 'number'" class="ctl-with-var">
          <div class="ctl-cand-wrap">
            <input
              v-if="isTpl(getValue(f))"
              type="text"
              class="ctl tpl"
              :value="getValue(f) as string"
              :placeholder="placeholderFor(f)"
              :disabled="readonly"
              @input="e => setValueTplNum(f, (e.target as HTMLInputElement).value)"
            />
            <input
              v-else
              type="number"
              class="ctl"
              :value="getValue(f) as number | string"
              :placeholder="placeholderFor(f)"
              :disabled="readonly"
              @input="e => setValueNum(f, e)"
            />
            <FieldActionMenu
              v-if="fieldActions"
              :field="f"
              :value="String(getValue(f) ?? '')"
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :open="menuField === f.name"
              @toggle="toggleMenu(f)"
              @close="menuField = null"
              @var-insert="(name) => onMenuVarInsert(f, name)"
              @field-extract="(field) => emit('fieldExtract', field)"
              @field-assign="(field, name) => emit('fieldAssign', field, name)"
              @field-promote="(field) => onFieldPromote(field)"
              @field-assert="(field) => emit('fieldAssert', field)"
            />
          </div>
        </div>

        <!-- boolean(值为模板串 → 降级 text 输入) -->
        <div v-else-if="f.ui_kind === 'boolean'" class="ctl-with-var">
          <input
            v-if="isTpl(getValue(f))"
            type="text"
            class="ctl tpl"
            :value="getValue(f) as string"
            :placeholder="placeholderFor(f)"
            :disabled="readonly"
            @input="e => setValue(f, (e.target as HTMLInputElement).value)"
          />
          <label v-else class="ctl-bool">
            <input
              type="checkbox"
              :checked="Boolean(getValue(f))"
              :disabled="readonly"
              @change="e => setValue(f, (e.target as HTMLInputElement).checked)"
            />
            <span>{{ getValue(f) ? 'true' : 'false' }}</span>
          </label>
          <FieldActionMenu
            v-if="fieldActions"
            :field="f"
            :value="String(getValue(f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === f.name"
            @toggle="toggleMenu(f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- select(值为模板串 → 降级 text 输入:选项列表不含模板值) -->
        <div v-else-if="f.ui_kind === 'select' && f.enum" class="ctl-with-var">
          <input
            v-if="isTpl(getValue(f))"
            type="text"
            class="ctl tpl"
            :value="getValue(f) as string"
            :placeholder="placeholderFor(f)"
            :disabled="readonly"
            @input="e => setValue(f, (e.target as HTMLInputElement).value)"
          />
          <select
            v-else
            class="ctl"
            :value="getValue(f) as string"
            :disabled="readonly"
            @change="e => setValue(f, (e.target as HTMLSelectElement).value)"
          >
            <option value="">— select —</option>
            <option v-for="opt in f.enum" :key="String(opt)" :value="String(opt)">{{ String(opt) }}</option>
          </select>
          <FieldActionMenu
            v-if="fieldActions"
            :field="f"
            :value="String(getValue(f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === f.name"
            @toggle="toggleMenu(f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- textarea -->
        <div v-else-if="f.ui_kind === 'textarea'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-area"
            rows="3"
            :value="getValue(f) as string"
            :placeholder="placeholderFor(f)"
            :disabled="readonly"
            @input="e => setValue(f, (e.target as HTMLTextAreaElement).value)"
          />
          <FieldActionMenu
            v-if="fieldActions"
            :field="f"
            :value="String(getValue(f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === f.name"
            @toggle="toggleMenu(f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- json (dark code editor) -->
        <div v-else-if="f.ui_kind === 'json'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-code"
            rows="4"
            :value="formatJson(getValue(f))"
            placeholder="JSON object"
            :disabled="readonly"
            @input="e => setValue(f, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
          />
          <FieldActionMenu
            v-if="fieldActions"
            :field="f"
            :value="String(getValue(f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === f.name"
            @toggle="toggleMenu(f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
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

    <!-- 其他字段(Type C 逆向面):body 实有键 + plate schema 非绑定字段,合并去重。
         实有键随请求发送;契约字段编辑即写入 body — 默认折叠。 -->
    <div v-if="extraRows.length" class="extras" data-testid="extra-fields">
      <button type="button" class="extras-toggle" @click="extrasOpen = !extrasOpen">
        <span class="extras-arrow" :class="{ open: extrasOpen }">▸</span>
        <span class="extras-title">其他字段 · {{ extraRows.length }}</span>
        <span class="extras-hint">不在接口绑定中 · 已写入的随请求发送</span>
      </button>
      <div v-if="extrasOpen" class="extras-body">
        <div v-for="row in extraRows" :key="row.key" class="extra-row">
          <label class="extra-label">
            <span class="label-text">{{ row.key }}</span>
            <span class="field-path">$.{{ row.key }}</span>
            <span
              class="extra-src"
              :class="row.source"
              :title="row.source === 'schema'
                ? (row.inBody ? 'plate 契约声明,已写入请求体' : 'plate 契约声明;编辑后写入请求体')
                : '请求体实有键,随请求发送'"
            >{{ row.source === 'schema' ? '契约' : '实有' }}</span>
          </label>
          <div class="extra-control">
            <textarea
              v-if="isStructured(extraValue(row.key)) || row.type === 'object' || row.type === 'array'"
              class="ctl ctl-code"
              rows="3"
              :value="formatJson(extraValue(row.key))"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row.key, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
            />
            <label v-else-if="row.type === 'boolean'" class="ctl-bool">
              <input
                type="checkbox"
                :checked="Boolean(extraValue(row.key))"
                :disabled="readonly"
                @change="e => setExtra(row.key, (e.target as HTMLInputElement).checked)"
              />
              <span>{{ extraValue(row.key) ? 'true' : 'false' }}</span>
            </label>
            <input
              v-else-if="row.type === 'number'"
              type="number"
              class="ctl"
              :value="extraValue(row.key) ?? ''"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row.key, (e.target as HTMLInputElement).value === '' ? '' : Number((e.target as HTMLInputElement).value))"
            />
            <input
              v-else
              type="text"
              class="ctl"
              :value="String(extraValue(row.key) ?? '')"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row.key, (e.target as HTMLInputElement).value)"
            />
            <button
              v-if="row.inBody"
              type="button"
              class="extra-del"
              title="从请求体移除该字段"
              :disabled="readonly"
              @click="removeExtra(row.key)"
            >×</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { IOFieldBinding } from '@/types/plate'
import type { VarEntry } from '@/utils/var-registry'
import { getByPath, setByPath } from '@/utils/jsonpath'
import FieldActionMenu from './FieldActionMenu.vue'
import { parseJson } from '../../utils/json'

const props = defineProps<{
  bindings: IOFieldBinding[]
  body: any
  /**
   * 字段动作菜单门控(#4/#5 变量工作台):仅 Canvas 请求体场景传。
   * 开启后每个字段控件挂 ☰ 菜单(引用/提取/注入/断言);
   * StrategyForm 复用本组件处不传 → 模板零变化。
   */
  fieldActions?: boolean
  /** 引用子列表(config/数据集出身,插 ${var.x} 文本)— Canvas 传入 */
  varChoices?: VarEntry[]
  /** 注入子列表(extract 出身 + 时序门控 disabled 标记)— Canvas 传入 */
  injectChoices?: Array<VarEntry & { disabled?: boolean }>
  /**
   * 候选值映射(#2 策略改造):字段名 → 候选 JSONPath 列表。
   * 策略表单场景:assertion.target / extract.expression 从响应
   * assertable_fields 选,不手打;缺省无候选按钮。
   */
  candidates?: Record<string, string[]>
  /**
   * 只读门控(IO 双签卡片 Response 页):契约参考用 — 控件 disabled、
   * 不发 update:body;☰ 菜单保留(提取/断言仍可用)。
   */
  readonly?: boolean
  /**
   * 字段域(IO 双签卡片):'request'(默认四项菜单)|
   * 'response'(契约参考,菜单仅 提取/断言 两项)。
   */
  domain?: 'request' | 'response'
  /** 可断言字段的 plate 域路径列表(Response 页 ✓ 标线) */
  assertable?: string[]
  /**
   * plate 非绑定字段(请求 schema 有、binding 无 — Canvas 的 reqTypeC):
   * 并入「其他字段」折叠区,可编辑;编辑即写入 body(未编辑不随请求发送)。
   */
  unboundFields?: Array<{ name: string; path: string; type?: string; default?: unknown }>
}>()
const emit = defineEmits<{
  'update:body': [any]
  /** 快捷策略创建(菜单动作,Canvas 落地为策略骨架) */
  'fieldExtract': [field: IOFieldBinding]
  'fieldAssign': [field: IOFieldBinding, varName: string]
  'fieldAssert': [field: IOFieldBinding]
  /** 插入 ${var.<name>} 文本(原 Ⓥ 行为,Canvas 可用于引导提示) */
  'varInsert': [field: IOFieldBinding, name: string]
  /** 设为变量(D8 提升):值整串替换为 ${var.<name>},原值随事件上抛登记默认值 */
  'varPromote': [field: IOFieldBinding, name: string, value: unknown]
}>()

/** 候选下拉开合状态(同屏至多一个)— 存字段名而非对象引用:
 *  props.bindings 被 Vue 包 reactive proxy,v-for 元素与原始对象
 *  === 不等(菜单 menuField 踩过同坑,存 name 后列表才能展开) */
const candOpenField = ref<string | null>(null)
function candidatesFor(f: IOFieldBinding): string[] {
  return props.candidates?.[f.name] ?? []
}
function applyCandidate(f: IOFieldBinding, c: string) {
  setValue(f, c)
  candOpenField.value = null
}

/**
 * 字段动作菜单开合状态(同屏至多一个;与候选下拉互斥)。
 * 存字段名而非对象引用 — props.bindings 会被 Vue 包 reactive proxy,
 * v-for 元素与调用方原始对象引用不等(=== 失败,菜单不开)。
 */
const menuField = ref<string | null>(null)
function toggleMenu(f: IOFieldBinding) {
  candOpenField.value = null
  menuField.value = menuField.value === f.name ? null : f.name
}

/**
 * 菜单"引用共享变量"插值:字符串现值追加(部分模板 ORD-${var.x});
 * 非字符串(number/boolean)或空值整串替换 — String(5) 拼出
 * '5${var.x}' 是垃圾值,typed 字段模板只能整串。
 */
function onMenuVarInsert(f: IOFieldBinding, name: string) {
  const cur = getValue(f)
  const tpl = `\${var.${name}}`
  setValue(f, typeof cur === 'string' && cur !== '' ? cur + tpl : tpl)
  emit('varInsert', f, name)
  menuField.value = null
}

/**
 * 菜单"设为变量"(D8 提升语义):与"引用共享变量"的**追加**不同 —
 * ① 值整串替换为 ${var.<name>};② 变量名默认取字段名,同名(共享
 * 变量/extract 任一出身)自动加 _2/_3 后缀;③ 原值随 varPromote
 * 上抛,由 Canvas → CaseComposer 登记进 definition.config.vars。
 */
function onFieldPromote(f: IOFieldBinding) {
  const original = getValue(f)
  const base = f.name.replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
  const taken = new Set([
    ...(props.varChoices ?? []).map((v) => v.name),
    ...(props.injectChoices ?? []).map((v) => v.name),
  ])
  let name = base
  let n = 2
  while (taken.has(name)) name = `${base}_${n++}`
  setValue(f, `\${var.${name}}`)
  emit('varPromote', f, name, original)
  menuField.value = null
}

/**
 * 值是否为模板串(${...})— number/boolean/select 控件遇模板降级
 * text 输入:number input 拒显非数字、checkbox/select 无法承载串值。
 * 运行期引擎(resolve_template)对整串模板按变量原类型解析,合法。
 */
function isTpl(v: unknown): boolean {
  return typeof v === 'string' && v.includes('${')
}

/** number 控件输入:清空存 ''(对齐「其他字段」分支约定,不落幻影 0) */
function setValueNum(f: IOFieldBinding, e: Event) {
  const v = (e.target as HTMLInputElement).value
  setValue(f, v === '' ? '' : Number(v))
}

/** number 字段模板态输入:纯数字串回归 number;模板/混排保持字符串 */
function setValueTplNum(f: IOFieldBinding, v: string) {
  if (v !== '' && !isTpl(v) && !Number.isNaN(Number(v))) {
    setValue(f, Number(v))
    return
  }
  setValue(f, v)
}

// Type A + Type B: 有 binding 的都显示; Type C (无 binding 的 schema 字段) 走 hiddenFields 不在此显示
const visibleFields = computed(() => props.bindings)

/**
 * 其他字段(Type C 逆向面)行视图,两个来源合并去重:
 * ① body 实有键(body 顶层键 − binding 根段;binding $.cfg.timeout 覆盖键 cfg)
 * ② plate schema 声明但无 binding 的字段(unboundFields,请求侧 Canvas 传入)
 * source=行来源标签;inBody=是否已写入 body(决定随请求发送 + 可删除)。
 * ② 未编辑前不进 body → 不发送;编辑即写入(setExtra)转为实有。
 */
interface ExtraRowView {
  key: string
  source: 'body' | 'schema'
  inBody: boolean
  /** schema 声明类型(body 实有行无) — 控件按此渲染:boolean 勾选/number 数字框/object·array JSON 域 */
  type?: string
  /** schema 默认值(契约行):未写入 body 时以 placeholder 透出,编辑写入 */
  default?: unknown
}

const extraRows = computed<ExtraRowView[]>(() => {
  const bodyObj =
    props.body && typeof props.body === 'object' && !Array.isArray(props.body)
      ? (props.body as Record<string, unknown>)
      : null
  const roots = new Set(
    props.bindings.map((b) => b.path.replace(/^\$\./, '').split('.')[0])
  )
  const schemaTypes = new Map(
    (props.unboundFields ?? []).map((f) => [f.name, f.type ?? 'string'])
  )
  const rows: ExtraRowView[] = []
  // ① body 实有且未绑定的键(schema 已声明的标 契约,与 ② 去重)
  for (const k of bodyObj ? Object.keys(bodyObj) : []) {
    if (roots.has(k)) continue
    rows.push({
      key: k,
      source: schemaTypes.has(k) ? 'schema' : 'body',
      inBody: true,
      type: schemaTypes.get(k),
    })
  }
  // ② plate 契约声明但未写入 body 的(编辑后转实有;默认值 placeholder 透出)
  const schemaDefaults = new Map(
    (props.unboundFields ?? []).map((f) => [f.name, f.default])
  )
  for (const f of props.unboundFields ?? []) {
    if (bodyObj && f.name in bodyObj) continue
    if (roots.has(f.name)) continue
    rows.push({
      key: f.name,
      source: 'schema',
      inBody: false,
      type: f.type ?? 'string',
      default: schemaDefaults.get(f.name),
    })
  }
  return rows
})

/** 折叠区默认收起(挂载即折叠,不跨步骤记忆) */
const extrasOpen = ref(false)

function extraValue(k: string): unknown {
  return props.body?.[k]
}

/** 结构值(对象/数组)走 JSON 域,其余按原始值文本编辑(未声明 → 类型未知,text 是诚实兜底) */
function isStructured(v: unknown): boolean {
  return typeof v === 'object' && v !== null
}

function setExtra(k: string, val: unknown) {
  if (props.readonly) return
  const next = { ...(props.body || {}) }
  next[k] = val
  emit('update:body', next)
}

function removeExtra(k: string) {
  if (props.readonly) return
  const next = { ...(props.body || {}) }
  delete next[k]
  emit('update:body', next)
}

/** 契约行未写入时以 schema 默认值作 placeholder(灰字提示 ≠ 值,不随请求发送) */
function extraPlaceholder(row: ExtraRowView): string {
  if (row.inBody || row.default === undefined || row.default === null) return ''
  if (typeof row.default === 'object') return JSON.stringify(row.default, null, 2)
  return String(row.default)
}

function getValue(f: IOFieldBinding): unknown {
  if (!props.body) return f.default ?? f.example ?? ''
  return getByPath(props.body, f.path.replace(/^\$\./, '')) ?? f.default ?? f.example ?? ''
}

function setValue(f: IOFieldBinding, val: unknown) {
  if (props.readonly) return
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

/** JSON field semantics: empty → null, non-JSON → raw string (user is typing). */
function parseJsonOrRaw(s: string): unknown {
  return s.trim() ? parseJson(s, s) : null
}

function formatJson(v: unknown): string {
  if (v === null || v === undefined || v === '') return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v, null, 2)
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
/* assertable ✓ 标(Response 页契约参考线) */
.assertable-mark {
  font-size: 11px; font-weight: 700; color: #059669;
}
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

/* 模板态降级输入(typed 字段值为 ${...}):等宽字体 + 靛蓝底提示语域切换 */
.ctl.tpl {
  font-family: var(--font-mono); font-size: 12px;
  border-color: #c7d2fe; background: #f5f7ff;
}

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

/* ── 其他字段折叠区:琥珀警示(浅底 + 左条),与 sk-generated 橙同族 ── */
.extras {
  padding: 8px 10px 8px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-left: 3px solid #f59e0b;
  border-radius: 8px;
}
.extras-toggle {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 0; border: none; background: transparent;
  font-size: 12px; text-align: left; cursor: pointer;
}
.extras-arrow {
  display: inline-block; font-size: 10px; color: #b45309;
  transition: transform 0.15s;
}
.extras-arrow.open { transform: rotate(90deg); }
.extras-title { font-weight: 600; color: #92400e; }
.extras-hint { margin-left: auto; font-size: 11px; color: #b45309; }
.extras-body { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.extra-row { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.extra-label { display: flex; align-items: center; gap: 6px; font-size: 12px; }
/* 来源标签:实有(body 键,随请求发送)/ 契约(plate schema 声明) */
.extra-src {
  font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px;
  background: #fef3c7; color: #92400e; cursor: default;
}
.extra-src.schema { background: #ecf5ff; color: #409eff; }
.extra-control { display: flex; gap: 6px; align-items: flex-start; }
.extra-control .ctl { flex: 1; min-width: 0; }
.extra-del {
  flex-shrink: 0; width: 26px; height: 32px;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  color: #94a3b8; cursor: pointer; font-size: 14px; line-height: 1;
  transition: all 0.15s;
}
.extra-del:hover:not(:disabled) { border-color: #fca5a5; background: #fef2f2; color: #ef4444; }
.extra-del:disabled { cursor: not-allowed; opacity: 0.5; }
</style>
