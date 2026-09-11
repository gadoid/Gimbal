<!--
  VariableDetailPanel.vue — 数据集单变量详情面板(spec v2 §6 变量优先双模式)

  「单变量」模式的独立渲染(不为与网格风格一致妥协):
    基线   — config.vars[varName] 唯一编辑入口(emit set-baseline → 编辑器
             baselineDirty → 保存基线链)
    引用面 — 该变量全部引用位(步骤 · body/headers · 字段路径;期望引用
             带 ↗ 跳编排器断言卡,emit jump)
    取数   — 直接向被测系统查询选值(ValueSourcePicker 复用,零改动):
             步骤上下文(服务 URL + 查询别名 + 参数预填)→ 查询视图
             (索引 query_safe 过滤)→ 行选 → 列选值 → 应用到基线/行
    行值   — 该变量在各数据行的值(继承态标注;emit set-cell)

  本组件持有取数 IO(index/rows 两次 api);行/基线只上抛不落地。
-->
<template>
  <div class="vdp">
    <div class="vdp-head">
      <h3 class="vdp-title mono">{{ varName }}</h3>
      <span v-if="!refs.length" class="vdp-unref">未被引用 — 模板化(编排器)后在此取数/填值</span>
      <span v-else class="muted">{{ refs.length }} 处引用</span>
    </div>

    <section class="vdp-card">
      <div class="vdp-card-title">基线(config.vars)</div>
      <input
        class="vdp-input"
        :value="baseline"
        :aria-label="`基线 ${varName}`"
        placeholder="(未声明 — 输入即声明)"
        @input="(e: Event) => emit('set-baseline', (e.target as HTMLInputElement).value)"
      />
    </section>

    <section class="vdp-card">
      <div class="vdp-card-title">引用面</div>
      <div v-if="!refs.length" class="muted vdp-empty">无引用</div>
      <div v-for="(r, i) in refs" :key="`${r.stepIndex}:${r.source}:${i}:${r.field}`" class="vdp-ref">
        <span class="vdp-ref-step">步骤{{ r.stepIndex + 1 }} · {{ stepLabelOf(r.stepIndex) }}</span>
        <span class="vdp-ref-where mono">{{ r.source === 'expect' ? `断言 ${r.field}` : `${r.source} · ${r.field}` }}</span>
        <span v-if="r.source === 'expect'" class="exp-col-badge" :title="`断言 ${r.field} ${r.expect?.operator}`">期望</span>
        <button v-if="r.source === 'expect'" type="button" class="exp-jump" title="跳编排器断言卡" @click="emit('jump', r)">↗</button>
      </div>
    </section>

    <section class="vdp-card">
      <div class="vdp-card-title">取数(向被测系统查询选值)</div>
      <div class="vdp-query-row">
        <label class="vdp-query-item">
          <span class="vdp-query-label">步骤上下文</span>
          <el-select v-model="stepChoice" size="small" class="vdp-select">
            <el-option
              v-for="s in stepContexts"
              :key="`sc:${s.index}`"
              :value="s.index"
              :label="`步骤${s.index + 1} · ${s.label}`"
            />
          </el-select>
        </label>
        <label class="vdp-query-item">
          <span class="vdp-query-label">查询视图</span>
          <el-select v-model="viewChoice" size="small" class="vdp-select" :loading="viewsLoading">
            <el-option v-for="v in views" :key="v.name" :value="v.name" :label="`${v.name}(${v.path})`" />
          </el-select>
        </label>
        <el-button size="small" type="primary" plain :disabled="!viewChoice" @click="onQuery">查询取数</el-button>
      </div>
      <div v-if="viewsError" class="vdp-error">视图索引加载失败:{{ viewsError }} — <button type="button" class="vdp-linkbtn" @click="loadViews">重试</button></div>
      <div v-else-if="!viewsLoading && !views.length" class="muted vdp-empty">无 query-safe 查询视图可取数</div>

      <!-- 取数结果 + 应用 -->
      <div v-if="pickedValue !== '' || pickedTouched" class="vdp-apply">
        <div class="vdp-apply-row">
          <span class="vdp-query-label">取数值</span>
          <input v-model="pickedValue" class="vdp-input vdp-picked" :aria-label="`取数值 ${varName}`" />
          <el-button size="small" plain @click="onApplyBaseline">设为基线</el-button>
          <el-select v-model="applyRowChoice" size="small" class="vdp-select vdp-apply-row-select" placeholder="写入行…">
            <el-option v-for="(n, i) in caseNames" :key="`ar:${i}`" :value="i" :label="n || `data-${i + 1}`" />
          </el-select>
          <el-button size="small" plain :disabled="applyRowChoice === null || applyRowChoice === undefined" @click="onApplyRow">写入该行</el-button>
        </div>
      </div>
    </section>

    <section class="vdp-card">
      <div class="vdp-card-title">行值</div>
      <div v-if="!rows.length" class="muted vdp-empty">暂无数据行</div>
      <div v-for="(row, i) in rows" :key="`rv:${i}`" class="vdp-rowval">
        <span class="vdp-rowval-name mono">{{ caseNames[i] || `data-${i + 1}` }}</span>
        <span class="vdp-rowval-flag" :class="hasOwn(row) ? 'ovr' : 'inh'">{{ hasOwn(row) ? '覆写' : '继承基线' }}</span>
        <input
          class="vdp-input"
          :value="row[varName] ?? ''"
          :placeholder="baseline"
          :aria-label="`${caseNames[i] || `data-${i + 1}`} ${varName}`"
          @input="(e: Event) => emit('set-cell', i, (e.target as HTMLInputElement).value)"
        />
      </div>
    </section>

    <!-- 行集选择器(ValueSourcePicker 复用,零改动;数据全本组件供给) -->
    <ValueSourcePicker
      v-model="pickerOpen"
      :view="viewChoice"
      :label="pLabel"
      :columns="pColumns"
      :rows="pRows"
      :truncated="pTruncated"
      :fetched-at="pFetchedAt"
      :stale="pStale"
      :loading="pLoading"
      :error="pError"
      :param-fields="pParamFields"
      :param-prefill="pParamPrefill"
      @select="onPickerSelect"
      @refresh="onPickerRefresh"
      @query="onPickerQuery"
      @back-params="pError = null"
    />

    <!-- 列选值 overlay:行已选,点列取值(变量可映射行内任意列) -->
    <div v-if="chooserRow" class="vdp-chooser-overlay" @click.self="chooserRow = null">
      <div class="vdp-chooser" role="dialog" aria-modal="true">
        <header class="vdp-chooser-head">
          <span>选择取值列</span>
          <button type="button" class="vdp-linkbtn" aria-label="关闭" @click="chooserRow = null">✕</button>
        </header>
        <div class="vdp-chooser-body">
          <button
            v-for="c in chooserColumns"
            :key="`cc:${c}`"
            type="button"
            class="vdp-chooser-cell"
            @click="onPickColumn(c)"
          >
            <code class="mono">{{ c }}</code>
            <span class="vdp-chooser-val mono">{{ chooserCell(c) }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import ValueSourcePicker from '@/components/composer/ValueSourcePicker.vue'
import { ApiError } from '@/api/http'
import { fetchQueryViewIndex, fetchQueryViewRows, type QueryViewIndexEntry } from '@/api/query-views'
import { resolveQueryCtx, type PanelStepContext, type QueryCtxConfig } from '@/utils/query-context'
import type { GridVarColumn } from '@/utils/dataset-segments'

const props = defineProps<{
  varName: string
  /** config.vars[varName] 显示串(未声明 = '') */
  baseline: string
  /** 该变量全部引用位(含期望引用) */
  refs: GridVarColumn[]
  rows: Array<Record<string, any>>
  caseNames: string[]
  stepContexts: PanelStepContext[]
  queryConfig: QueryCtxConfig
}>()

const emit = defineEmits<{
  'set-baseline': [value: string]
  'set-cell': [rowIndex: number, value: string]
  'jump': [ref: GridVarColumn]
}>()

function stepLabelOf(i: number): string {
  return props.stepContexts[i]?.label || `Step ${i + 1}`
}
function hasOwn(row: Record<string, any>): boolean {
  return Object.prototype.hasOwnProperty.call(row, props.varName)
}

// ── 取数:视图索引(query_safe 过滤 — 编辑期查询不得打变更型端点)──────
const views = ref<QueryViewIndexEntry[]>([])
const viewsLoading = ref(false)
const viewsError = ref('')
const viewChoice = ref('')

async function loadViews() {
  viewsLoading.value = true
  viewsError.value = ''
  try {
    const idx = await fetchQueryViewIndex()
    views.value = idx.filter(v => v.query_safe)
    if (!views.value.some(v => v.name === viewChoice.value)) {
      viewChoice.value = views.value[0]?.name ?? ''
    }
  } catch (e) {
    viewsError.value = e instanceof Error ? e.message : String(e)
  } finally {
    viewsLoading.value = false
  }
}

/** 步骤上下文默认 = 首个引用位所在步骤;无引用退第 1 步(取数不强依赖引用) */
const stepChoice = ref(
  props.refs.find(r => props.stepContexts.some(s => s.index === r.stepIndex))?.stepIndex
    ?? props.stepContexts[0]?.index
    ?? 0,
)

onMounted(() => { void loadViews() })

// ── 取数:picker 状态(Canvas VsPickerState 同构,减 group/anchor 面)────
const pickerOpen = ref(false)
const pLabel = ref('')
const pColumns = ref<string[]>([])
const pRows = ref<Array<Record<string, unknown>>>([])
const pTruncated = ref(false)
const pFetchedAt = ref('')
const pStale = ref(false)
const pLoading = ref(false)
const pError = ref<{ code: string; message: string } | null>(null)
const pParamFields = ref<string[]>([])
const pParamPrefill = ref<Record<string, string>>({})
/** 最近一次携参(refresh 复用,§13.5) */
let lastParams: Record<string, string> | null = null

function currentView(): QueryViewIndexEntry | undefined {
  return views.value.find(v => v.name === viewChoice.value)
}

/** 查询取数:先定参数面(§13.5 同名约定预填自步骤上下文 body 顶层字面量),
 *  再开选择器;无参视图直拉行集。 */
function onQuery() {
  const view = currentView()
  const fields = view?.query_params ?? []
  const bodyTop = props.stepContexts.find(s => s.index === stepChoice.value)?.bodyTop ?? {}
  const prefill: Record<string, string> = {}
  for (const p of fields) {
    const v = bodyTop[p]
    prefill[p] = typeof v === 'string'
      ? (v && !v.includes('${') ? v : '')
      : (typeof v === 'number' || typeof v === 'boolean') && v !== null ? String(v) : ''
  }
  pParamFields.value = fields
  pParamPrefill.value = prefill
  pError.value = null          // R1 开壳清错(残错会困住参数面)
  pickerOpen.value = true
  if (!fields.length) void loadRows(false, null)
}

/** 参数段确认:空值剔除(未填 = 未供给,后端缺键 422 兜底)→ 携参拉数。 */
function onPickerQuery(values: Record<string, string>) {
  const params: Record<string, string> = {}
  for (const [k, v] of Object.entries(values)) {
    const t = v.trim()
    if (t) params[k] = t
  }
  void loadRows(false, params)
}

function onPickerRefresh() {
  void loadRows(true, lastParams)
}

/** 拉行集:呈现列 = 视图声明列(索引携带);ApiError → 降级态(§7.5)。 */
async function loadRows(refresh: boolean, params: Record<string, string> | null) {
  const view = currentView()
  const ctxStep = props.stepContexts.find(s => s.index === stepChoice.value)
  if (!view || !ctxStep) return
  lastParams = params
  pLoading.value = true
  pError.value = null
  pRows.value = []
  pColumns.value = []
  pLabel.value = ''
  try {
    const ctx = resolveQueryCtx(ctxStep, props.queryConfig)
    const res = await fetchQueryViewRows(view.name, {
      refresh,
      serviceUrl: ctx.serviceUrl,
      queryAlias: ctx.queryAlias,
      ...(params && Object.keys(params).length ? { params } : {}),
    })
    pRows.value = res.rows
    const label = Object.keys(res.rows[0] ?? {})[0] ?? ''
    pLabel.value = label
    const cols = new Set<string>(view.columns ?? [])
    if (label) cols.add(label)
    pColumns.value = [...cols]
    pTruncated.value = res.truncated
    pFetchedAt.value = res.fetched_at
    pStale.value = res.stale
  } catch (e) {
    pError.value = e instanceof ApiError
      ? { code: String(e.code ?? ''), message: e.message }
      : { code: '', message: e instanceof Error ? e.message : String(e) }
  } finally {
    pLoading.value = false
  }
}

// ── 行选 → 列选值 → 应用 ──────────────────────────────────────────
const chooserRow = ref<Record<string, unknown> | null>(null)
const pickedValue = ref('')
const pickedTouched = ref(false)
const applyRowChoice = ref<number | null>(null)

/** 呈现列 = label 打头 + 视图列去重(与 picker 呈现面一致)。 */
const chooserColumns = computed(() => [
  pLabel.value,
  ...pColumns.value.filter(c => c !== pLabel.value),
])

function chooserCell(col: string): string {
  const v = chooserRow.value?.[col]
  return v === undefined || v === null ? '--' : String(v)
}

function onPickerSelect(row: Record<string, unknown>) {
  pickerOpen.value = false
  chooserRow.value = row
}

function onPickColumn(col: string) {
  const v = chooserRow.value?.[col]
  if (v !== undefined && v !== null) {
    pickedValue.value = String(v)
    pickedTouched.value = true
  }
  chooserRow.value = null
}

function onApplyBaseline() {
  emit('set-baseline', pickedValue.value)
  ElMessage.success(`已应用到基线 ${props.varName}(记得「保存基线」)`)
}

function onApplyRow() {
  if (applyRowChoice.value === null || applyRowChoice.value === undefined) return
  emit('set-cell', applyRowChoice.value, pickedValue.value)
  ElMessage.success(`已写入第 ${applyRowChoice.value + 1} 行 ${props.varName}`)
}
</script>

<style scoped>
.vdp { display: flex; flex-direction: column; gap: 12px; padding: 14px 16px; }
.vdp-head { display: flex; align-items: center; gap: 10px; }
.vdp-title { margin: 0; font-size: 15px; color: var(--accent); }
.vdp-unref { font-size: 11px; color: var(--color-text-secondary); background: #f1f5f9; padding: 2px 8px; border-radius: 3px; }
.muted { color: var(--color-text-secondary); font-size: 12px; }
.mono { font-family: var(--font-mono); }

.vdp-card {
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 10px 12px; background: #fff;
  display: flex; flex-direction: column; gap: 8px;
}
.vdp-card-title { font-size: 12px; font-weight: 700; color: #475569; }
.vdp-empty { padding: 2px 0; }

.vdp-input {
  border: 1px solid #cbd5e1; background: #fff; border-radius: 4px;
  padding: 4px 8px; font-family: var(--font-mono); font-size: 12px;
  outline: none; box-sizing: border-box; width: 100%;
  color: var(--color-text-primary);
}
.vdp-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15); }
.vdp-input::placeholder { color: #94a3b8; }

/* 引用面 */
.vdp-ref { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 2px 0; }
.vdp-ref-step { color: #334155; min-width: 130px; }
.vdp-ref-where { color: var(--color-text-secondary); flex: 1; }
.vdp-ref .exp-col-badge { font-size: 10px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 1px 5px; border-radius: 3px; }
.vdp-ref .exp-jump { border: none; background: transparent; color: #7c3aed; cursor: pointer; font-size: 12px; padding: 0 2px; }
.vdp-ref .exp-jump:hover { color: #4c1d95; }

/* 取数 */
.vdp-query-row { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
.vdp-query-item { display: flex; flex-direction: column; gap: 4px; }
.vdp-query-label { font-size: 11px; color: var(--color-text-secondary); }
.vdp-select { width: 240px; }
.vdp-error { font-size: 11px; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 4px 8px; }
.vdp-linkbtn { border: none; background: none; color: #4f46e5; cursor: pointer; font-size: 11px; padding: 0; }
.vdp-linkbtn:hover { text-decoration: underline; }

.vdp-apply { border-top: 1px dashed var(--color-border-tertiary); padding-top: 8px; }
.vdp-apply-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.vdp-picked { max-width: 260px; }
.vdp-apply-row-select { width: 160px; }

/* 行值 */
.vdp-rowval { display: grid; grid-template-columns: 120px 64px 1fr; gap: 8px; align-items: center; padding: 2px 0; }
.vdp-rowval-name { font-size: 12px; color: var(--accent); }
.vdp-rowval-flag { font-size: 10px; padding: 1px 6px; border-radius: 3px; text-align: center; }
.vdp-rowval-flag.inh { color: #64748b; background: #f1f5f9; }
.vdp-rowval-flag.ovr { color: #b45309; background: #fef3c7; }

/* 列选值 overlay(自绘,RunDialog/ValueSourcePicker 同款惯例) */
.vdp-chooser-overlay {
  position: fixed; inset: 0; z-index: 2200;
  background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: flex-start; justify-content: center; padding-top: 14vh;
}
.vdp-chooser {
  width: 480px; max-width: calc(100vw - 32px);
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 10px; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
}
.vdp-chooser-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; border-bottom: 1px solid var(--color-border-tertiary);
  font-size: 13px; font-weight: 600;
}
.vdp-chooser-body { padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; max-height: 320px; overflow-y: auto; }
.vdp-chooser-cell {
  display: flex; justify-content: space-between; gap: 12px; align-items: center;
  border: 1px solid var(--color-border-tertiary); background: #f8fafc;
  border-radius: 6px; padding: 6px 10px; cursor: pointer; text-align: left;
}
.vdp-chooser-cell:hover { border-color: var(--accent); background: #eef2ff; }
.vdp-chooser-cell code { font-size: 11px; color: var(--color-text-secondary); }
.vdp-chooser-val { font-size: 12px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }
</style>
