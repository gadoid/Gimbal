<!-- DataSetEditor.vue — 转置表 + 折叠基线(spec §4.5 重构)

     信息架构:
       - 顶部折叠基线(默认收起),按 step · source 树形分组,搜索过滤
       - 下方全宽数据表格(行 = 数据,列 = 变量;直填列不进入表格)
       - 每列 header 显示 变量名 + 步骤号 · source 缩写
       - 三态单元格:inherit(灰显基线 placeholder) / override-empty(红条) / override-value
       - TSV 粘贴 / CSV 导出 / CSV 导入

     数据契约(与后端对齐):
       - row 是稀疏 dict;undefined = 继承基线, "" = 显式空覆盖
       - 保存走 createDataSet / updateDataSet(rows)
       - 基线修改走 updateScenario(draft.definition)
-->
<template>
  <section class="ds-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title">
          <el-icon><DataAnalysis /></el-icon>数据集编辑
        </h2>
        <p>
          场景 <strong class="scenario-name">{{ scenarioName }}</strong>
          <code class="sid">{{ scenarioId }}</code>
          · {{ datasetId === 'new' ? '新建数据集' : datasetId }}
        </p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(scenarioDataSetsUrl(scenarioId))">返回列表</el-button>
        <el-button
          v-if="promotedOrder.length"
          plain
          type="warning"
          :title="`撤销最近一次提升(共 ${promotedOrder.length} 次)`"
          @click="demoteLast"
        >
          ↶ 撤销提升{{ promotedOrder.length > 1 ? ` (${promotedOrder.length})` : '' }}
        </el-button>
        <el-button :loading="savingBaseline" plain :disabled="!draft" @click="onSaveBaseline">
          保存基线{{ baselineDirty ? ' *' : '' }}
        </el-button>
        <el-button v-if="datasetId !== 'new'" type="danger" plain :icon="Delete" @click="onDelete">删除</el-button>
        <el-button type="primary" :loading="savingRows" plain :disabled="loadFailed || savingRows" @click="onSaveRows">保存数据集</el-button>
      </div>
    </header>

    <el-form label-position="top" class="meta">
      <div class="grid-3">
        <el-form-item label="数据集名称">
          <el-input v-model="form.name" placeholder="边界 amount 集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="amount = 0, 1, 999, -1(验证边界值)" />
        </el-form-item>
        <el-form-item label="摘要">
          <span class="mono">
            变量 {{ stats.varCount }} · 直填 {{ stats.directCount }} ·
            数据 {{ stats.rowCount }} · 覆盖 {{ stats.overrideCount }} 格
          </span>
        </el-form-item>
      </div>
    </el-form>

    <!-- 折叠基线区 -->
    <el-collapse v-model="baselineOpen" class="baseline-collapse">
      <el-collapse-item name="baseline">
        <template #title>
          <span class="baseline-title">
            基线
            <span class="muted">({{ stats.varCount }} 变量 · {{ stats.directCount }} 直填)</span>
          </span>
        </template>
        <div class="baseline-toolbar">
          <el-input
            v-model="baselineQuery"
            placeholder="搜索字段名 / 变量名…"
            clearable
            size="small"
            class="baseline-search"
          />
        </div>
        <el-collapse v-model="openGroups" class="baseline-groups">
          <el-collapse-item
            v-for="g in filteredGroups"
            :key="`${g.stepIndex}:${g.source}`"
            :name="`${g.stepIndex}:${g.source}`"
          >
            <template #title>
              <span class="group-title">
                步骤{{ g.stepIndex + 1 }} · {{ g.source }}
                <span class="muted">({{ g.fields.length }})</span>
              </span>
            </template>
            <div class="baseline-rows">
              <div v-for="col in g.fields" :key="`${col.stepIndex}:${col.source}:${col.field}`" class="baseline-row">
                <span class="field-path mono" :class="col.kind">
                  {{ col.kind === 'var' ? col.varName : col.field }}
                </span>
                <span class="field-sub">步骤{{ col.stepIndex + 1 }} · {{ col.source }} · {{ col.field }}</span>
                <div class="baseline-edit">
                  <el-input
                    v-if="col.kind === 'var' && col.varName"
                    size="small"
                    :model-value="baselineValue(col)"
                    @update:model-value="(v: string) => setBaseline(col, v)"
                  />
                  <template v-else>
                    <span class="direct-val">{{ col.baseline || '(空)' }}</span>
                    <el-button size="small" text type="primary" @click="promote(col)">提升为变量</el-button>
                  </template>
                  <!-- 只要字段当前还是 `${var.x}` 形态就显示撤销入口(不依赖会话状态) -->
                  <el-button
                    v-if="isPromotableVar(col)"
                    size="small"
                    text
                    type="warning"
                    @click="demote(col)"
                  >
                    撤销提升
                  </el-button>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-collapse-item>
    </el-collapse>

    <!-- 数据表格(转置) -->
    <div class="grid-card">
      <div class="grid-toolbar">
        <span class="grid-title">数据</span>
        <span class="muted">{{ stats.rowCount }} 条</span>
        <div class="grid-actions">
          <el-button size="small" plain @click="addRow">+ 新增数据</el-button>
          <el-button
            size="small"
            plain
            type="primary"
            :disabled="selectedRows.size === 0"
            @click="previewDialogOpen = true"
          >
            预览选中的数据{{ selectedRows.size ? ` (${selectedRows.size})` : '' }}
          </el-button>
          <el-upload
            :show-file-list="false"
            accept=".csv,text/csv"
            :before-upload="onImportCsv"
          >
            <el-button size="small" plain>导入 CSV</el-button>
          </el-upload>
          <el-button size="small" plain :disabled="!varColumns.length" @click="onExportCsv">导出 CSV</el-button>
        </div>
      </div>
      <!-- 字段描述行(从 Plate IOFieldBinding 拉)— description 可选,空时显示 — -->
      <table class="data-table">
        <colgroup>
          <col class="col-select" />
          <col class="col-dataname" />
          <col v-for="col in allColumns" :key="`cg:${col.stepIndex}:${col.source}:${col.field}`" class="col-data" />
          <col class="col-action" />
        </colgroup>
        <thead>
          <tr class="row-info row-desc">
            <th class="th-select">
              <el-checkbox
                :model-value="isAllSelected"
                :indeterminate="isPartialSelected"
                @change="onToggleAll"
                aria-label="全选"
              />
            </th>
            <th class="th-label">描述</th>
            <th
              v-for="col in allColumns"
              :key="`info-d:${col.stepIndex}:${col.source}:${col.field}`"
              :class="['th-data', isPromotableVar(col) ? 'col-promoted' : '']"
              :title="descriptionByColumnKey.get(`${col.stepIndex}:${col.source}:${col.field}`) || col.field"
            >
              {{ descriptionByColumnKey.get(`${col.stepIndex}:${col.source}:${col.field}`) || '—' }}
            </th>
            <th class="th-action" />
          </tr>
          <tr class="row-info row-field">
            <th class="th-select" />
            <th class="th-label">字段</th>
            <th
              v-for="col in allColumns"
              :key="`info-f:${col.stepIndex}:${col.source}:${col.field}`"
              :class="['th-data', isPromotableVar(col) ? 'col-promoted' : '']"
              :title="(col.kind === 'var' ? col.varName : col.field) ?? ''"
            >
              步骤{{ col.stepIndex + 1 }} - {{ col.kind === 'var' ? col.varName : col.field }}
            </th>
            <th class="th-action" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="`r:${i}`" class="row-data">
            <td class="td-select">
              <el-checkbox
                :model-value="selectedRows.has(i)"
                @change="(v: boolean | string | number) => toggleRow(i, !!v)"
                :aria-label="`选中 ${caseNames[i] || `data-${i + 1}`}`"
              />
            </td>
            <td class="td-label">
              <input
                v-model="caseNames[i]"
                class="data-name-input"
                :placeholder="`data-${i + 1}`"
              />
            </td>
            <td
              v-for="col in allColumns"
              :key="`c:${i}:${col.stepIndex}:${col.source}:${col.field}`"
              :class="['td-data', cellClass(row, col), isPromotableVar(col) ? 'col-promoted' : '']"
              :title="col.kind === 'var' ? col.baseline : col.baseline || '空'"
            >
              <input
                v-if="col.kind === 'var'"
                :value="row[col.varName!] ?? ''"
                class="data-cell-input"
                :placeholder="col.baseline"
                @input="(e: Event) => onCellInput(i, col, (e.target as HTMLInputElement).value)"
                @paste="(e: ClipboardEvent) => onCellPaste(e, col, i)"
              />
              <!-- 直填列:数据行里所有数据共享同一字面值;编辑即改 step 字面值(基线 dirty) -->
              <input
                v-else
                :value="directBaselineValue(col)"
                class="data-cell-input data-cell-direct"
                :placeholder="col.baseline || '空'"
                @input="(e: Event) => setDirectBaseline(col, (e.target as HTMLInputElement).value)"
              />
            </td>
            <td class="td-action">
              <el-button size="small" text @click="cloneRow(i)">复制</el-button>
              <el-button size="small" text :icon="Delete" :aria-label="`删除数据 ${i + 1}`" @click="removeRow(i)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- 预览选中的数据:每个数据一行「合并后有效值」(baseline + override) -->
  <el-dialog
    v-model="previewDialogOpen"
    title="预览选中的数据"
    width="640px"
    :close-on-click-modal="false"
  >
    <div v-if="!previewedRows.length" class="muted">未选中任何数据</div>
    <div v-else class="preview-list">
      <div v-for="(item, i) in previewedRows" :key="item.index" class="preview-item">
        <div class="preview-header">
          <span class="preview-name">{{ item.name }}</span>
          <span class="muted">第 {{ item.index + 1 }} 行</span>
        </div>
        <pre class="preview-block">{{ JSON.stringify(item.merged, null, 2) }}</pre>
        <div v-if="item.overrides.length" class="preview-overrides muted">
          override: {{ item.overrides.join(', ') }}
        </div>
        <div v-else class="preview-overrides muted">全部字段都走基线</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Back, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { getDataSet, getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { scenarioDataSetsUrl } from '@/utils/links'
import { deriveBaselineColumns, fieldsOf, type BaselineColumn } from '@/utils/dataset-palette'
import {
  cellDisplay, gridStats, groupByStepLocation,
  matchesQuery, parseTsvPaste, applyPastePlan,
  varOnlyPalette,
} from '@/utils/dataset-grid'
import { exportDataSetCsv, importDataSetCsv } from '@/utils/csv-dataset'
import { useFieldDescriptions } from '@/composables/useFieldDescriptions'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string
const datasetId = route.params.datasetId as string
/** 场景名(来自 draft.definition.meta.name)。draft 未加载或加载失败时回退到
 *  scenarioId,避免主标题空白。 */
const scenarioName = computed(() => draft.value?.definition?.meta?.name || scenarioId)

const savingRows = ref(false)
const savingBaseline = ref(false)
const loadFailed = ref(false)
const form = reactive({ name: '', description: '' })
const rows = ref<Array<Record<string, any>>>([])
const caseNames = ref<string[]>([])
/** 场景草稿本地副本 — 基线唯一事实源;「保存基线」整体 PUT 回场景 */
const draft = ref<{ definition: any; orchestration: any } | null>(null)
const baselineDirty = ref(false)
/** 本会话内「提升过 / 撤销过」过的字段集合 — key = `${stepIndex}:${source}:${field}`。
 *  用于:① 提升后整列加浅灰底色提示「这是新提升的 var」;
 *       ② 撤销提升按钮的入口开关。
 *  重启页面 / 刷新会清空 — 不持久化,只影响会话内视觉与撤销能力。 */
const promotedKeys = reactive<Set<string>>(new Set())
/** 提升顺序栈 — LIFO 弹出,给顶栏「撤销最近一次提升」用。
 *  promotedKeys 是 Set 没有顺序;用数组维护 push/pop 顺序。 */
const promotedOrder = ref<string[]>([])
/** 选中的数据行索引集合(Set)。用于「预览选中的数据」入口。 */
const selectedRows = reactive(new Set<number>())
/** 预览弹窗显示开关 */
const previewDialogOpen = ref(false)
const baselineOpen = ref<string[]>([])        // 默认折叠
const openGroups = ref<string[]>([])           // 步骤分组默认折叠
const baselineQuery = ref('')

const allColumns = computed<BaselineColumn[]>(() =>
  draft.value ? deriveBaselineColumns(draft.value.definition) : [],
)
const varColumns = computed(() => varOnlyPalette(allColumns.value))
const baselineGroups = computed(() => groupByStepLocation(allColumns.value))
const filteredGroups = computed(() => {
  const q = baselineQuery.value
  return baselineGroups.value
    .map((g) => ({ ...g, fields: g.fields.filter((f) => matchesQuery(f, q)) }))
    .filter((g) => g.fields.length)
})

const stats = computed(() => gridStats(allColumns.value, rows.value))

// 字段描述行(Plate IOFieldBinding.description)— 复用 CaseComposer 的缓存
const { descriptionByColumnKey } = useFieldDescriptions(draft as any)

// ── 基线 ───────────────────────────────────────────────
function baselineValue(col: BaselineColumn): string {
  const v = draft.value?.definition?.config?.vars?.[col.varName as string]
  return v === undefined || v === null ? '' : String(v)
}
function setBaseline(col: BaselineColumn, v: string) {
  if (!draft.value || !col.varName) return
  const def = draft.value.definition
  const config = def.config ?? {}
  draft.value = {
    ...draft.value,
    definition: {
      ...def,
      config: { ...config, vars: { ...(config.vars ?? {}), [col.varName]: v } },
    },
  }
  baselineDirty.value = true
}

/** draft 深克隆 + mutate + 整体替换。
 *  - draft 是响应式 ref,Vue 3 对内部深层 mutate 不触发更新,必须新建对象引用
 *  - baselineDirty 在所有写入者处统一翻起
 *  - mutator 返回 true 才算「真改了」,避免 no-op(没找到 fields 等)被误标 dirty,
 *    否则下次保存会 PUT 一份内容未变的数据回服务器。 */
function mutateDraft(mutator: (clone: any) => boolean): void {
  if (!draft.value) return
  const clone = JSON.parse(JSON.stringify(draft.value))
  const changed = mutator(clone)
  if (!changed) return
  draft.value = clone
  baselineDirty.value = true
}

function promote(col: BaselineColumn) {
  if (!draft.value) return
  // promote 是 direct → var,新 var 名自生成(不读 col.varName)。
  let name = ''
  let original: unknown
  mutateDraft((clone) => {
    const step = clone.definition.steps[col.stepIndex]
    const fields = fieldsOf(step, col.source)
    if (!fields) return false
    original = fields[col.field]
    const vars = clone.definition.config?.vars ?? {}
    const base = String(col.field).replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
    name = base
    let n = 2
    while (Object.prototype.hasOwnProperty.call(vars, name)) name = `${base}_${n++}`
    fields[col.field] = `\${var.${name}}`
    clone.definition.config = {
      ...(clone.definition.config ?? {}),
      vars: { ...vars, [name]: original },
    }
    return true
  })
  if (!name) return
  // 标记为「本会话提升过」— 用于整列浅灰底色 + 撤销入口
  const key = `${col.stepIndex}:${col.source}:${col.field}`
  promotedKeys.add(key)
  promotedOrder.value.push(key)
  ElMessage.success(`已提升为变量 ${name}(默认值 = 原值)— 保存基线后生效`)
}

/** 撤销提升:把字段从 `\${var.x}` 还原为字面值,从 config.vars 移除 x。
 *  - 不依赖会话状态 — 只要字段当前是 `${var.x}` 形态 且 x 仍在 config.vars 里,
 *    就允许撤销(刷新页面 / 保存基线后仍可撤销)
 *  - baselineDirty = true,需要「保存基线」PUT 回去 */
function demote(col: BaselineColumn) {
  if (!draft.value || !col.varName) return
  const fields = fieldsOf(draft.value.definition?.steps?.[col.stepIndex], col.source)
  if (!fields) return
  // 找到当前值里的 var 名(`${var.NAME}`)
  // 字符集与 dataset-palette.ts 的 VAR_RE 对齐(允许 `<system>.key` 等点号命名空间)
  const cur = fields[col.field]
  const m = /^\$\{var\.([A-Za-z0-9_.]+)\}$/.exec(typeof cur === 'string' ? cur : '')
  if (!m) {
    // 已经不是 var 形态(可能被用户手动改过)→ 静默跳过
    ElMessage.warning(`字段 ${col.field} 当前不是变量形态,无需撤销`)
    return
  }
  const varName = m[1]
  let applied = false
  mutateDraft((clone) => {
    const f = fieldsOf(clone.definition.steps[col.stepIndex], col.source)
    if (!f) return false
    const vars = { ...(clone.definition.config?.vars ?? {}) }
    // 兜底:若 var 不在 vars 里(罕见,比如用户基线删过),用空串还原
    const orig = vars[varName]
    delete vars[varName]
    f[col.field] = orig === undefined || orig === null ? '' : String(orig)
    clone.definition.config = { ...(clone.definition.config ?? {}), vars }
    applied = true
    return true
  })
  if (!applied) return
  // 同步会话级追踪(给顶栏「撤销最近」用)
  const key = `${col.stepIndex}:${col.source}:${col.field}`
  promotedKeys.delete(key)
  promotedOrder.value = promotedOrder.value.filter((k) => k !== key)
  ElMessage.success(`已撤销提升(变量 ${varName} 已移除)— 保存基线后生效`)
}

/** 判断一个字段是不是「可撤销提升」状态:当前值是 `${var.x}` 且 x 在 vars 里。
 *  不依赖会话状态 — 刷新页面后仍能识别。 */
function isPromotableVar(col: BaselineColumn): boolean {
  if (!draft.value) return false
  if (col.kind !== 'var' || !col.varName) return false
  const fields = fieldsOf(draft.value.definition?.steps?.[col.stepIndex], col.source)
  if (!fields) return false
  const cur = fields[col.field]
  return typeof cur === 'string' && /^\$\{var\./.test(cur)
}

/** 顶栏入口:撤销最近一次提升(按 LIFO 顺序)。
 *  走的是同一份 demote 逻辑,只是从 promotedOrder 末尾弹 key,反查列。 */
function demoteLast() {
  if (!draft.value) return
  const key = promotedOrder.value[promotedOrder.value.length - 1]
  if (!key) return
  const [stepIndexStr, source, field] = key.split(':')
  const stepIndex = Number(stepIndexStr)
  const col = allColumns.value.find(
    (c) => c.stepIndex === stepIndex && c.source === source && c.field === field,
  )
  if (!col) {
    // 字段已不在 columns 里(罕见)— 兜底,直接清栈
    promotedKeys.delete(key)
    promotedOrder.value.pop()
    return
  }
  demote(col)
}

// ── 选中 / 预览选中 ──────────────────────────────────────────────
function toggleRow(i: number, checked: boolean) {
  if (checked) selectedRows.add(i)
  else selectedRows.delete(i)
}
const isAllSelected = computed(() => rows.value.length > 0 && selectedRows.size === rows.value.length)
const isPartialSelected = computed(() => selectedRows.size > 0 && selectedRows.size < rows.value.length)
function onToggleAll(v: boolean | string | number) {
  const next = !!v
  if (next) {
    for (let i = 0; i < rows.value.length; i++) selectedRows.add(i)
  } else {
    selectedRows.clear()
  }
}

/** 把一行 row + 字段定义合并成「实际跑的有效值」(baseline + override)。
 *  - var 列:row[col.varName] ?? baseline  →  用户没填就用基线
 *  - direct 列:col.baseline                →  共享字面值
 *  返回:{ merged, overrides[] }
 *  overrides 列出该行实际 override 的字段名(便于 UI 提示)。 */
function mergeRowWithBaseline(row: Record<string, any>): {
  merged: Record<string, string>
  overrides: string[]
} {
  const merged: Record<string, string> = {}
  const overrides: string[] = []
  for (const col of allColumns.value) {
    let value: string
    if (col.kind === 'var' && col.varName) {
      const override = row[col.varName]
      if (override === undefined) {
        value = col.baseline
      } else {
        value = override === null ? '' : String(override)
        overrides.push(col.varName)
      }
    } else {
      value = col.baseline || ''
    }
    if (col.kind === 'var' && col.varName) {
      merged[col.varName] = value
    } else {
      merged[col.field] = value
    }
  }
  return { merged, overrides }
}

/** 预览弹窗内容:按选中顺序(数组化 selectedRows 排个序)— 不影响原 selectedRows 的 Set 语义。 */
const previewedRows = computed(() => {
  const idxs = Array.from(selectedRows).sort((a, b) => a - b)
  return idxs.map((i) => {
    const { merged, overrides } = mergeRowWithBaseline(rows.value[i] ?? {})
    return {
      index: i,
      name: caseNames.value[i] || `data-${i + 1}`,
      merged,
      overrides,
    }
  })
})

/** 直填列字面值读取(从 draft 里走真实路径:body / query / headers)。 */
function directBaselineValue(col: BaselineColumn): string {
  if (!draft.value) return ''
  const fields = fieldsOf(draft.value.definition?.steps?.[col.stepIndex], col.source)
  if (!fields) return ''
  const v = fields[col.field]
  if (v === undefined || v === null) return ''
  return typeof v === 'string' ? v : String(v)
}

/** 直填列字面值编辑 — 修改 step 的真实字面值(所有数据共享这个 baseline)。
 *  baselineDirty = true,需要点「保存基线」PUT 回场景后才真正生效。 */
function setDirectBaseline(col: BaselineColumn, v: string) {
  if (!draft.value) return
  mutateDraft((clone) => {
    const fields = fieldsOf(clone.definition.steps[col.stepIndex], col.source)
    if (!fields) return false
    // 空串视作显式空值(覆盖 baseline);保留字段键
    fields[col.field] = v
    return true
  })
  // 静默 — 一次性 toast 会打扰用户连续编辑;dirty 标记已经在按钮上
}
async function onSaveBaseline() {
  if (savingBaseline.value) return
  if (!draft.value) return
  savingBaseline.value = true
  try {
    await updateScenario(scenarioId, draft.value)
    baselineDirty.value = false
    ElMessage.success('基线已保存')
  } catch (e) {
    showError('保存基线', e)
  } finally {
    savingBaseline.value = false
  }
}

// ── 数据 ────────────────────────────────────────────────
/** 下一个可用编号:扫现有 caseNames 中匹配 `data-(\d+)` / `case-(\d+)` 的最大值 + 1。
 *  兼容旧 `case-N` 命名(已存在数据集载入时可能带 case- 前缀),输出统一 `data-N`。 */
function nextDataNum(): number {
  let max = 0
  for (const name of caseNames.value) {
    const m = /^(?:data|case)-(\d+)$/.exec(name ?? '')
    if (m) {
      const n = Number(m[1])
      if (n > max) max = n
    }
  }
  return max + 1
}

function addRow() {
  rows.value.push({})
  caseNames.value.push(`data-${nextDataNum()}`)
}
function cloneRow(i: number) {
  rows.value.splice(i + 1, 0, { ...rows.value[i] })
  caseNames.value.splice(i + 1, 0, caseNames.value[i] ?? `data-${nextDataNum()}`)
}
function removeRow(i: number) {
  rows.value.splice(i, 1)
  caseNames.value.splice(i, 1)
}

/** 输入框编辑:空白字符串 = 显式空覆盖(留 key='');@blur 时区分
 *  "用户没改"vs"覆盖为空"——空输入 = 删除 key(回 inherit)。 */
function onCellInput(rowIndex: number, col: BaselineColumn, v: string) {
  const cur = rows.value[rowIndex] ?? {}
  const next = { ...cur }
  if (v === '') {
    // 显式空覆盖:留 key=''
    next[col.varName!] = ''
  } else {
    next[col.varName!] = v
  }
  rows.value[rowIndex] = next
}

/** TSV 粘贴:从某个 cell 出发,把 tab 切的多行写入同一列。 */
function onCellPaste(e: ClipboardEvent, col: BaselineColumn, rowIndex: number) {
  if (!col.varName) return
  const text = e.clipboardData?.getData('text/plain') ?? ''
  if (!text) return
  // 仅当含 \t 或 \n 才接管;普通文本不接管
  if (!/\t|\n/.test(text)) return
  e.preventDefault()
  const plan = parseTsvPaste(text, col.varName, rowIndex, rows.value.length)
  rows.value = applyPastePlan(rows.value, plan)
  // 同步补 caseNames(用 data-N 占位)
  while (caseNames.value.length < rows.value.length) {
    caseNames.value.push(`data-${caseNames.value.length + 1}`)
  }
  if (plan.needsAppend > 0) {
    ElMessage.success(`已粘贴 ${plan.cells.length} 行(自动新增 ${plan.needsAppend} 行)`)
  } else {
    ElMessage.success(`已粘贴 ${plan.cells.length} 行`)
  }
}

/** 三态单元格 class:inherit / override-empty / override-value / direct。 */
function cellClass(row: Record<string, unknown>, col: BaselineColumn): string {
  if (col.kind === 'direct') return 'td-direct'
  const cell = cellDisplay(row, col)
  return `cell-${cell.state}`
}

/** 转 API row:稀疏化(undefined / '' 保留;空字符串 = override-empty 不删) */
function toApiRow(r: Record<string, any>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const k of Object.keys(r)) {
    const v = r[k]
    if (v === undefined) continue
    out[k] = v === null ? '' : String(v)
  }
  return out
}

async function onSaveRows() {
  if (savingRows.value) return
  if (!form.name) {
    ElMessage.warning('请填写数据集名称')
    return
  }
  savingRows.value = true
  try {
    const apiRows = rows.value.map(toApiRow)
    await store.saveDataSet(scenarioId, datasetId === 'new' ? null : datasetId, {
      name: form.name,
      description: form.description,
      rows: apiRows,
    })
    ElMessage.success('已保存')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('保存', e)
  } finally {
    savingRows.value = false
  }
}

async function onDelete() {
  const ok = await confirmAction(
    `删除数据集「${form.name || datasetId}」?此操作不可恢复。`, '删除数据集',
    { confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await store.removeDataSet(scenarioId, datasetId)
    ElMessage.success('已删除')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('删除数据集', e)
  }
}

// ── CSV 导入 / 导出 ─────────────────────────────────────
function onExportCsv() {
  // 字段描述(按 varColumns 顺序,缺描述的列填空串)
  const descriptions = varColumns.value.map(
    (c) => descriptionByColumnKey.value.get(`${c.stepIndex}:${c.source}:${c.field}`) ?? '',
  )
  exportDataSetCsv({
    datasetName: form.name || 'dataset',
    columns: allColumns.value,
    rows: rows.value.map(toApiRow),
    caseNames: caseNames.value,
    descriptions,
  })
}
async function onImportCsv(file: File) {
  try {
    const text = await file.text()
    const result = importDataSetCsv({
      fileText: text,
      columns: allColumns.value,
      rows: rows.value.map(toApiRow),
      caseNames: caseNames.value,
      mode: 'merge-by-name',
    })
    if (result.errors.length) {
      ElMessage.warning(`CSV 导入有问题:${result.errors.join('; ')}`)
    } else {
      ElMessage.success(`CSV 导入成功(共 ${result.rows.length} 条数据)`)
    }
    rows.value = result.rows
    caseNames.value = result.caseNames
  } catch (e) {
    showError('导入 CSV', e)
  }
  return false  // 阻止 el-upload 默认上传行为
}

// ── 加载 ────────────────────────────────────────────────
onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    if (datasetId !== 'new') {
      const full = await getDataSet(datasetId)
      form.name = full.name
      form.description = full.description ?? ''
      rows.value = full.rows.map((r) => ({ ...r }))
      caseNames.value = full.rows.map((_, i) => `data-${i + 1}`)
    } else {
      form.name = '默认数据集'
      caseNames.value = []
    }
  } catch (e) {
    showError('加载', e)
    loadFailed.value = true
  }
})
</script>

<style scoped>
.ds-editor {
  max-width: 1480px; min-height: calc(100vh - 48px);
  padding: 28px 32px 48px; margin: 0 auto; box-sizing: border-box;
}
.page-header {
  display: flex; gap: 24px; align-items: center;
  justify-content: space-between; margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.page-header code.sid {
  padding: 1px 4px; font-family: var(--font-mono); font-size: 11px;
  background: var(--accent-soft); border-radius: 3px;
}
.page-header .scenario-name {
  color: var(--color-text-primary);
  font-weight: 600;
  margin-right: 4px;
}
.header-actions { display: flex; gap: 8px; }
.meta {
  margin: 12px 0; padding: 16px 18px; background: #fff;
  border: 1px solid var(--color-border-tertiary); border-radius: 8px;
}
.grid-3 {
  display: grid; grid-template-columns: 1fr 2fr auto;
  gap: 14px; align-items: center;
}
.mono { font-family: var(--font-mono); font-size: 12px; }
.muted { color: var(--color-text-secondary); font-weight: normal; }

/* ── 折叠基线 ── */
.baseline-collapse {
  margin-bottom: 16px; background: #fff;
  border: 1px solid var(--color-border-tertiary); border-radius: 8px;
  /* 折叠区统一水平缩进 — 设计决定(无 EP 默认约束),所有标题 / 搜索框 / 字段起点共享。
     注:CSS 变量必须挂在 .baseline-collapse 上,不能写 :root —
     <style scoped> 会把 :root 编译为 :root[data-v-xxx],而 html 元素不带
     data-v-xxx 属性,变量永远不会生效,var(--baseline-indent) 引用无效,
     整条 padding-left 声明被丢弃。 */
  --baseline-indent: 30px;
}
/* EP 2.8 el-collapse-item header 默认有底色 + 1px 底边框 + 0 16px padding,
   看起来像嵌套 card 与外层卡片视觉冲突;同时 border-bottom 又会跟我们自己的
   .baseline-rows dashed border 重叠。所以这里把 padding / border / 底色全压成 0。
   水平偏移由 .baseline-title / .group-title / .baseline-toolbar 自己控制(共用 --baseline-indent)。 */
.baseline-collapse :deep(.el-collapse-item__header),
.baseline-collapse :deep(.el-collapse-item__content) {
  padding: 0;
  border: none;
  background: transparent;
}
.baseline-title {
  font-family: var(--font-mono); font-size: 13px; font-weight: 600;
  padding-left: var(--baseline-indent);
}
/* 搜索框所在行 — 单独一行(在 "基线" 标题下方),
   水平 padding 起点用 --baseline-indent(与标题对齐),右侧与卡片 border 一致 */
.baseline-toolbar { padding: 0 16px 12px var(--baseline-indent); display: flex; gap: 8px; }
.baseline-search { width: 280px; }
.baseline-groups { background: transparent; border-top: 1px dashed var(--color-border-tertiary); }
.group-title { font-family: var(--font-mono); font-size: 12px; font-weight: 600; padding-left: var(--baseline-indent); }
.baseline-rows {
  display: flex; flex-direction: column; gap: 8px; padding: 4px 0;
}
/* baseline-row 用 padding-left 与 .baseline-title / .group-title / .baseline-toolbar
   共享同一缩进起点(对齐基线标题文字);后续 field-path / field-sub / baseline-edit
   用 flex + gap 自然展开,避免 grid 固定列宽把长字段名挤进 30px gutter
   与 field-sub 重叠。 */
.baseline-row {
  display: flex; align-items: center; gap: 12px;
  padding: 6px 16px 6px var(--baseline-indent);
  border-bottom: 1px dashed var(--color-border-tertiary);
}
.baseline-row:last-child { border-bottom: none; }
.field-path { font-size: 12px; font-weight: 700; }
.field-path.var { color: var(--accent); }
.field-path.direct { color: #475569; }
.field-sub { font-size: 11px; color: var(--color-text-secondary); }
.baseline-edit { display: flex; align-items: center; gap: 8px; }
.direct-val { font-family: var(--font-mono); font-size: 12px; color: #475569; }

/* ── 数据表格 ── */
.grid-card {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; overflow: hidden;
}
.grid-toolbar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; border-bottom: 1px solid var(--color-border-tertiary);
  background: #f8fafc;
}

/* 字段描述行 + 字段名行 + 数据行 — 全部走同一个 <table>,列对齐
   - colgroup 给每列 120px min,保证四个 thead/tbody 行严格对齐
   - .row-info / .row-quick-add / .row-data 行级只覆盖背景色,不影响 td 宽度
*/
.data-table {
  width: 100%;
  border-collapse: collapse;       /* 关键 — 默认 separate 时 td 间会有缝隙,破坏对齐 */
  table-layout: fixed;             /* 列宽由 colgroup 决定,不被内容撑开 */
  font-family: var(--font-mono); font-size: 12px;
}
.data-table col.col-dataname { width: 140px; }
.data-table col.col-data     { width: 140px; }
.data-table col.col-action   { width: 120px; }
.data-table th, .data-table td {
  padding: 6px 8px;
  border-right: 1px solid var(--color-border-tertiary);
  border-bottom: 1px solid var(--color-border-tertiary);
  vertical-align: middle;
  background: #fff;
  text-align: left;
}
.data-table th:last-child, .data-table td:last-child { border-right: none; }

/* ── 表头 ── */
.data-table .row-info th {
  background: #f1f5f9; font-weight: normal;
  color: var(--color-text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 11px;
}
.data-table .row-desc th  { background: #f1f5f9; }
.data-table .row-field th { background: #e2e8f0; }
.data-table .th-label, .data-table .td-label {
  background: #f8fafc; color: var(--accent);
  font-weight: 700; text-align: center;
  font-family: var(--font-mono);
}
.data-table .th-action, .data-table .td-action {
  text-align: center; color: var(--color-text-secondary);
}

/* ── 数据行 ── */
/* hover 整行轻微高亮(让用户知道这是可交互区域) */
.data-table .row-data:hover td { background: #f8faff; }

/* data-name input:默认就有可见边框(否则跟普通文本没区别,误以为只读) */
.data-table .data-name-input {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  background: #fff;
  padding: 4px 6px;
  border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
  outline: none; box-sizing: border-box;
  color: var(--color-text-primary);
}
.data-table .data-name-input:hover { border-color: #cbd5e1; }
.data-table .data-name-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
  background: #fff;
}

/* 数据格 input:明显的边框 + hover/focus 状态 */
.data-table .data-cell-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 4px; padding: 4px 6px;
  font-family: var(--font-mono); font-size: 12px;
  outline: none; box-sizing: border-box;
  color: var(--color-text-primary);
}
.data-table .data-cell-input::placeholder { color: #94a3b8; }
.data-table .data-cell-input:hover { border-color: #94a3b8; }
.data-table .data-cell-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
  background: #fff;
}

/* 直填列:可编辑 input,改 step 字面值(所有数据共享)。视觉上跟 var 一致,
   但用略浅的背景暗示「这是 baseline,不是 per-data 配置」。 */
.data-table td.td-direct { background: #f8fafc; }
.data-table .data-cell-direct {
  /* 跟 var input 同形状,但稍淡的边框让用户感知「这是 baseline」 */
  border-color: #e2e8f0;
}
.data-table .data-cell-direct:hover { border-color: #cbd5e1; }

/* 三态单元格(只对 var 列有意义) */
/* inherit 状态:背景与 override-value 区分(让用户知道「可编辑但当前用基线」) */
.data-table td.cell-inherit        { background: #f8fafc; }
.data-table td.cell-override-empty {
  background: #fef2f2;
  box-shadow: inset 2px 0 0 #ef4444;
}
.data-table td.cell-override-value { background: #fff; }

/* 提升过的字段列:浅灰底色(thead + tbody 同步),提示「这是本次新提升的 var」 */
.data-table .col-promoted {
  background: #f1f5f9;
}
.data-table .row-info .col-promoted {
  background: #e2e8f0;  /* 表头再深一档,与 row-info 已有色阶一致 */
}
/* hover 高亮需要压过 promoted 的底色,保持「这是可交互列」的视觉 */
.data-table .row-data:hover td.col-promoted { background: #e2e8f0; }

.grid-title { font-weight: 600; font-size: 14px; }
.grid-actions { margin-left: auto; display: flex; gap: 6px; }

/* 选中列宽度 */
.data-table col.col-select { width: 36px; }
.data-table .th-select,
.data-table .td-select {
  text-align: center; vertical-align: middle;
  background: #f8fafc;
  padding: 4px;
}
.data-table .td-select { background: #fff; }
.data-table .row-data:hover .td-select { background: #f8faff; }

/* 预览弹窗 */
.preview-list {
  display: flex; flex-direction: column; gap: 14px;
  max-height: 60vh; overflow-y: auto;
}
.preview-item {
  border: 1px solid var(--color-border-tertiary); border-radius: 6px;
  padding: 10px 12px; background: #f8fafc;
}
.preview-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
}
.preview-name {
  font-family: var(--font-mono); font-size: 13px; font-weight: 600;
  color: var(--accent);
}
.preview-block {
  margin: 0; padding: 10px 12px;
  font-family: var(--font-mono); font-size: 11px; line-height: 1.55;
  color: #cbd5e1; background: #0f172a; border-radius: 4px;
  overflow-x: auto; max-height: 220px; overflow-y: auto;
}
.preview-overrides { margin-top: 6px; font-size: 11px; }
</style>
