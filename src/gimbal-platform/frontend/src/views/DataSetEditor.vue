<!-- DataSetEditor.vue — 单数据集编辑（行级字段矩阵）
     列：# / 字段1 / 字段2 / ... / 备注 / 最后结果 / 操作（复制 / 单条运行 / 删除）
     行编辑使用 el-input 直接绑定 rows[i][col]，列由首行 keys 推断
-->
<template>
  <section class="ds-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>数据集编辑</h2>
        <p>用例 <code class="sid">{{ caseId }}</code> · {{ datasetId === 'new' ? '新建数据集' : datasetId }}</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(caseDataSetsUrl(caseId))">返回列表</el-button>
        <el-button :loading="saving" plain :disabled="loadFailed" @click="onSave">保存</el-button>
        <el-button type="primary" :icon="VideoPlay" @click="onBatchRun" :disabled="!rows.length">批量运行 {{ rows.length }} 条</el-button>
      </div>
    </header>

    <el-form label-position="top" class="meta">
      <div class="grid-3">
        <el-form-item label="数据集名称">
          <el-input v-model="form.name" placeholder="边界 qty 集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="qty = 0, 1, 999, -1（验证边界值）" />
        </el-form-item>
        <el-form-item label="字段数">
          <span class="mono">{{ columns.length }}</span>
        </el-form-item>
      </div>
    </el-form>

    <div class="table">
      <!-- 列头 -->
      <div class="row head">
        <div class="c c-idx">#</div>
        <div v-for="(col, idx) in columns" :key="idx" class="c c-field">
          <el-input v-model="columns[idx]" size="small" placeholder="字段名" />
        </div>
        <div class="c c-action">
          <el-button size="small" plain @click="addColumn">+ 列</el-button>
        </div>
      </div>

      <!-- 数据行 -->
      <div v-for="(row, i) in rows" :key="i" class="row">
        <div class="c c-idx">
          <span class="idx">{{ i + 1 }}</span>
        </div>
        <div v-for="col in columns" :key="col" class="c c-field">
          <el-input
            v-model="(row as any)[col]"
            size="small"
            :placeholder="col"
          />
        </div>
        <div class="c c-action">
          <el-button size="small" plain @click="cloneRow(i)">复制</el-button>
          <el-button size="small" plain :icon="VideoPlay" @click="runRow(i)" aria-label="运行此行" />
          <el-button size="small" plain :icon="Delete" @click="removeRow(i)" aria-label="删除此行" />
        </div>
      </div>

      <div class="row add-row" @click="addRow">
        + 添加一行
      </div>
    </div>

    <h3 style="margin-top: 24px;">JSON 预览</h3>
    <pre class="preview">{{ JSON.stringify({ name: form.name, rows }, null, 2) }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Back, DataAnalysis, Delete, VideoPlay } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { getDataSet } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { caseDataSetsUrl, caseViewUrl, composerUrl } from '@/utils/links'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const caseId = route.params.caseId as string
const datasetId = route.params.datasetId as string

const saving = ref(false)
// 已有 datasetId 加载失败（被删除 / 网络错误）时禁止保存，避免把
// 空行 PUT 到一个可能不存在的 id 上。
const loadFailed = ref(false)

const form = reactive({ name: '', description: '' })
const columns = ref<string[]>(['customer_id', 'qty', 'expected_status'])
const rows = ref<Array<Record<string, any>>>([])

const current = computed(() =>
  datasetId === 'new' ? null : store.dataSetById(datasetId),
)

onMounted(async () => {
  try {
    if (!store.dataSets.length) await store.fetchDataSets(caseId)
    const ds = current.value
    if (ds) {
      form.name = ds.name
      form.description = ds.description ?? ''
      // P0 修复：store 里的 preview 被截为前 3 行，直接编辑保存会静默
      // 丢弃第 4 行起的数据。必须用 getDataSet 拉全量 rows。
      let fullRows = ds.preview
      try {
        const full = await getDataSet(ds.datasetId)
        fullRows = full.rows
      } catch {
        showError('加载完整行数据失败，当前仅为前 3 行预览 — 保存将丢失其余行', undefined)
      }
      rows.value = fullRows.map((r) => ({ ...r }))
      // 推断列：第一行 keys
      if (rows.value[0]) columns.value = Object.keys(rows.value[0])
    } else if (datasetId !== 'new') {
      // datasetId 存在但列表里没有（fetch 失败 / 已被删除）：
      // 直接拉一次全量，仍失败才按新建处理，避免误把空行 PUT 到该 id。
      try {
        const full = await getDataSet(datasetId)
        form.name = full.name
        form.description = full.description ?? ''
        rows.value = full.rows.map((r) => ({ ...r }))
        if (rows.value[0]) columns.value = Object.keys(rows.value[0])
      } catch {
        showError('数据集不存在或已被删除', undefined)
        loadFailed.value = true
        addRow()
      }
    } else {
      addRow()
    }
  } catch (e) {
    showError('加载数据集', undefined, (e as Error).message)
  }
})

// 列变化时给所有行补上空字段
let prevColumns: string[] = [...columns.value]
watch(columns, (cols) => {
  // 非法表头态直接回滚：清空列名会让数据"失联"（rows 里旧 key 仍在
  // 但不再渲染，且会写入 '' 键）；改成已有列名会静默覆盖/合并两列
  // 数据。两种都还原为上一个合法名并提示。
  if (cols.length === prevColumns.length) {
    for (let i = 0; i < cols.length; i++) {
      const oldName = prevColumns[i]
      const newName = cols[i]
      if (oldName && newName === '') {
        columns.value[i] = oldName
        ElMessage.warning('列名不能为空')
        return
      }
      if (
        newName && oldName && newName !== oldName &&
        cols.filter((c) => c === newName).length > 1
      ) {
        columns.value[i] = oldName
        ElMessage.warning(`列名 "${newName}" 已存在`)
        return
      }
    }
  }
  // 列重命名（表头 el-input 直接改 columns[idx]）：旧 key 下的数据必须
  // 迁到新 key，否则 rows 仍按旧 key 存值、保存 payload 携带旧键 +
  // 空新键 — 重命名等于静默丢列数据。
  if (cols.length === prevColumns.length) {
    for (let i = 0; i < cols.length; i++) {
      const oldName = prevColumns[i]
      const newName = cols[i]
      if (oldName && newName && oldName !== newName && !cols.includes(oldName)) {
        for (const r of rows.value) {
          r[newName] = r[oldName]
          delete r[oldName]
        }
      }
    }
  }
  prevColumns = [...cols]
  // 新增列 / 加载后的补空
  for (const r of rows.value) {
    for (const c of cols) if (!(c in r)) r[c] = ''
  }
}, { deep: true })

function addColumn() {
  const name = window.prompt('新列名（英文 / 字母数字）')
  if (!name || columns.value.includes(name)) return
  columns.value.push(name)
  for (const r of rows.value) r[name] = ''
}

function addRow() {
  const seed: Record<string, any> = {}
  for (const c of columns.value) seed[c] = ''
  rows.value.push(seed)
}

function cloneRow(i: number) {
  rows.value.splice(i + 1, 0, { ...rows.value[i] })
}

function removeRow(i: number) {
  rows.value.splice(i, 1)
}

function runRow(i: number) {
  ElMessage.info(`单条运行 #${i + 1} (待后端支持)`)
}

async function onSave() {
  saving.value = true
  try {
    await store.saveDataSet(caseId, datasetId === 'new' ? null : datasetId, {
      name: form.name,
      description: form.description,
      rows: rows.value,
    })
    ElMessage.success('已保存')
    router.push(caseDataSetsUrl(caseId))
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
  } finally {
    saving.value = false
  }
}

/** 批量运行统一走编排器的 RunDialog(先保存,再到运行对话框勾选本数据集) */
async function onBatchRun() {
  if (datasetId === 'new') {
    ElMessage.warning('请先保存数据集，再批量运行')
    return
  }
  let sid = store.caseById(caseId)?.scenarioId
  if (!sid) {
    try { await store.fetchCases() } catch { /* 忽略,回退到详情页 */ }
    sid = store.caseById(caseId)?.scenarioId
  }
  router.push(sid ? composerUrl(sid) : caseViewUrl(caseId))
}
</script>

<style scoped>
.ds-editor {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p  { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.page-header code.sid {
  padding: 1px 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 3px;
}
.header-actions { display: flex; gap: 8px; }

.meta {
  margin: 12px 0;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.grid-3 {
  display: grid;
  grid-template-columns: 1fr 2fr auto;
  gap: 14px;
  align-items: center;
}
.mono { font-family: var(--font-mono); font-size: 12px; }

.table {
  padding: 8px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}

.row {
  display: grid;
  grid-template-columns: 32px repeat(auto-fit, minmax(120px, 1fr)) 90px 180px;
  gap: 6px;
  align-items: center;
  padding: 6px;
  border-radius: 6px;
}
.row + .row { margin-top: 4px; }
.row.head { background: #f8fafc; border: 1px solid var(--color-border-tertiary); }
.row:not(.head):hover { background: #fafbff; }

.c {
  min-width: 0;
}
.c-idx { text-align: center; }
.idx {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-text-secondary);
}
.c-status, .c-action { display: flex; gap: 4px; justify-content: center; }

.add-row {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 6px;
  padding: 10px;
  color: var(--color-text-secondary);
  font-size: 11px;
  background: #f8fafc;
  border: 1px dashed var(--color-border-tertiary);
  cursor: pointer;
}
.add-row:hover {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: var(--accent);
}

.preview {
  padding: 12px;
  margin: 0;
  max-height: 240px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.55;
  color: #cbd5e1;
  background: #0f172a;
  border-radius: 6px;
}
</style>
