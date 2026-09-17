<script setup lang="ts">
/**
 * 方案工作台 · 数据区:数据集多选(行级勾选)、失效标注与移除、内联新建。
 *
 * 数据集独立路由已退役(D1,重构方案 Phase 2 批次 0):创建能力由本区
 * 内联承接(名称 + 行数据粘贴),不再跳独立编辑器页。
 */
import { computed, ref } from 'vue'
import type { DataSetRow, DataSetSummary } from '@/types/scenario-composer'
import { createDataSet } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'

type Sel = { datasetId: string; rowIndexes?: number[] }

const props = defineProps<{
  modelValue: Sel[]
  dataSets: DataSetSummary[]
  scenarioId: string
}>()
const emit = defineEmits<{
  'update:modelValue': [v: Sel[]]
  created: []
  /** 用户已在区内确认;落库(refetch)由工作台处理 */
  delete: [datasetId: string]
}>()

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

// ── 内联新建(编辑器页退役后的创建承接)──────────────────────────
const createOpen = ref(false)
const createName = ref('')
const createRowsText = ref('[]')
const creating = ref(false)

function openCreate() {
  createName.value = `数据集 ${props.dataSets.length + 1}`
  createRowsText.value = '[]'
  createOpen.value = true
}

/** 解析粘贴的行数据:数组 + 每行对象 + 值限标量(DataSetRow 契约)。 */
function parseRows(text: string): { rows?: DataSetRow[]; error?: string } {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return { error: '不是合法 JSON' }
  }
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

const parsedPreview = computed(() => parseRows(createRowsText.value))

async function submitCreate() {
  // 复用实时预览的解析结果(同一数据源,submit 时再断言一次兜底)
  const { rows, error } = parsedPreview.value
  if (error || !rows) return
  creating.value = true
  try {
    const created = await createDataSet(props.scenarioId, {
      name: createName.value.trim() || `数据集 ${props.dataSets.length + 1}`,
      rows,
    })
    toast.success(`已创建数据集「${created.name || created.datasetId}」(${rows.length} 行)`)
    createOpen.value = false
    emit('created')
  } catch (e) {
    showError('创建', e)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">数据</span>
      <span class="zone-count">{{ dataSets.length }}</span>
      <span class="zone-spacer"></span>
      <el-button size="small" text type="primary" data-testid="open-create"
        @click="openCreate">+ 新建数据集</el-button>
    </header>

    <div v-if="dead.length" class="dead-row" data-testid="dead-row">
      <span>{{ dead.map((d) => d.datasetId).join('、') }} 已删除</span>
      <el-button size="small" type="danger" text data-testid="drop-dead" @click="dropDead">一键移除</el-button>
    </div>

    <div class="ds-tiles">
      <div v-for="d in dataSets" :key="d.datasetId" class="ds-tile" :class="{ on: isSelected(d.datasetId) }">
        <label data-testid="ds-tile">
          <input type="checkbox" :checked="isSelected(d.datasetId)"
            @change="toggleDataset(d, ($event.target as HTMLInputElement).checked)" />
          <span class="ds-name">{{ d.name || d.datasetId }}</span>
          <span class="row-count">{{ rowsOf(d).length }} 行</span>
        </label>
        <div class="ds-tile-foot">
          <div v-if="isSelected(d.datasetId)" class="row-picks">
            <!-- rowsOf 已是 0 基索引数组,v-for 取数组值后直接用 r(原稿 i-1 会错位成 -1,0,1) -->
            <label v-for="r in rowsOf(d)" :key="r" class="row-pick">
              <input type="checkbox" :checked="rowChecked(d.datasetId, r)"
                @change="toggleRow(d.datasetId, r, ($event.target as HTMLInputElement).checked)" />
              行{{ r }}
            </label>
          </div>
          <el-button class="ds-del" size="small" text type="danger"
            :data-testid="`ds-del-${d.datasetId}`" @click="removeDataset(d)">删除</el-button>
        </div>
      </div>
      <div v-if="!dataSets.length" class="empty-state">
        <p>场景暂无数据集 — 不选即基线执行。</p>
        <el-button size="small" type="primary" plain data-testid="open-create-empty"
          @click="openCreate">+ 新建数据集</el-button>
      </div>
    </div>

    <!-- 内联新建:名称 + 行数据(JSON 粘贴),校验通过才落库 -->
    <el-dialog v-model="createOpen" title="新建数据集" width="560px">
      <div class="create-form" data-testid="create-form">
        <label class="create-label">名称</label>
        <el-input v-model="createName" placeholder="数据集 N" data-testid="create-name" />
        <label class="create-label">行数据(JSON 数组,每行一个对象)</label>
        <el-input
          v-model="createRowsText"
          type="textarea"
          :rows="8"
          data-testid="create-rows"
          placeholder='[{"amount": 100, "channel": "alipay"}, {"amount": 200, "channel": "wechat"}]'
        />
        <p v-if="parsedPreview.rows" class="create-hint ok" data-testid="create-preview">
          可解析:{{ parsedPreview.rows.length }} 行
        </p>
        <p v-else-if="parsedPreview.error" class="create-hint bad" data-testid="create-error">
          {{ parsedPreview.error }}
        </p>
      </div>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :disabled="!parsedPreview.rows || creating" data-testid="create-submit"
          @click="submitCreate">{{ creating ? '创建中…' : '创建' }}</el-button>
      </template>
    </el-dialog>
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
.ds-tile-foot { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.ds-del { align-self: flex-end; height: 22px; padding: 0 6px; font-size: 11px; }
.row-picks {
  display: flex; flex-wrap: wrap; gap: 4px 6px; padding-top: 8px;
  border-top: 1px dashed var(--color-border-tertiary);
}
.row-pick {
  display: inline-flex; align-items: center; gap: 4px; cursor: pointer;
  padding: 2px 8px; border: 1px solid transparent; border-radius: 4px;
  font-size: 12px; color: var(--color-text-secondary);
}
.row-pick:hover { border-color: var(--color-border-tertiary); background: #fff; }
.row-pick input[type="checkbox"] { accent-color: var(--accent); margin: 0; }

/* 空态(三处统一形状:dashed 框 + muted 文案 + 引导按钮) */
.empty-state {
  grid-column: 1 / -1;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 18px 16px; text-align: center;
  border: 1px dashed var(--color-border-tertiary); border-radius: 8px;
}
.empty-state p { margin: 0; font-size: 12px; color: var(--color-text-tertiary); }

/* 内联新建表单 */
.create-form { display: flex; flex-direction: column; gap: 6px; }
.create-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-top: 4px; }
.create-hint { margin: 0; font-size: 12px; }
.create-hint.ok { color: var(--color-success, #15803d); }
.create-hint.bad { color: var(--color-danger, #dc2626); }
</style>
