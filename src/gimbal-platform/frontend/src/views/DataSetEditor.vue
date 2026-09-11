<!-- DataSetEditor.vue — 转置表 + 段多选网格(基线区已退场)

     信息架构:
       - 全宽数据表格(行 = 数据,列 = 勾选段的变量并排;直填列不进表格,
         编辑家在编排器 FieldForm)
       - 段多选(spec §6.2 演进):引用扫描派生段,勾选框并列多段;
         "全部" = master 快捷(勾=全选 / 取消=回只选首段);至少一段
       - 置顶基线行(tbody 首行):config.vars 基线唯一编辑入口,
         不可选 / 不可粘贴;编辑触发 baselineDirty →「保存基线」
       - 期望列与输入列并排(行键 = varName),列头带「期望」徽标(target/operator)
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
            变量 {{ stats.varCount }} · 数据 {{ stats.rowCount }} · 覆盖 {{ stats.overrideCount }} 格
          </span>
        </el-form-item>
      </div>
    </el-form>

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
          <el-button size="small" plain :disabled="!csvVarColumns.length" @click="onExportCsv">导出 CSV</el-button>
        </div>
      </div>
      <!-- 段多选(spec §6.2 演进):>1 段才显示;勾选段并列,
           "全部" = master 快捷(勾=全选 / 取消=回只选首段);至少一段 -->
      <div v-if="segments.length > 1" class="seg-picker">
        <el-checkbox
          class="seg-all"
          :model-value="isAllSegs"
          :indeterminate="isPartialSegs"
          @change="onToggleAllSegs"
        >全部({{ totalGridColumns }} 列)</el-checkbox>
        <el-checkbox
          v-for="(seg, si) in segments"
          :key="`segsel:${seg.stepIndex}`"
          :model-value="selectedSegs.has(si)"
          @change="(v: boolean | string | number) => toggleSeg(si, !!v)"
        >步骤{{ seg.stepIndex + 1 }} · {{ stepLabel(seg.stepIndex) }}</el-checkbox>
      </div>
      <!-- 死行键软提示(spec §7):行键 ∉ config.vars 列宇宙 — 标黄提示,不阻断编辑 -->
      <div v-if="deadKeys.length" class="dead-keys-bar">
        ⚠ {{ deadKeys.length }} 个行键不在列宇宙(变量已删):{{ deadKeys.join(', ') }} — 运行无效果,可继续编辑(spec §7 软提示)
      </div>
      <!-- 横向滚动容器:变量列多时表格按 colgroup 定宽展开,拖动条滚动查看;
           工具栏留在滚动区外不随之移动 -->
      <div class="grid-scroll">
      <!-- 字段描述行(从 Plate IOFieldBinding 拉)— description 可选,空时显示 — -->
      <table class="data-table">
        <colgroup>
          <col class="col-select" />
          <col class="col-dataname" />
          <col v-for="(col, ci) in visibleColumns" :key="`cg:${ci}:${col.stepIndex}:${col.source}:${col.varName}`" class="col-data" />
          <col class="col-action" />
        </colgroup>
        <thead>
          <!-- 步骤分组行(P1.4):同 stepIndex 相邻列合并 colspan,横多列时
               一眼看出列属于哪个步骤;名读 orchestration,缺名降级 Step N。
               勾选 >1 段才渲染 — 单段无段间边界可标。 -->
          <tr v-if="selectedSegCount > 1" class="row-step-group">
            <th class="th-select" />
            <th class="th-label" />
            <th
              v-for="g in stepGroups"
              :key="`grp:${g.stepIndex}`"
              :colspan="g.colspan"
              class="th-step-group"
            >步骤 {{ g.stepIndex + 1 }} · {{ stepLabel(g.stepIndex) }}</th>
            <th class="th-action" />
          </tr>
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
              v-for="(col, ci) in visibleColumns"
              :key="`info-d:${ci}:${col.stepIndex}:${col.source}:${col.varName}`"
              :class="['th-data', col.source === 'expect' ? 'col-expect' : '', selectedSegCount > 1 && isStepStart(ci) ? 'is-step-start' : '']"
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
              v-for="(col, ci) in visibleColumns"
              :key="`info-f:${ci}:${col.stepIndex}:${col.source}:${col.varName}`"
              :class="['th-data', col.source === 'expect' ? 'col-expect' : '', selectedSegCount > 1 && isStepStart(ci) ? 'is-step-start' : '']"
              :title="col.source === 'expect'
                ? `期望列 ${col.varName} — 断言 ${col.expect?.target} ${col.expect?.operator}(步骤${col.stepIndex + 1})`
                : `${col.stepIndex + 1} 步 ${col.source} · ${col.field}`"
            >
              步骤{{ col.stepIndex + 1 }} - {{ col.varName }}
              <span
                v-if="segSharedVars.has(col.varName)"
                class="shared-mark"
                title="该变量被多个步骤引用 — 数据行里改一处,所有引用处生效"
              >共享</span>
              <span
                v-if="col.source === 'expect'"
                class="exp-col-badge"
                :title="`期望列 — 断言 ${col.expect?.target} ${col.expect?.operator}`"
              >期望</span>
              <button
                v-if="col.source === 'expect'"
                type="button"
                class="exp-jump"
                :title="`跳编排器断言卡 — ${col.expect?.target} ${col.expect?.operator}`"
                @click.stop="jumpToAssertion(col)"
              >↗</button>
            </th>
            <th class="th-action" />
          </tr>
        </thead>
        <tbody>
          <!-- 置顶基线行:config.vars 基线唯一编辑入口 — 不可选(无 checkbox)/
               不可粘贴(无 paste 接管);编辑触发 baselineDirty →「保存基线」 -->
          <tr class="row-baseline">
            <td class="td-select" />
            <td class="td-label">基线</td>
            <td
              v-for="(col, ci) in visibleColumns"
              :key="`b:${ci}:${col.stepIndex}:${col.source}:${col.varName}`"
              :class="['td-data', col.source === 'expect' ? 'col-expect' : '', selectedSegCount > 1 && isStepStart(ci) ? 'is-step-start' : '']"
            >
              <input
                class="baseline-cell-input"
                :value="baselineValue(bcOf(col))"
                :aria-label="`基线 ${col.varName}`"
                @input="(e: Event) => setBaseline(bcOf(col), (e.target as HTMLInputElement).value)"
              />
            </td>
            <td class="td-action" />
          </tr>
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
              v-for="(col, ci) in visibleColumns"
              :key="`c:${i}:${ci}:${col.stepIndex}:${col.source}:${col.varName}`"
              :class="['td-data', cellClass(row, bcOf(col)), col.source === 'expect' ? 'col-expect' : '', selectedSegCount > 1 && isStepStart(ci) ? 'is-step-start' : '']"
              :title="bcOf(col).baseline"
            >
              <!-- 期望列与输入列同款单元格:行键 = varName,期望列 baseline
                   = config.vars 值(Task 1 契约),placeholder 显基线 -->
              <input
                :value="row[col.varName] ?? ''"
                class="data-cell-input"
                :placeholder="col.baseline === undefined || col.baseline === null ? '' : String(col.baseline)"
                @input="(e: Event) => onCellInput(i, bcOf(col), (e.target as HTMLInputElement).value)"
                @paste="(e: ClipboardEvent) => onCellPaste(e, bcOf(col), i)"
              />
            </td>
            <td class="td-action">
              <el-button size="small" text @click="cloneRow(i)">复制</el-button>
              <el-button size="small" text :icon="Delete" :aria-label="`删除数据 ${i + 1}`" @click="removeRow(i)" />
            </td>
          </tr>
        </tbody>
      </table>
      </div><!-- /grid-scroll -->
    </div>
  </section>

  <!-- 预览选中的数据:行详情(spec §6.2 v1 只读)— 按段分组垂直呈现 + 继承态标注。
       append-to-body:弹层 teleport 出编辑器的 overflow/stacking 上下文 -->
  <el-dialog
    v-model="previewDialogOpen"
    title="预览选中的数据"
    width="640px"
    append-to-body
    :close-on-click-modal="false"
  >
    <div v-if="!previewedRows.length" class="muted">未选中任何数据</div>
    <div v-else class="preview-list">
      <div v-for="item in previewedDetail" :key="item.index" class="preview-item">
        <div class="preview-header">
          <span class="preview-name">{{ item.name }}</span>
          <span class="muted">第 {{ item.index + 1 }} 行</span>
        </div>
        <div v-for="g in item.groups" :key="g.stepIndex" class="detail-seg">
          <div class="detail-seg-head">{{ g.label }}</div>
          <div v-for="(it, gi) in g.items" :key="`${g.stepIndex}:${gi}:${it.varName}`" class="detail-row">
            <span class="detail-name mono">{{ it.varName }}</span>
            <span v-if="it.expect" class="exp-col-badge" :title="`断言 ${it.expect.target} ${it.expect.operator}`">期望</span>
            <span class="detail-val mono">{{ it.value === undefined ? '(未声明基线)' : JSON.stringify(it.value) }}</span>
            <span class="detail-flag" :class="it.inherited ? 'inh' : 'ovr'">{{ it.inherited ? '继承基线' : '覆写' }}</span>
          </div>
        </div>
        <div v-if="item.dead.length" class="detail-dead">死键(变量已删,运行无效果):{{ item.dead.join(', ') }}</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Back, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { getDataSet, getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { scenarioDataSetsUrl } from '@/utils/links'
import { type BaselineColumn } from '@/utils/dataset-palette'
import {
  cellDisplay, gridStats, parseTsvPaste, applyPastePlan,
} from '@/utils/dataset-grid'
import {
  deriveSegments, gridColumnsOf, sharedVarNames, deadRowKeys,
  type GridVarColumn,
} from '@/utils/dataset-segments'
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
/** 选中的数据行索引集合(Set)。用于「预览选中的数据」入口。 */
const selectedRows = reactive(new Set<number>())
/** 预览弹窗显示开关 */
const previewDialogOpen = ref(false)

// ── 段网格(spec §6.2 演进:勾选多选)─────────────────────────
/** 段派生(spec §6.2):打开编辑器对场景一次引用扫描(纯前端投影) */
const segments = computed(() => deriveSegments(
  draft.value?.definition?.steps ?? [],
  draft.value?.definition?.config?.vars ?? {},
))
const segSharedVars = computed(() => sharedVarNames(segments.value))
const ALL_THRESHOLD = 8   // 全段列数 ≤8 默认全段勾选(spec §6.2 初值)

/** 勾选段索引集合(checkbox 多选);至少一段 — 取消最后一段 no-op + 提示 */
const selectedSegs = reactive(new Set<number>())
const segInitialized = ref(false)
watch(segments, (segs) => {
  if (segInitialized.value || !segs.length) return
  segInitialized.value = true
  const total = segs.reduce((n, s) => n + gridColumnsOf(s).length, 0)
  if (total <= ALL_THRESHOLD) segs.forEach((_, si) => selectedSegs.add(si))
  else selectedSegs.add(0)
}, { immediate: true })

const selectedSegCount = computed(() => selectedSegs.size)
const isAllSegs = computed(() =>
  segments.value.length > 0 && selectedSegs.size === segments.value.length)
const isPartialSegs = computed(() =>
  selectedSegs.size > 0 && selectedSegs.size < segments.value.length)
/** master「全部」:勾 = 全选;取消 = 回只选首段(至少一段约束的快捷回退) */
function onToggleAllSegs(v: boolean | string | number) {
  if (!segments.value.length) return
  selectedSegs.clear()
  if (!!v) segments.value.forEach((_, si) => selectedSegs.add(si))
  else selectedSegs.add(0)
}
function toggleSeg(si: number, checked: boolean) {
  if (checked) selectedSegs.add(si)
  else {
    if (selectedSegs.size <= 1) {
      ElMessage.warning('至少保留一个步骤段')
      return
    }
    selectedSegs.delete(si)
  }
}

/** 全段总列数("全部"快捷标签提示用) */
const totalGridColumns = computed(() =>
  segments.value.reduce((n, s) => n + gridColumnsOf(s).length, 0))

/** 勾选段的列并排(段序);勾选 >1 段时表头渲染步骤分组行 + 段首分隔线 */
const visibleColumns = computed<GridVarColumn[]>(() =>
  segments.value.flatMap((seg, si) => (selectedSegs.has(si) ? gridColumnsOf(seg) : [])),
)

/** GridVarColumn → BaselineColumn 适配:cellClass/onCellInput/onCellPaste
 *  既有签名消费完整 BaselineColumn 形状(最小适配对象补齐
 *  stepIndex/source/field)。 */
function bcOf(col: GridVarColumn): BaselineColumn {
  return {
    stepIndex: col.stepIndex,
    source: col.source === 'headers' ? 'headers' : 'body',
    field: col.field,
    kind: 'var',
    varName: col.varName,
    baseline: col.baseline === undefined || col.baseline === null ? '' : String(col.baseline),
  }
}

/** CSV 导入导出链专用:全量 var 列宇宙(brief ⑥ — 不随段过滤)。
 *  flatMap gridColumnsOf 覆盖 ALL 段(输入列 + 期望列);columns 与
 *  descriptions 同源同序 → 单段模式下他段列不丢,(description) 行守卫
 *  (descriptions.length === vars.length)恒满足,不再静默丢描述行。
 *  varName 首现去重(修轮 f2):同一 var 兼为输入与期望(或跨段重复)时
 *  行键唯一(行键 = varName),CSV 列头重复会让导入端同列互踩 — 输入列
 *  先于期望列(gridColumnsOf 序),首现胜出。 */
const csvVarColumns = computed<BaselineColumn[]>(() => {
  const seen = new Set<string>()
  const out: BaselineColumn[] = []
  for (const col of segments.value.flatMap(gridColumnsOf)) {
    if (seen.has(col.varName)) continue
    seen.add(col.varName)
    out.push(bcOf(col))
  }
  return out
})

// ── 步骤分组表头(P1.4:横多列时按 step 视觉分组,零后端)─────────
/** 列序上同 stepIndex 的连续段(merge 相邻同段,colspan 呈现)。
 *  仅勾选 >1 段时渲染(模板侧短路);单段无段间边界可标。 */
const stepGroups = computed(() => {
  const groups: Array<{ stepIndex: number; colspan: number }> = []
  for (const col of visibleColumns.value) {
    const last = groups[groups.length - 1]
    if (last && last.stepIndex === col.stepIndex) last.colspan++
    else groups.push({ stepIndex: col.stepIndex, colspan: 1 })
  }
  return groups
})
/** 步骤展示名:读 orchestration.steps[i].name(平台编排视图,plate Step
 *  无 name 字段);缺名/越界降级 Step N(同 RunDialog stepTo 下拉语义)。 */
function stepLabel(i: number): string {
  const name = draft.value?.orchestration?.steps?.[i]?.name
  return name || `Step ${i + 1}`
}
/** 该列是所属步骤段的首列 → 渲染左分隔线(表头到数据行贯穿)。
 *  仅勾选 >1 段时消费(模板侧短路);单段无段间边界。 */
function isStepStart(ci: number): boolean {
  const cols = visibleColumns.value
  return ci === 0 || cols[ci - 1].stepIndex !== cols[ci].stepIndex
}

/** 期望列头 → 断言卡直跳(spec §5.3):路由携带 focusStep/focusStrategy,
 *  CaseComposer onMounted 消费(Task 3 契约)。索引恒为数字转串 —
 *  绝不发空串(Number('') === 0 会骗过消费端守卫,伪造 0/0 跳转)。 */
function jumpToAssertion(col: GridVarColumn) {
  if (!col.expect) return
  router.push({
    path: `/composer/${scenarioId}`,
    query: {
      step: '4',
      focusStep: String(col.stepIndex),
      focusStrategy: String(col.expect.strategyIdx),
    },
  })
}

/** 死行键(spec §7 软提示):行键 ∉ config.vars 列宇宙 → 提示条标黄,
 *  不阻断编辑(变量已删但行数据还在的悬空键)。 */
const deadKeys = computed(() => deadRowKeys(draft.value?.definition?.config?.vars ?? {}, rows.value))

/** 摘要统计:列宇宙 = csvVarColumns(全段 var 列,不随勾选段过滤) */
const stats = computed(() => gridStats(csvVarColumns.value, rows.value))

// 字段描述行(Plate IOFieldBinding.description)— 复用 CaseComposer 的缓存
const { descriptionByColumnKey } = useFieldDescriptions(draft as any)

// ── 基线(置顶基线行消费)─────────────────────────────────
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

/** 预览弹窗行索引:按选中顺序(数组化 selectedRows 排个序)— 不影响原
 *  selectedRows 的 Set 语义;值/继承态由 previewedDetail 按段展开。 */
const previewedRows = computed(() => {
  const idxs = Array.from(selectedRows).sort((a, b) => a - b)
  return idxs.map((i) => ({
    index: i,
    name: caseNames.value[i] || `data-${i + 1}`,
  }))
})

/** 行详情(§6.2 v1 只读):整条数据垂直呈现,按段分组 + 继承态标注 */
const previewedDetail = computed(() => previewedRows.value.map((item) => {
  const row = rows.value[item.index] ?? {}
  return {
    ...item,
    groups: segments.value.map((seg) => ({
      stepIndex: seg.stepIndex,
      label: `步骤${seg.stepIndex + 1} · ${stepLabel(seg.stepIndex)}`,
      items: gridColumnsOf(seg).map((c) => ({
        varName: c.varName,
        value: Object.prototype.hasOwnProperty.call(row, c.varName) ? row[c.varName] : c.baseline,
        inherited: !Object.prototype.hasOwnProperty.call(row, c.varName),
        expect: c.expect,
      })),
    })),
    dead: deadRowKeys(draft.value?.definition?.config?.vars ?? {}, [row]),
  }
}))

/** 直填列编辑入口已退场(2026-09-11 基线区退场):字面值的家在编排器
 *  FieldForm — 数据集编辑器只消费 config.vars 列宇宙,不再改 step 字面值。 */
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

/** 三态单元格 class:inherit / override-empty / override-value。 */
function cellClass(row: Record<string, unknown>, col: BaselineColumn): string {
  return `cell-${cellDisplay(row, col).state}`
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
  // 字段描述(按 csvVarColumns 顺序,缺描述的列填空串)— 全量宇宙,
  // 与 exportDataSetCsv 内部 varOnlyPalette(columns) 同源同序,不受段过滤影响
  const descriptions = csvVarColumns.value.map(
    (c) => descriptionByColumnKey.value.get(`${c.stepIndex}:${c.source}:${c.field}`) ?? '',
  )
  exportDataSetCsv({
    datasetName: form.name || 'dataset',
    columns: csvVarColumns.value,
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
      // 与导出同宇宙(全段输入列 + 期望列,不随段过滤):导出的列可原样回导
      columns: csvVarColumns.value,
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

/* ── 段多选(spec §6.2 演进):勾选段并列 + 全部 master ── */
.seg-picker { display: flex; gap: 4px 18px; flex-wrap: wrap; align-items: center; padding: 8px 12px 0; }
.seg-picker .seg-all { font-weight: 600; }

/* 死行键软提示条(spec §7):标黄不阻断 */
.dead-keys-bar { margin: 6px 12px 0; font-size: 11px; color: #b45309; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 5px 10px; }

/* 期望列头 ↗ 跳断言卡(spec §5.3) */
.exp-jump { border: none; background: transparent; color: #7c3aed; cursor: pointer; font-size: 12px; padding: 0 2px; }
.exp-jump:hover { color: #4c1d95; }

/* 横向滚动:列少时表格仍占满(width:100%),列多时按 colgroup 定宽展开
   (min-width:max-content 赢),拖滚动条查看右侧列 */
.grid-scroll { overflow-x: auto; }

/* 字段描述行 + 字段名行 + 数据行 — 全部走同一个 <table>,列对齐
   - colgroup 给每列 120px min,保证四个 thead/tbody 行严格对齐
   - .row-info / .row-quick-add / .row-data 行级只覆盖背景色,不影响 td 宽度
*/
.data-table {
  width: 100%;
  min-width: max-content;          /* 列多时不被压扁 — 撑开到 colgroup 总宽,交给 .grid-scroll 滚动 */
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

/* 步骤分组行:比 row-field 更深一档的底色,colspan 段 + 段间分隔线
   (P1.4 — 横多列时按 step 视觉分组) */
.data-table .row-step-group th {
  background: #dde3ee;
  color: #334155;
  font-weight: 700;
  font-size: 11px;
  text-align: center;
  border-left: 1px solid #c3ccdb;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.data-table .row-step-group th:first-of-type { border-left: none; }
/* 步骤段首列:贯穿 thead(描述/字段行)与 tbody 的左分隔线 */
.data-table .is-step-start { border-left: 1px solid #c3ccdb; }
/* 共享 var 徽标:多步骤引用同一变量(config.vars 单值,改一处全局生效) */
.data-table .shared-mark {
  display: inline-block;
  margin-left: 4px; padding: 0 4px;
  border-radius: 3px;
  background: #eef2ff; color: #4338ca;
  font-size: 10px; line-height: 16px;
  vertical-align: middle;
}
/* 期望列(spec §6.2):列头徽标 + 淡紫底,与输入列并排但可辨识 */
.col-expect .exp-col-badge { font-size: 10px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }
.th-data.col-expect { background: #faf5ff; }
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

/* 置顶基线行(tbody 首行):config.vars 基线唯一编辑入口 —
   灰底与数据行区分;不可选 / 不可粘贴(无交互态) */
.data-table .row-baseline td { background: #f1f5f9; }
.data-table .row-baseline .td-label { color: #64748b; }
.baseline-cell-input {
  width: 100%;
  border: 1px dashed #cbd5e1;
  background: #fff;
  border-radius: 4px; padding: 4px 6px;
  font-family: var(--font-mono); font-size: 12px;
  outline: none; box-sizing: border-box;
  color: var(--color-text-primary);
}
.baseline-cell-input:focus {
  border-color: var(--accent); border-style: solid;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

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

/* 三态单元格(只对 var 列有意义) */
/* inherit 状态:背景与 override-value 区分(让用户知道「可编辑但当前用基线」) */
.data-table td.cell-inherit        { background: #f8fafc; }
.data-table td.cell-override-empty {
  background: #fef2f2;
  box-shadow: inset 2px 0 0 #ef4444;
}
.data-table td.cell-override-value { background: #fff; }

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

/* ── 行详情(§6.2 v1 只读):按段分组垂直呈现 ── */
/* 期望徽标在弹窗侧的样式(网格侧挂在 .col-expect 下,弹窗行无该祖先) */
.detail-row .exp-col-badge { font-size: 10px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 1px 5px; border-radius: 3px; }
.detail-seg-head { font-size: 12px; font-weight: 700; color: #475569; margin: 8px 0 4px; }
.detail-row { display: flex; gap: 8px; align-items: center; padding: 2px 0 2px 12px; font-size: 12px; }
.detail-name { min-width: 120px; color: #334155; }
.detail-val { color: #0f172a; }
.detail-flag { font-size: 10px; padding: 1px 6px; border-radius: 3px; }
.detail-flag.inh { color: #64748b; background: #f1f5f9; }
.detail-flag.ovr { color: #b45309; background: #fef3c7; }
.detail-dead { margin-top: 6px; font-size: 11px; color: #b45309; background: #fef3c7; padding: 4px 8px; border-radius: 4px; }
</style>
