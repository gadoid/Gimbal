<!-- DataSetEditor.vue — 单数据集编辑(spec §4 重做:行 0 虚行 + 稀疏行)

     列由场景草稿推导(utils/dataset-palette),两组:
       · 变量列(步骤值含 ${var.x})— 白底可编辑;行 0 = 基线默认值
         (改 config.vars,「保存基线」PUT 回场景)
       · 直填列(步骤里直接填的字面值)— 灰底只读;真实数据行恒 "—";
         行 0 单元格可就地「提升为变量」(D8:步骤值整串替换为 ${var.x}
         + 登记默认值,保存基线后该列变为变量列)
     真实数据行 = 稀疏 dict,键只能是变量名(后端调色板 422 兜底)。
-->
<template>
  <section class="ds-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>数据集编辑</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code> · {{ datasetId === 'new' ? '新建数据集' : datasetId }}</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(scenarioDataSetsUrl(scenarioId))">返回列表</el-button>
        <el-button :loading="savingBaseline" plain :disabled="!draft" @click="onSaveBaseline">
          保存基线{{ baselineDirty ? ' *' : '' }}
        </el-button>
        <el-button v-if="datasetId !== 'new'" type="danger" plain :icon="Delete" @click="onDelete">删除</el-button>
        <el-button type="primary" :loading="savingRows" plain :disabled="loadFailed" @click="onSaveRows">保存数据集</el-button>
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
        <el-form-item label="变量列 / 直填列">
          <span class="mono">{{ varColumns.length }} / {{ columns.length - varColumns.length }}</span>
        </el-form-item>
      </div>
    </el-form>

    <div class="table">
      <!-- 列头:变量列(可被数据集覆盖)与直填列(仅基线可见) -->
      <div class="row head">
        <div class="c c-idx">#</div>
        <div v-for="col in columns" :key="`h:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field">
          <span class="mono col-name">{{ col.kind === 'var' ? col.varName : col.field }}</span>
          <span class="col-sub" :class="col.kind">
            步骤{{ col.stepIndex + 1 }} · {{ col.source }} · {{ col.field }}{{ col.kind === 'direct' ? ' · 直填' : '' }}
          </span>
        </div>
        <div class="c c-action"></div>
      </div>

      <!-- 行 0:基线虚行(场景 payload 投影,不是数据;编辑走「保存基线」) -->
      <div class="row row-zero">
        <div class="c c-idx"><span class="idx">0</span></div>
        <div v-for="col in columns" :key="`z:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field" :class="col.kind">
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
        </div>
        <div class="c c-action"><span class="zero-tag">基线默认</span></div>
      </div>

      <!-- 真实数据行(稀疏:仅变量列可编辑,直填列恒 "—") -->
      <div v-for="(row, i) in rows" :key="i" class="row">
        <div class="c c-idx"><span class="idx">{{ i + 1 }}</span></div>
        <div v-for="col in columns" :key="`r${i}:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field" :class="col.kind">
          <el-input
            v-if="col.kind === 'var' && col.varName"
            v-model="row[col.varName]"
            size="small"
            :placeholder="baselineValue(col)"
          />
          <span v-else class="dash">—</span>
        </div>
        <div class="c c-action">
          <el-button size="small" plain @click="cloneRow(i)">复制</el-button>
          <el-button size="small" plain :icon="Delete" :aria-label="`删除行 ${i + 1}`" @click="removeRow(i)" />
        </div>
      </div>

      <div class="row add-row">
        <span class="add-link" @click="addRow">+ 添加一行(空)</span>
        <span class="add-sep">|</span>
        <span class="add-link" @click="addFromBaseline">从基线提取首行</span>
      </div>
    </div>

    <h3 style="margin-top: 24px;">JSON 预览(稀疏行 — 只含变量列键)</h3>
    <pre class="preview">{{ JSON.stringify({ name: form.name, rows }, null, 2) }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Back, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { deleteDataSet, getDataSet, getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { scenarioDataSetsUrl } from '@/utils/links'
import { deriveBaselineColumns, rowFromBaseline, type BaselineColumn } from '@/utils/dataset-palette'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string
const datasetId = route.params.datasetId as string

const savingRows = ref(false)
const savingBaseline = ref(false)
const loadFailed = ref(false)
const form = reactive({ name: '', description: '' })
const rows = ref<Array<Record<string, any>>>([])
/** 场景草稿本地副本 — 行 0 的唯一事实源;「保存基线」整体 PUT 回场景 */
const draft = ref<{ definition: any; orchestration: any } | null>(null)
const baselineDirty = ref(false)

const columns = computed<BaselineColumn[]>(() =>
  draft.value ? deriveBaselineColumns(draft.value.definition) : [],
)
const varColumns = computed(() => columns.value.filter((c) => c.kind === 'var'))

// ── 行 0(基线)──────────────────────────────────────────────
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

/** 行 0 就地提升(D8):步骤字段值整串替换为 ${var.<name>},默认值 = 原字面值 */
function promote(col: BaselineColumn) {
  if (!draft.value) return
  const clone = JSON.parse(JSON.stringify(draft.value)) // payload 是纯 JSON 值
  const step = clone.definition.steps[col.stepIndex]
  const fields = col.source === 'body' ? step?.request?.body : step?.api?.[col.source]
  if (!fields || typeof fields !== 'object') return
  const original = fields[col.field]
  const vars = clone.definition.config?.vars ?? {}
  const base = String(col.field).replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
  let name = base
  let n = 2
  while (Object.prototype.hasOwnProperty.call(vars, name)) name = `${base}_${n++}`
  fields[col.field] = `\${var.${name}}`
  clone.definition.config = {
    ...(clone.definition.config ?? {}),
    vars: { ...vars, [name]: original },
  }
  draft.value = clone
  baselineDirty.value = true
  ElMessage.success(`已提升为变量 ${name}(默认值 = 原值)— 保存基线后生效`)
}

async function onSaveBaseline() {
  if (!draft.value) return
  savingBaseline.value = true
  try {
    await updateScenario(scenarioId, draft.value)
    baselineDirty.value = false
    ElMessage.success('基线已保存')
  } catch (e) {
    showError('保存基线', undefined, (e as Error).message)
  } finally {
    savingBaseline.value = false
  }
}

// ── 真实数据行(稀疏)───────────────────────────────────────
function addRow() { rows.value.push({}) }

/** 从基线提取首行:每个变量列取行 0 默认值,生成一条可编辑的真实行 */
function addFromBaseline() { rows.value.push(rowFromBaseline(columns.value)) }

function cloneRow(i: number) { rows.value.splice(i + 1, 0, { ...rows.value[i] }) }
function removeRow(i: number) { rows.value.splice(i, 1) }

async function onSaveRows() {
  if (!form.name) {
    ElMessage.warning('请填写数据集名称')
    return
  }
  savingRows.value = true
  try {
    await store.saveDataSet(scenarioId, datasetId === 'new' ? null : datasetId, {
      name: form.name,
      description: form.description,
      rows: rows.value,
    })
    ElMessage.success('已保存')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
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
    await deleteDataSet(datasetId)
    ElMessage.success('已删除')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('删除数据集', undefined, (e as Error).message)
  }
}

// ── 加载:草稿(列/基线唯一事实源)+ 数据集全量行 ─────────────
onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    if (datasetId !== 'new') {
      const full = await getDataSet(datasetId)
      form.name = full.name
      form.description = full.description ?? ''
      rows.value = full.rows.map((r) => ({ ...r }))
    } else {
      form.name = '默认数据集'
    }
  } catch (e) {
    showError('加载', undefined, (e as Error).message)
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
.table {
  padding: 8px; background: #fff;
  border: 1px solid var(--color-border-tertiary); border-radius: 8px;
  overflow-x: auto;
}
.row {
  display: grid;
  grid-template-columns: 32px repeat(auto-fit, minmax(150px, 1fr)) 120px;
  gap: 6px; align-items: center; padding: 6px; border-radius: 6px;
}
.row + .row { margin-top: 4px; }
.row.head { background: #f8fafc; border: 1px solid var(--color-border-tertiary); }
.row:not(.head):not(.add-row):hover { background: #fafbff; }
.c { min-width: 0; }
.c-idx { text-align: center; }
.c-field { display: flex; flex-direction: column; gap: 2px; }
.c-field.direct { background: #f8fafc; border-radius: 4px; padding: 4px; }
.col-name { font-family: var(--font-mono); font-size: 12px; font-weight: 700; }
.col-sub { font-size: 10px; color: var(--color-text-secondary); }
.idx { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary); }
.row-zero { background: #f8fafc; border: 1px dashed var(--color-border-tertiary); }
.direct-val { font-family: var(--font-mono); font-size: 11px; color: #475569; }
.dash { color: #cbd5e1; text-align: center; }
.zero-tag {
  font-size: 10px; color: #92400e;
  background: #fef3c7; border-radius: 3px; padding: 1px 6px;
}
.c-action { display: flex; gap: 4px; justify-content: center; align-items: center; }
.add-row {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  margin-top: 6px; padding: 10px; color: var(--color-text-secondary);
  font-size: 11px; background: #f8fafc;
  border: 1px dashed var(--color-border-tertiary);
}
.add-link { cursor: pointer; }
.add-link:hover { color: var(--accent); }
.add-sep { color: #cbd5e1; }
.preview {
  padding: 12px; margin: 0; max-height: 240px; overflow: auto;
  font-family: var(--font-mono); font-size: 11px; line-height: 1.55;
  color: #cbd5e1; background: #0f172a; border-radius: 6px;
}
</style>
