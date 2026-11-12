<script setup lang="ts">
/**
 * DataSetGridEditor.vue — 数据集「变量即列」网格编辑器。
 *
 * 沿袭:旧栈 DataSetEditor 的转置网格(变量即列 / 置顶基线行 / 三态 cell /
 * 字段说明行)在 D1(2026-09-17)随独立路由退役;2026-11-12 以新栈形制
 * 回迁方案工作台 —— 列宇宙 = config.vars 标量变量(+ @slot.* 账号列),
 * 与后端 `_scalar_vars` 调色板门同规则;基线行只读(变量默认值归编排器③,
 * 用户裁定不回迁旧版的行内基线编辑)。
 *
 * 稀疏行三态不变式见 utils/dataset-grid.ts 头注:`undefined` = 继承基线,
 * `""` = 显式空覆盖;行值统一存字符串(运行期 coerce_row_value 按基线
 * 类型还原)。`__` 前缀键(__rowKey,服务端敏感列并回键)原样保留不编辑。
 *
 * 界面词汇 ↔ 字段:列 = 变量 · 基线 = config.vars 默认 · 空格 = 继承。
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  deriveVarColumns, cellDisplay, gridStats, deadKeysOf, stripDeadKeys,
  parseTsvPaste, applyPastePlan, injectionSlotNames, baselineText,
  type GridColumn,
} from '@/utils/dataset-grid'
import { fieldPathsOf, type SegmentStepShape } from '@/utils/dataset-segments'
import { iterFlat } from '@/utils/declarations'
import { getEndpointFull } from '@/composables/useEndpointFull'
import { stepEndpointId } from '@/types/plate'
import { composerUrl } from '@/utils/links'
import { toast } from '@/utils/toast'
import { promptAction } from '@/utils/confirmAction'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  scenarioId: string
  /** 场景 config.vars(变量即列的宇宙来源) */
  configVars: Record<string, unknown> | null
  /** 场景级 var_locks(锁列默认隐藏;数据集级 varUnlocks 放开) */
  varLocks: string[]
  /** definition.steps(引用位扫描 + 契约描述 + 账号列候选) */
  steps: unknown[]
}>()

/** 工作行(v-model;cell 原位改写走响应式,行级操作换新数组) */
const rows = defineModel<Array<Record<string, unknown>>>('rows', { required: true })
/** 数据集级变量锁本地放开清单(v-model;保存随 PUT 整体替换) */
const varUnlocks = defineModel<string[]>('varUnlocks', { default: () => [] })

const router = useRouter()

// ── 列宇宙 ─────────────────────────────────────────────────────
/** 手动激活的账号列(行内还没有键、但用户已加列;新行会带上这些键) */
const extraSlots = ref<string[]>([])

const derivedCols = computed(() =>
  deriveVarColumns(props.configVars, rows.value, props.varLocks, varUnlocks.value))
const columns = computed<GridColumn[]>(() => {
  const out = [...derivedCols.value]
  for (const name of extraSlots.value) {
    const key = `@slot.${name}`
    if (!out.some((c) => c.key === key)) {
      out.push({ kind: 'slot', name, key, baseline: undefined, locked: false })
    }
  }
  return out
})
const visibleCols = computed(() => columns.value.filter((c) => !c.locked))
const lockedCols = computed(() => columns.value.filter((c) => c.locked))
const stats = computed(() => gridStats(columns.value, rows.value))
const dead = computed(() => deadKeysOf(columns.value, rows.value))

/** 账号列候选:注入槽静态近似 − 已有账号列(手打槽名交后端 422 兜底) */
const slotCandidates = computed(() =>
  injectionSlotNames(props.steps, props.configVars)
    .filter((s) => !columns.value.some((c) => c.kind === 'slot' && c.name === s)))

// ── 引用面 / 契约描述行 ────────────────────────────────────────
/** var → 首个 body 引用位(整值 ${var.x} 模板的叶子) */
const refSites = computed(() => {
  const out = new Map<string, { stepIdx: number; path: string }>()
  ;(props.steps ?? []).forEach((st, si) => {
    for (const leaf of fieldPathsOf(st as SegmentStepShape)) {
      if (leaf.source !== 'body' || !leaf.varName || out.has(leaf.varName)) continue
      out.set(leaf.varName, { stepIdx: si, path: leaf.path })
    }
  })
  return out
})

/** 叶子实例路径 → 声明模板路径(去 [i] 下标) */
function normPath(p: string): string {
  return p.replace(/\[\d+\]/g, '')
}

/** 列描述:首个 body 引用位的契约描述(EndpointFull 纯读缓存 —— 工作台
 *  surface.ensure() 已预取;未命中缓存/无描述退化为引用位文本)。 */
function descOf(col: GridColumn): string {
  if (col.kind === 'slot') return '值 = 执行者凭证池里的绑定名(每行可换账号)'
  const site = refSites.value.get(col.name)
  if (!site) return ''
  const eid = stepEndpointId(props.steps[site.stepIdx])
  const full = eid ? getEndpointFull(eid) : undefined
  const decls = full?.request?.declarations
  if (decls) {
    const target = normPath(site.path)
    for (const e of iterFlat(decls)) {
      if (e.path === target) return e.description ?? ''
    }
  }
  return site ? `步骤${site.stepIdx + 1} · ${site.path}` : ''
}

/** 字段行引用徽标(有引用位才显) */
function refBadgeOf(col: GridColumn): string | null {
  if (col.kind !== 'var') return null
  const site = refSites.value.get(col.name)
  return site ? `步骤${site.stepIdx + 1}` : null
}

// ── 基线行 ─────────────────────────────────────────────────────
const baselineCell = (col: GridColumn) => baselineText(col.baseline)
const isStructuredBaseline = (col: GridColumn) =>
  col.kind === 'var' && col.baseline !== undefined && col.baseline !== null
    && typeof col.baseline === 'object'

// ── cell 编辑 ──────────────────────────────────────────────────
/** 数字基线列的非数字软提示(不硬拦:后端 coerce 失败保留原串,运行期语义不变) */
function numWarn(col: GridColumn, value: string): boolean {
  return col.kind === 'var' && typeof col.baseline === 'number'
    && value !== '' && !/^-?\d+(\.\d+)?$/.test(value)
}

/** 碰过即写键:清空 = 显式空覆盖(override-empty);未碰 = 键不存在(继承) */
function onCellInputValue(rowIdx: number, col: GridColumn, value: string) {
  rows.value[rowIdx][col.key] = value
}

function onBoolChange(rowIdx: number, col: GridColumn, ev: Event) {
  const v = (ev.target as HTMLSelectElement).value
  const row = rows.value[rowIdx]
  if (v === '') delete row[col.key]  // 选「继承」= 摘键,回稀疏
  else row[col.key] = v
}

/** cell 粘贴含 \t/\n → 从当前格向右下铺(自动补行),否则走默认单格输入 */
function onCellPaste(ev: ClipboardEvent, rowIdx: number, colIdx: number) {
  const text = ev.clipboardData?.getData('text') ?? ''
  if (!text.includes('\t') && !text.includes('\n')) return
  ev.preventDefault()
  const colKeys = visibleCols.value.slice(colIdx).map((c) => c.key)
  const plan = parseTsvPaste(text, colKeys, rowIdx, rows.value.length)
  if (!plan.cells.length) return
  rows.value = applyPastePlan(rows.value, plan)
  toast.success(`已粘贴 ${plan.cells.length} 行 × ${plan.colKeys.length} 列`)
}

function addRow() {
  // 新行带上已激活的账号列键(空串 = 不覆写账号,中性)——列不因加行而消失
  const slotKeys = columns.value.filter((c) => c.kind === 'slot').map((c) => c.key)
  rows.value = [...rows.value, Object.fromEntries(slotKeys.map((k) => [k, '']))]
}
function removeRow(idx: number) {
  rows.value = rows.value.filter((_, i) => i !== idx)
}
function dropDeadKeys() {
  rows.value = stripDeadKeys(rows.value, dead.value)
  toast.success('已移除失效键')
}

// ── 锁列放开/收回(数据集级 varUnlocks)────────────────────────
function unlock(name: string) {
  if (!varUnlocks.value.includes(name)) varUnlocks.value = [...varUnlocks.value, name]
}
function relock(name: string) {
  varUnlocks.value = varUnlocks.value.filter((n) => n !== name)
}

// ── 账号列激活 ─────────────────────────────────────────────────
async function addCustomSlot() {
  const raw = await promptAction(
    '槽名(执行注入引用的槽,如 qa;仅限字母/数字/_/-)', '加账号列',
    { placeholder: '槽名' },
  )
  const name = raw?.trim()
  if (!name) return
  if (!/^[A-Za-z0-9_-]+$/.test(name)) {
    toast.error('槽名仅限字母/数字/_/-')
    return
  }
  activateSlot(name)
}
function activateSlot(name: string) {
  const key = `@slot.${name}`
  if (!extraSlots.value.includes(name)) extraSlots.value = [...extraSlots.value, name]
  // 物化进现有行:空串 = 运行期不覆写账号(row_binding_refs 空值跳过),中性
  if (rows.value.some((r) => !(key in r))) {
    rows.value = rows.value.map((r) => (key in r ? r : { ...r, [key]: '' }))
  }
}
function onSlotCandidateChange(ev: Event) {
  const name = (ev.target as HTMLSelectElement).value
  if (name) activateSlot(name)
}
</script>

<template>
  <div class="dsg" data-testid="ds-grid">
    <!-- 顶栏:统计 + 跳编排器 -->
    <div class="dsg-top">
      <span class="dsg-stats" data-testid="ds-stats">
        变量 {{ stats.varCount }} · 数据 {{ stats.rowCount }} 行 · 覆写 {{ stats.overrideCount }} 格
      </span>
      <span class="flex-1" />
      <Button variant="link" size="sm" class="h-6 px-1" data-testid="ds-composer-link"
        @click="router.push(composerUrl(scenarioId, 3))">
        变量与基线在编排器③配置步维护 ↗
      </Button>
    </div>

    <!-- 锁列条:被场景 var_locks 锁定的变量默认不出列 -->
    <div v-if="lockedCols.length" class="dsg-bar warn" data-testid="ds-lock-bar">
      <span>
        {{ lockedCols.length }} 个变量已被场景锁定(列已隐藏):{{ lockedCols.map((c) => c.name).join('、') }}
      </span>
      <Button v-for="c in lockedCols" :key="c.name" variant="link" size="sm" class="h-6 px-1"
        :data-testid="`ds-unlock-${c.name}`" @click="unlock(c.name)">放开 {{ c.name }}</Button>
    </div>

    <!-- 失效键条:行键 ∉ 列宇宙(变量已删等)— 软警示,不阻断 -->
    <div v-if="dead.length" class="dsg-bar warn" data-testid="ds-dead-bar">
      <span>行键 {{ dead.join('、') }} 不在变量列里(变量已删?)— 运行无效果,可继续编辑</span>
      <Button variant="link" size="sm" class="h-6 px-1" data-testid="ds-drop-dead"
        @click="dropDeadKeys">一键移除</Button>
    </div>

    <!-- 引导条:列宇宙全空 -->
    <div v-if="!columns.length" class="dsg-bar" data-testid="ds-empty-guide">
      <span>场景还没有标量变量 — 去编排器③配置步添加共享变量,或在字段菜单「设为变量」;有注入槽时也可加账号列。</span>
    </div>

    <div v-if="visibleCols.length || rows.length" class="dsg-scroll">
      <table class="slib-table dsg-table">
        <thead>
          <!-- 描述行:契约描述(引用位兜底) -->
          <tr class="dsg-desc-row">
            <th class="dsg-gutter" rowspan="2">变量</th>
            <td v-for="col in visibleCols" :key="`d:${col.key}`" class="dsg-desc"
              :data-testid="`ds-desc-${col.key}`" :title="descOf(col)">{{ descOf(col) || '—' }}</td>
          </tr>
          <!-- 字段行:名 + 引用徽标 + 账号徽标 + 放开后的收回钮 -->
          <tr>
            <th class="dsg-gutter-2">
              <select v-if="slotCandidates.length" class="dsg-slot-add" data-testid="ds-slot-add"
                title="加账号列(@slot.<槽名>,每行可换账号)" @change="onSlotCandidateChange">
                <option value="">+ 账号列…</option>
                <option v-for="s in slotCandidates" :key="s" :value="s">{{ s }}</option>
              </select>
              <Button v-else variant="link" size="sm" class="h-6 px-1" data-testid="ds-slot-add-custom"
                title="加账号列(@slot.<槽名>,每行可换账号)" @click="addCustomSlot">+ 账号列…</Button>
            </th>
            <th v-for="col in visibleCols" :key="`h:${col.key}`" class="dsg-colhead"
              :data-testid="`ds-col-${col.key}`">
              <span class="dsg-name" :class="{ slot: col.kind === 'slot' }">{{ col.name }}</span>
              <span v-if="refBadgeOf(col)" class="dsg-ref" :title="`引用于 ${refSites.get(col.name)!.path}`">
                {{ refBadgeOf(col) }}
              </span>
              <span v-if="col.kind === 'slot'" class="dsg-kind">账号</span>
              <button v-if="col.kind === 'var' && props.varLocks.includes(col.name)"
                type="button" class="dsg-lock" :data-testid="`ds-relock-${col.name}`"
                title="收回:本数据集恢复隐藏该锁列" @click="relock(col.name)">收回</button>
            </th>
          </tr>
        </thead>
        <tbody>
          <!-- 置顶基线行(只读):config.vars 默认值,继承的占位即来自这里 -->
          <tr class="dsg-baseline" data-testid="ds-baseline-row">
            <th class="dsg-gutter-2">基线</th>
            <td v-for="col in visibleCols" :key="`b:${col.key}`" class="dsg-baseline-cell"
              :data-testid="`ds-baseline-${col.key}`">
              <span v-if="isStructuredBaseline(col)" class="dsg-chip"
                :title="JSON.stringify(col.baseline)">JSON</span>
              <template v-else>{{ baselineCell(col) === '' ? '(空)' : baselineCell(col) }}</template>
            </td>
          </tr>
          <!-- 数据行:三态 cell -->
          <tr v-for="(row, i) in rows" :key="i">
            <th class="dsg-gutter-2 dsg-rowhead">
              <span>行{{ i }}</span>
              <button type="button" class="dsg-del" :data-testid="`ds-del-row-${i}`"
                title="删行" @click="removeRow(i)">×</button>
            </th>
            <td v-for="(col, j) in visibleCols" :key="`c:${col.key}`" class="dsg-cell"
              :class="cellDisplay(row, col).state">
              <select v-if="col.kind === 'var' && typeof col.baseline === 'boolean'"
                :value="String(row[col.key] ?? '')"
                :data-testid="`ds-cell-${i}-${col.key}`"
                :title="cellDisplay(row, col).state === 'inherit' ? `继承基线:${cellDisplay(row, col).placeholder}` : ''"
                @change="onBoolChange(i, col, $event)"
                @paste="onCellPaste($event, i, j)">
                <option value="">继承{{ cellDisplay(row, col).placeholder ? `(${cellDisplay(row, col).placeholder})` : '' }}</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
              <Input v-else :model-value="cellDisplay(row, col).value"
                :placeholder="cellDisplay(row, col).placeholder"
                :style="numWarn(col, cellDisplay(row, col).value) ? { borderColor: '#f59e0b' } : undefined"
                :title="numWarn(col, cellDisplay(row, col).value) ? '基线是数字,非数字值运行期将按字符串合入' : undefined"
                class="h-7 dsg-input"
                :data-testid="`ds-cell-${i}-${col.key}`"
                @update:model-value="(v) => onCellInputValue(i, col, String(v ?? ''))"
                @paste="onCellPaste($event, i, j)" />
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="visibleCols.length + 1" class="dsg-norow">还没有数据行 — 下方「+ 加一行」开始填。</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="dsg-foot">
      <Button variant="outline" size="sm" data-testid="ds-add-row" @click="addRow">+ 加一行</Button>
      <span class="dsg-hint">空格 = 继承基线;输入后清空 = 显式空值;行值运行期按基线类型还原。</span>
    </div>
  </div>
</template>

<style scoped>
.dsg { display: flex; flex-direction: column; gap: 8px; }
.dsg-top, .dsg-foot { display: flex; align-items: center; gap: 8px; }
.dsg-stats { font-size: 11px; color: var(--color-text-secondary, #64748b); }
.flex-1 { flex: 1; }

.dsg-bar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 5px 10px; font-size: 11px; border-radius: 6px;
  color: var(--color-text-secondary, #475569); background: #f8fafc; border: 1px solid var(--color-border-tertiary, #e2e8f0);
}
.dsg-bar.warn { color: #b45309; background: #fffbeb; border-color: #fde68a; }

.dsg-scroll { max-height: 420px; overflow: auto; border: 1px solid var(--color-border-tertiary, #e2e8f0); border-radius: 8px; }
.dsg-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; }
.dsg-table th, .dsg-table td { border-bottom: 1px solid var(--color-border-tertiary, #e2e8f0); padding: 4px 8px; text-align: left; }
.dsg-table thead th, .dsg-table thead td { background: #fff; position: sticky; z-index: 2; }
.dsg-desc-row th, .dsg-desc-row td { top: 0; }
/* 字段行吸在描述行之下(描述行 ~28px) */
.dsg-table thead tr:nth-child(2) th { top: 28px; }
.dsg-gutter, .dsg-gutter-2 {
  position: sticky; left: 0; background: #fff;
  min-width: 64px; width: 64px; font-weight: 600; color: var(--color-text-secondary, #475569);
}
.dsg-desc-row .dsg-gutter { z-index: 4; }
.dsg-gutter-2 { z-index: 3; }
.dsg-desc { color: var(--color-text-tertiary, #94a3b8); font-weight: 400; font-size: 10.5px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dsg-colhead { white-space: nowrap; }
.dsg-name { font-family: var(--font-mono, ui-monospace, monospace); font-weight: 600; color: var(--color-text-primary, #0f172a); }
.dsg-name.slot { color: #1d4ed8; }
.dsg-ref { margin-left: 4px; padding: 0 4px; font-size: 9px; border-radius: 3px; background: #eef2ff; color: #4338ca; }
.dsg-kind { margin-left: 4px; padding: 0 4px; font-size: 9px; border-radius: 3px; background: rgb(37 99 235 / 8%); color: #1d4ed8; }
.dsg-lock { margin-left: 4px; border: 0; background: none; font-size: 10px; color: var(--accent, #4f46e5); cursor: pointer; padding: 0; }
.dsg-lock:hover { text-decoration: underline; }

.dsg-baseline th, .dsg-baseline td { background: #f8fafc; color: var(--color-text-secondary, #475569); }
.dsg-baseline-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono, ui-monospace, monospace); font-size: 11px; }
.dsg-chip { padding: 0 5px; font-size: 9px; border-radius: 3px; background: #fce7f3; color: #be185d; font-weight: 700; }

.dsg-cell { max-width: 220px; }
.dsg-cell.override-empty { box-shadow: inset 3px 0 0 #ef4444; }
.dsg-cell.override-empty :deep(input) { color: #b91c1c; }
select.dsg-slot-add, .dsg-cell select { height: 26px; font-size: 11.5px; border: 1px solid var(--color-border-tertiary, #e2e8f0); border-radius: 6px; background: #fff; color: inherit; }

.dsg-rowhead { display: flex; align-items: center; gap: 4px; }
.dsg-del { border: 0; background: none; color: var(--color-text-tertiary, #94a3b8); cursor: pointer; font-size: 13px; line-height: 1; padding: 0 2px; }
.dsg-del:hover { color: #dc2626; }
.dsg-norow { color: var(--color-text-tertiary, #94a3b8); text-align: center; font-size: 11px; padding: 14px 8px !important; }
.dsg-hint { font-size: 10.5px; color: var(--color-text-tertiary, #94a3b8); }
</style>
