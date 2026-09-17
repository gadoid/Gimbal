<script setup lang="ts">
/**
 * 方案工作台 · 数据区:数据集多选(行级勾选)、失效标注与移除、内联维护。
 *
 * D1 能力承接(数据集独立路由退役后,"维护方案数据集"全部在此可做):
 * 新建 / 编辑(改名 + 行数据)/ 删除;行数据粘贴支持 JSON / TSV / CSV,
 * CSV 导出为简单序列化(union 列头),与粘贴导入互为往返 — 不复活已
 * 作废的 var-palette 模板协议(dataset v2 T6-T8,D1 作废)。
 * 编辑保存保留既有 varUnlocks(PUT 整体替换语义,不带会被清空)。
 */
import { computed, ref } from 'vue'
import type { DataSetRow, DataSetSummary } from '@/types/scenario-composer'
import { createDataSet, updateDataSet, getDataSet } from '@/api/scenario-composer'
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
const rowsText = ref('[]')
const saving = ref(false)
/** 编辑目标:varUnlocks 随保存原样带回(PUT 整体替换,不带会清空)。 */
const editing = ref<{ datasetId: string; varUnlocks?: string[] } | null>(null)
const loadingExisting = ref(false)

function openCreate() {
  mode.value = 'create'
  editing.value = null
  formName.value = `数据集 ${props.dataSets.length + 1}`
  rowsText.value = '[]'
  dialogOpen.value = true
}

async function openEdit(d: DataSetSummary) {
  mode.value = 'edit'
  editing.value = null
  formName.value = d.name || d.datasetId
  rowsText.value = '[]'
  dialogOpen.value = true
  loadingExisting.value = true
  try {
    const full = await getDataSet(d.datasetId)
    formName.value = full.name
    rowsText.value = JSON.stringify(full.rows, null, 2)
    editing.value = { datasetId: full.datasetId, varUnlocks: full.varUnlocks }
  } catch (e) {
    showError('加载', e)
    dialogOpen.value = false
  } finally {
    loadingExisting.value = false
  }
}

// ── 行数据解析:JSON → TSV → CSV(自动识别)──────────────────────
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
  if (!trimmed) return { error: '内容为空' }
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

/** 简单 CSV 序列化(union 列头,首见序;与粘贴导入互为往返)。 */
function toCsv(rows: DataSetRow[]): string {
  const cols: string[] = []
  for (const r of rows) {
    for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k)
  }
  const esc = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
}

function exportCsv() {
  const { rows } = parsed.value
  if (!rows) return
  const base = (formName.value.trim() || editing.value?.datasetId || 'dataset').replace(/[\\/:*?"<>|]/g, '_')
  downloadFile(`${base}.csv`, toCsv(rows), 'text/csv')
}

async function submit() {
  const { rows } = parsed.value
  if (!rows || saving.value || loadingExisting.value) return
  const name = formName.value.trim() || `数据集 ${props.dataSets.length + 1}`
  saving.value = true
  try {
    if (mode.value === 'create') {
      const made = await createDataSet(props.scenarioId, { name, rows })
      toast.success(`已创建数据集「${made.name || made.datasetId}」(${rows.length} 行)`)
    } else if (editing.value) {
      // varUnlocks 原样带回:PUT 整体替换,不带会把既有放开清单清掉
      const draft: Parameters<typeof updateDataSet>[1] = { name, rows }
      if (editing.value.varUnlocks?.length) draft.varUnlocks = editing.value.varUnlocks
      await updateDataSet(editing.value.datasetId, draft)
      toast.success(`已保存数据集「${name}」(${rows.length} 行)`)
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

    <!-- 内联维护:名称 + 行数据(JSON/TSV/CSV 粘贴),校验通过才落库 -->
    <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
      <DialogContent class="max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{{ mode === 'create' ? '新建数据集' : '编辑数据集' }}</DialogTitle>
        </DialogHeader>
        <div class="create-form" data-testid="create-form">
          <label class="create-label">名称</label>
          <Input v-model="formName" placeholder="数据集 N" data-testid="create-name" />
          <label class="create-label">行数据(支持粘贴 JSON 数组 / TSV / CSV,自动识别)</label>
          <textarea
            v-model="rowsText"
            rows="8"
            data-testid="create-rows"
            class="w-full rounded-field border border-input bg-transparent p-2 font-mono text-body"
            :placeholder="loadingExisting ? '载入中…' : '粘贴 JSON 数组,或直接从 Excel 粘贴(Tab 分隔)/ CSV 文本'"
          ></textarea>
          <p v-if="parsed.rows" class="create-hint ok" data-testid="create-preview">
            {{ parsed.format }} 可解析:{{ parsed.rows.length }} 行
          </p>
          <p v-else-if="parsed.error" class="create-hint bad" data-testid="create-error">
            {{ parsed.error }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="!parsed.rows" data-testid="export-csv" @click="exportCsv">导出 CSV</Button>
          <Button variant="outline" @click="dialogOpen = false">取消</Button>
          <Button :disabled="!parsed.rows || saving || loadingExisting" data-testid="create-submit"
            @click="submit">{{ mode === 'create' ? '创建' : saving ? '保存中…' : '保存' }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
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
</style>
