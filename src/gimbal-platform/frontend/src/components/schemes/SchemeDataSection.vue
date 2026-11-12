<script setup lang="ts">
/**
 * 方案工作台 · 数据区:数据集多选(行级勾选)、失效标注与移除、内联维护。
 *
 * D1 能力承接(数据集独立路由退役后,"维护方案数据集"全部在此可做):
 * 新建 / 编辑(改名 + 行数据)/ 删除。
 * 2026-11-12 编辑面重构:「变量即列」网格回迁(DataSetGridEditor)—— 列
 * 派生自场景 config.vars 标量变量 + @slot.* 账号列,与后端 `_scalar_vars`
 * 调色板门同规则;稀疏行三态(缺省=继承基线/""=显式空/覆写)。
 * 原始粘贴(JSON/TSV/CSV 自动识别)收进「高级粘贴」折叠区,应用后整表
 * 替换网格行。CSV 导出为简单序列化,列序 = 列宇宙序,与粘贴导入互为往返
 * —— 不复活已作废的 var-palette 模板协议(dataset v2 T6-T8,D1 作废)。
 * 失效键(行键 ∉ 列宇宙)保存会被后端 422 拒收(undeclared_var)→ 提交
 * 禁用,给一键移除。
 * 编辑保存保留既有 varUnlocks(PUT 整体替换语义;网格内可放开/收回)。
 */
import { computed, ref } from 'vue'
import type { DataSetRow, DataSetSummary } from '@/types/scenario-composer'
import { createDataSet, updateDataSet, getDataSet } from '@/api/scenario-composer'
import { deriveVarColumns, deadKeysOf, exportColumnOrder, type GridColumn } from '@/utils/dataset-grid'
import DataSetGridEditor from '@/components/schemes/DataSetGridEditor.vue'
import { downloadFile } from '@/utils/download'
import Papa from 'papaparse'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

type Sel = { datasetId: string; rowIndexes?: number[] }

const props = defineProps<{
  modelValue: Sel[]
  dataSets: DataSetSummary[]
  scenarioId: string
  /** 场景 config.vars(网格列宇宙来源;null = 场景草稿未含) */
  configVars: Record<string, unknown> | null
  /** 场景级 var_locks(锁列默认隐藏) */
  varLocks: string[]
  /** definition.steps(引用位/账号列候选/契约描述) */
  steps: unknown[]
}>()
const emit = defineEmits<{ 'update:modelValue': [v: Sel[]]; saved: []; delete: [datasetId: string] }>()

const liveIds = computed(() => new Set(props.dataSets.map((d) => d.datasetId)))
const dead = computed(() => props.modelValue.filter((s) => !liveIds.value.has(s.datasetId)))
const rowsOf = (d: DataSetSummary) =>
  Array.from({ length: (d as { rowCount?: number }).rowCount ?? 0 }, (_, i) => i)

function toggleDataset(ds: DataSetSummary, on: boolean) {
  const rest = props.modelValue.filter((s) => s.datasetId !== ds.datasetId)
  emit('update:modelValue', on
    ? [...rest, { datasetId: ds.datasetId, rowIndexes: rowsOf(ds) }]
    : rest)
}
function toggleRow(dsId: string, idx: number, on: boolean) {
  const cur = props.modelValue.find((s) => s.datasetId === dsId)
  if (!cur) return
  const set = new Set(cur.rowIndexes ?? [])
  on ? set.add(idx) : set.delete(idx)
  const next = [...set].sort((a, b) => a - b)
  if (!next.length) {  // 行全清 = 取消整库
    emit('update:modelValue', props.modelValue.filter((s) => s.datasetId !== dsId))
    return
  }
  emit('update:modelValue',
    props.modelValue.map((s) => (s.datasetId === dsId ? { ...s, rowIndexes: next } : s)))
}
const isSelected = (dsId: string) => props.modelValue.some((s) => s.datasetId === dsId)
const rowChecked = (dsId: string, i: number) =>
  props.modelValue.find((s) => s.datasetId === dsId)?.rowIndexes?.includes(i) ?? false

function dropDead() {
  emit('update:modelValue', props.modelValue.filter((s) => liveIds.value.has(s.datasetId)))
}

/** 删除数据集:区内先确认(新栈 confirmAction,取消/ESC=false),
 *  确认后上抛工作台落库。按钮在 label 外,避免触发 tile 的勾选。 */
async function removeDataset(d: DataSetSummary) {
  const name = d.name || d.datasetId
  const ok = await confirmAction(
    `删除数据集「${name}」?此操作不可恢复。`, '删除数据集',
    { type: 'warning', danger: true, confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  if (ok) emit('delete', d.datasetId)
}

// ── 内联维护对话框(新建 / 编辑)─────────────────────────────────
const dialogOpen = ref(false)
const mode = ref<'create' | 'edit'>('create')
const formName = ref('')
/** 网格工作行(v-model:行对象由网格原位改写;行级操作换新数组)。
 *  `__rowKey`(服务端敏感列并回键)之类未知键在克隆后原样保留。 */
const workingRows = ref<Array<Record<string, unknown>>>([])
const workingVarUnlocks = ref<string[]>([])
const saving = ref(false)
const loadingExisting = ref(false)
/** 编辑目标 id(文件名兜底;varUnlocks 在工作区,PUT 整体替换随保存带回) */
const editingId = ref<string | null>(null)
/** 高级粘贴 textarea(应用后清空) */
const rowsText = ref('')

/** 列宇宙(与网格同一纯函数派生)→ 失效键 → 导出列序 */
const columns = computed<GridColumn[]>(() =>
  deriveVarColumns(props.configVars, workingRows.value, props.varLocks, workingVarUnlocks.value))
const deadKeys = computed(() => deadKeysOf(columns.value, workingRows.value))

function openCreate() {
  mode.value = 'create'
  editingId.value = null
  formName.value = `数据集 ${props.dataSets.length + 1}`
  workingRows.value = []
  workingVarUnlocks.value = []
  rowsText.value = ''
  dialogOpen.value = true
}

async function openEdit(d: DataSetSummary) {
  mode.value = 'edit'
  editingId.value = d.datasetId
  formName.value = d.name || d.datasetId
  workingRows.value = []
  workingVarUnlocks.value = []
  rowsText.value = ''
  dialogOpen.value = true
  loadingExisting.value = true
  try {
    const full = await getDataSet(d.datasetId)
    formName.value = full.name
    // 克隆到工作区:未知键(__rowKey 等)原样随 PUT 回传(服务端并回)
    workingRows.value = (full.rows ?? []).map((r) => ({ ...(r as Record<string, unknown>) }))
    workingVarUnlocks.value = [...(full.varUnlocks ?? [])]
  } catch (e) {
    showError('加载', e)
    dialogOpen.value = false
  } finally {
    loadingExisting.value = false
  }
}

// ── 高级粘贴:JSON → TSV → CSV(自动识别),应用后整表替换 ────────

/** 数组形态校验:每行对象 + 值限标量(DataSetRow 契约)。 */
function coerceRows(parsed: unknown): { rows?: DataSetRow[]; error?: string } {
  if (!Array.isArray(parsed) || !parsed.length) return { error: '需要非空数组,每行一个对象' }
  const rows: DataSetRow[] = []
  for (let i = 0; i < parsed.length; i++) {
    const row = parsed[i]
    if (typeof row !== 'object' || row === null || Array.isArray(row)) {
      return { error: `第 ${i + 1} 行不是对象` }
    }
    for (const [k, v] of Object.entries(row)) {
      const t = typeof v
      if (v !== null && t !== 'string' && t !== 'number' && t !== 'boolean') {
        return { error: `第 ${i + 1} 行字段「${k}」的值必须是字符串/数字/布尔` }
      }
    }
    rows.push(row as DataSetRow)
  }
  return { rows }
}

function parseTsv(text: string): { rows?: DataSetRow[]; error?: string } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (lines.length < 2) return { error: 'TSV 需要表头行 + 至少一行数据(以 Tab 分隔)' }
  const header = lines[0].split('\t').map((h) => h.trim())
  const rows = lines.slice(1).map((line) => {
    const cells = line.split('\t')
    const row: DataSetRow = {}
    header.forEach((h, i) => { row[h || `col${i}`] = (cells[i] ?? '').trim() })
    return row
  })
  return { rows }
}

function parseCsv(text: string): { rows?: DataSetRow[]; error?: string } {
  const res = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: true })
  if (res.errors.length) return { error: `CSV 解析失败:${res.errors[0].message}` }
  if (!res.data.length) return { error: '需要表头行 + 至少一行数据(以逗号分隔)' }
  return { rows: res.data as DataSetRow[] }
}

/** 粘贴内容自动识别:JSON(以 [ 开头)/ TSV(含 Tab)/ CSV 兜底。 */
function parseInput(text: string): { rows?: DataSetRow[]; error?: string; format?: string } {
  const trimmed = text.trim()
  if (!trimmed) return {}
  if (trimmed.startsWith('[')) {
    try {
      return { format: 'JSON', ...coerceRows(JSON.parse(trimmed)) }
    } catch {
      return { error: '不是合法 JSON' }
    }
  }
  if (trimmed.startsWith('{')) return { error: '不是合法 JSON(需要数组,每行一个对象)' }
  if (trimmed.includes('\t')) return { format: 'TSV', ...parseTsv(trimmed) }
  return { format: 'CSV', ...parseCsv(trimmed) }
}

const parsed = computed(() => parseInput(rowsText.value))

/** 高级粘贴应用:整表替换网格行(未声明列在网格里以失效键条呈现) */
function applyPaste() {
  const { rows, format } = parsed.value
  if (!rows) return
  workingRows.value = rows.map((r) => ({ ...r }))
  rowsText.value = ''
  toast.success(`已应用 ${format} ${rows.length} 行(未声明列会在网格中标失效键)`)
}

/** M2b Q3:行账号列 ``@slot.<槽名>``(值 = 绑定名)→ 槽名清单(首见序) */
function accountSlotsOf(rows: DataSetRow[] | null | undefined): string[] {
  const out: string[] = []
  for (const r of rows ?? []) {
    for (const k of Object.keys(r ?? {})) {
      if (k.startsWith('@slot.') && k.length > 6 && !out.includes(k.slice(6))) out.push(k.slice(6))
    }
  }
  return out
}

/** CSV 序列化:列序 = 列宇宙序 + 失效键缀后(`__` 前缀键不出导出)。
 *  与高级粘贴导入互为往返 —— 不复活 var-palette 模板协议(D1 作废)。 */
function toCsv(rows: Array<Record<string, unknown>>): string {
  const cols = exportColumnOrder(columns.value, rows)
  const esc = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
}

function exportCsv() {
  if (!workingRows.value.length) return
  const base = (formName.value.trim() || editingId.value || 'dataset').replace(/[\\/:*?"<>|]/g, '_')
  downloadFile(`${base}.csv`, toCsv(workingRows.value), 'text/csv')
}

async function submit() {
  if (saving.value || loadingExisting.value || deadKeys.value.length) return
  const name = formName.value.trim() || `数据集 ${props.dataSets.length + 1}`
  saving.value = true
  try {
    // varUnlocks 非空才携带(PUT 整体替换,不带的语义 = 清空;空 = 本就无放开)
    const draft: Parameters<typeof updateDataSet>[1] = { name, rows: workingRows.value as DataSetRow[] }
    if (workingVarUnlocks.value.length) draft.varUnlocks = workingVarUnlocks.value
    if (mode.value === 'create') {
      const made = await createDataSet(props.scenarioId, draft)
      toast.success(`已创建数据集「${made.name || made.datasetId}」(${workingRows.value.length} 行)`)
    } else if (editingId.value) {
      await updateDataSet(editingId.value, draft)
      toast.success(`已保存数据集「${name}」(${workingRows.value.length} 行)`)
    }
    dialogOpen.value = false
    emit('saved')
  } catch (e) {
    showError(mode.value === 'create' ? '创建' : '保存', e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">数据</span>
      <span class="zone-count">{{ dataSets.length }}</span>
      <span class="zone-spacer"></span>
      <Button size="sm" variant="link" class="h-7 px-2" data-testid="open-create"
        @click="openCreate">+ 新建数据集</Button>
    </header>

    <div v-if="dead.length" class="dead-row" data-testid="dead-row">
      <span>{{ dead.map((d) => d.datasetId).join('、') }} 已删除</span>
      <Button size="sm" variant="link" class="h-7 px-2 text-signal-failed" data-testid="drop-dead" @click="dropDead">一键移除</Button>
    </div>

    <div class="ds-tiles">
      <div v-for="d in dataSets" :key="d.datasetId" class="ds-tile" :class="{ on: isSelected(d.datasetId) }">
        <label data-testid="ds-tile">
          <input type="checkbox" :checked="isSelected(d.datasetId)"
            @change="toggleDataset(d, ($event.target as HTMLInputElement).checked)" />
          <span class="ds-name">{{ d.name || d.datasetId }}</span>
          <span class="row-count">{{ rowsOf(d).length }} 行</span>
          <span v-if="accountSlotsOf(d.preview).length" class="acct-badge"
            :data-testid="`ds-acct-${d.datasetId}`"
            :title="`账号列:${accountSlotsOf(d.preview).join('、')}(每行可换账号)`">账号驱动</span>
        </label>
        <div v-if="isSelected(d.datasetId)" class="row-picks">
          <!-- rowsOf 已是 0 基索引数组,v-for 取数组值后直接用 r(原稿 i-1 会错位成 -1,0,1) -->
          <label v-for="r in rowsOf(d)" :key="r" class="row-pick">
            <input type="checkbox" :checked="rowChecked(d.datasetId, r)"
              @change="toggleRow(d.datasetId, r, ($event.target as HTMLInputElement).checked)" />
            行{{ r }}
          </label>
        </div>
        <div class="ds-tile-foot">
          <Button class="ds-act" size="sm" variant="link"
            :data-testid="`ds-edit-${d.datasetId}`" @click="openEdit(d)">编辑</Button>
          <Button class="ds-act ds-del" size="sm" variant="link"
            :data-testid="`ds-del-${d.datasetId}`" @click="removeDataset(d)">删除</Button>
        </div>
      </div>
      <div v-if="!dataSets.length" class="empty-state">
        <p>场景暂无数据集 — 不选即基线执行。</p>
        <Button size="sm" variant="outline" data-testid="open-create-empty"
          @click="openCreate">+ 新建数据集</Button>
      </div>
    </div>

    <!-- 内联维护:网格为主(变量即列),高级粘贴折叠兜底 -->
    <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
      <DialogContent class="max-w-[960px]">
        <DialogHeader>
          <DialogTitle>{{ mode === 'create' ? '新建数据集' : '编辑数据集' }}</DialogTitle>
        </DialogHeader>
        <div class="create-form" data-testid="create-form">
          <label class="create-label">名称</label>
          <Input v-model="formName" placeholder="数据集 N" data-testid="create-name" />

          <div v-if="loadingExisting" class="slib-loading">载入中…</div>
          <DataSetGridEditor
            v-else
            v-model:rows="workingRows"
            v-model:var-unlocks="workingVarUnlocks"
            :scenario-id="scenarioId"
            :config-vars="configVars"
            :var-locks="varLocks"
            :steps="steps"
          />

          <!-- 高级粘贴:原始 JSON / TSV / CSV 直接替换网格数据(幂等往返) -->
          <details class="adv-paste">
            <summary>高级粘贴 — JSON / TSV / CSV(整表替换)</summary>
            <textarea
              v-model="rowsText"
              rows="6"
              data-testid="create-rows"
              class="w-full rounded-field border border-input bg-transparent p-2 font-mono text-body"
              placeholder="粘贴 JSON 数组,或直接从 Excel 粘贴(Tab 分隔)/ CSV 文本"
            ></textarea>
            <p class="create-hint" data-testid="create-account-hint">
              账号列:列名 <code>@slot.&lt;槽名&gt;</code>,值填本次执行凭证池里的绑定名(个人凭证或项目凭证)——
              每行可换账号;留空沿用默认绑定。
            </p>
            <p v-if="parsed.rows" class="create-hint ok" data-testid="create-preview">
              {{ parsed.format }} 可解析:{{ parsed.rows.length }} 行
              <template v-if="accountSlotsOf(parsed.rows).length">
                · 账号列 {{ accountSlotsOf(parsed.rows).join('、') }}
              </template>
            </p>
            <p v-else-if="parsed.error" class="create-hint bad" data-testid="create-error">
              {{ parsed.error }}
            </p>
            <Button v-if="parsed.rows" variant="outline" size="sm"
              data-testid="apply-paste" @click="applyPaste">应用到网格(替换全部行)</Button>
          </details>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="!workingRows.length" data-testid="export-csv" @click="exportCsv">导出 CSV</Button>
          <Button variant="outline" @click="dialogOpen = false">取消</Button>
          <Button :disabled="saving || loadingExisting || deadKeys.length > 0
            || (mode === 'create' && !workingRows.length)"
          data-testid="create-submit"
            :title="deadKeys.length ? `存在未声明列(${deadKeys.join('、')})— 后端会 422 拒收,请移除或去编排器声明` : undefined"
            @click="submit">{{ mode === 'create' ? '创建' : saving ? '保存中…' : '保存' }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
.acct-badge { font-size: 0.7rem; padding: 0 6px; border-radius: 999px; background: rgb(37 99 235 / 8%); color: #1d4ed8; border: 1px solid rgb(37 99 235 / 25%); }
/* 分区卡片:对齐平台卡片体系(CaseDataSetsList .card / 编辑器 .meta) */
.wb-section {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
/* zone-head 体系(CaseDataSetsList 同款):左竖线标题 + 计数徽标 + 弹性空位 */
.zone-head { display: flex; align-items: center; gap: 10px; }
.zone-name {
  font-size: 14px; font-weight: 700; color: var(--color-text-primary);
  padding-left: 10px; border-left: 3px solid var(--accent);
}
.zone-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: var(--color-text-secondary); background: #f1f5f9; border-radius: 3px;
}
.zone-spacer { flex: 1; }

/* 失效行:amber 软提示条(DataSetEditor dead-keys-bar 同款语言) */
.dead-row {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 5px 10px; font-size: 11px; color: #b45309;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
}

/* tile 网格:平台卡片网格形制(CaseDataSetsList .grid auto-fill) */
.ds-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
.ds-tile {
  background: #fff; border: 1px solid var(--color-border-tertiary); border-radius: 8px;
  padding: 10px 12px; transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.ds-tile:hover { border-color: var(--accent); box-shadow: 0 1px 6px rgba(67, 56, 202, 0.12); }
/* 选中态:浅 accent 底 + 左侧竖条(与左栏选中项同一语言) */
.ds-tile.on {
  border-color: var(--accent-soft-border); background: #f0f5ff;
  box-shadow: inset 2px 0 0 var(--accent);
}
.ds-tile label {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
}
.ds-tile input[type="checkbox"] { accent-color: var(--accent); flex: none; }
.ds-name {
  flex: 1; min-width: 0; font-size: 13px; font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* 行数徽标:CaseDataSetsList .row-count 同款 chip */
.row-count {
  flex: none; padding: 1px 6px; font-family: var(--font-mono); font-size: 10px;
  font-weight: 600; color: var(--color-text-secondary);
  background: #f1f5f9; border-radius: 3px; white-space: nowrap;
}

/* 行级勾选展开态:换行排版 + 虚线分隔(选中 tile 的附属区) */
.row-picks {
  display: flex; flex-wrap: wrap; gap: 4px 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed var(--color-border-tertiary);
}
.row-pick {
  display: inline-flex; align-items: center; gap: 4px; cursor: pointer;
  padding: 2px 8px; border: 1px solid transparent; border-radius: 4px;
  font-size: 12px; color: var(--color-text-secondary);
}
.row-pick:hover { border-color: var(--color-border-tertiary); background: #fff; }
.row-pick input[type="checkbox"] { accent-color: var(--accent); margin: 0; }

/* tile 操作位:编辑/删除靠右,不触发 label 勾选 */
.ds-tile-foot { margin-top: 6px; display: flex; justify-content: flex-end; gap: 2px; }
.ds-act { height: 22px; padding: 0 6px; font-size: 11px; }

/* 空态(三处统一形状:dashed 框 + muted 文案 + 引导按钮) */
.empty-state {
  grid-column: 1 / -1;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 18px 16px; text-align: center;
  border: 1px dashed var(--color-border-tertiary); border-radius: 8px;
}
.empty-state p { margin: 0; font-size: 12px; color: var(--color-text-tertiary); }

/* 内联维护表单 */
.create-form { display: flex; flex-direction: column; gap: 6px; }
.create-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-top: 4px; }
.create-hint { margin: 0; font-size: 12px; }
.create-hint.ok { color: var(--color-success, #15803d); }
.create-hint.bad { color: var(--color-danger, #dc2626); }
/* 高级粘贴折叠区:标题行弱化,展开后与网格同一表单节奏 */
.adv-paste { margin-top: 6px; border: 1px dashed var(--color-border-tertiary); border-radius: 8px; padding: 8px 10px; }
.adv-paste summary { font-size: 11.5px; font-weight: 600; color: var(--color-text-secondary); cursor: pointer; }
.adv-paste[open] summary { margin-bottom: 8px; }
.adv-paste .create-hint { margin-top: 6px; }
.adv-paste button { margin-top: 8px; }
</style>
