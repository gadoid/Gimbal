<!-- CaseDataSetsList.vue — 场景 · 数据集列表
     卡片网格：每个数据集 = 一组独立运行的字段值
     卡片显示：名称 / 行数 / 预览前 3 行 / 最近运行 / 单条运行入口
-->
<template>
  <section class="ds-list">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>测试数据</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code> · {{ dataSets.length }} 数据集 · {{ registry.entries.length }} 断言条目</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(composerUrl(scenarioId))">编排器</el-button>
        <el-button type="primary" @click="onCreate">+ 新建数据集</el-button>
      </div>
    </header>

    <div v-loading="store.dataSetsStatus === 'loading'" class="grid">
      <article
        v-for="d in dataSets"
        :key="d.datasetId"
        class="card"
        @click="open(d)"
      >
        <header class="card-head">
          <div class="title">
            <h3>{{ d.name }}</h3>
            <span class="row-count">{{ d.rowCount }} 条记录</span>
          </div>
        </header>

        <p v-if="d.preview.length" class="preview">
          {{ previewLabel(d.preview) }}
        </p>
        <p v-else class="preview empty">还没有行数据</p>

        <footer class="card-foot">
          <div class="ops" @click.stop>
            <el-button size="small" plain @click="open(d)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="remove(d)">删除</el-button>
            <el-button size="small" type="primary" plain @click="runDataset(d)"><el-icon style="margin-right:3px"><VideoPlay /></el-icon>运行</el-button>
          </div>
        </footer>
      </article>

      <article class="card add-card" @click="onCreate">
        <div class="add-icon">+</div>
        <div class="add-text">新建数据集</div>
      </article>
    </div>

    <el-empty
      v-if="dataSets.length === 0 && store.dataSetsStatus !== 'loading'"
      description="此场景还没有数据集 · 新建数据集开始数据驱动"
    >
      <el-button type="primary" plain @click="onCreate">+ 新建数据集</el-button>
    </el-empty>

    <!-- 断言条目网格(spec v3 §5):同页双区第二区 — 编辑入口(点击跳
         断言管理编辑器);旧版条目灰显不可执行(保留原样不删) -->
    <section class="td-entries">
      <header class="page-header">
        <div>
          <h2 class="page-title sub">断言条目(偏离注入)</h2>
          <p>{{ registry.entries.length }} 条 · 定位 path + 偏离值 + 期望配对 · 与数据集行交叉执行</p>
        </div>
        <div class="header-actions">
          <el-button :icon="Back" @click="router.push(scenarioAssertionsUrl(scenarioId))">管理断言</el-button>
        </div>
      </header>
      <div class="grid">
        <article
          v-for="e in registry.entries"
          :key="e.id"
          class="card td-entry"
          :class="{ 'is-dead': isLegacyEntry(e) || deadOf(e) }"
          :title="isLegacyEntry(e) ? '旧版条目,请重建' : deadOf(e) ? '悬空条目 — 不可执行' : '点击编辑'"
          @click="openEntryEditor()"
        >
          <header class="card-head">
            <div class="title">
              <h3>{{ e.name }}</h3>
              <span v-if="!isLegacyEntry(e)" class="row-count">步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}</span>
              <span v-else class="row-count">旧版条目,请重建</span>
            </div>
          </header>
          <p class="preview">{{ valueSummary(e) }}</p>
          <footer class="card-foot">
            <div class="ops" @click.stop>
              <span class="row-count">{{ e.asserts?.length ?? 0 }} 期望</span>
              <span v-if="isLegacyEntry(e)" class="row-count">旧版</span>
              <span v-else-if="deadOf(e)" class="row-count">悬空</span>
            </div>
          </footer>
        </article>
        <article class="card add-card" @click="openEntryEditor()">
          <div class="add-icon">+</div>
          <div class="add-text">新建断言条目</div>
        </article>
      </div>
    </section>

    <!-- 运行面板宿主(spec v3 §6 数据集入口):整库/单行预填 -->
    <RunPanelHost v-if="panelOpen" :scenario-id="scenarioId" :preset="panelPreset" @close="panelOpen = false" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Back, DataAnalysis, VideoPlay } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { scenarioDataSetUrl, composerUrl, scenarioAssertionsUrl } from '@/utils/links'
import type { DataSetRow, DataSetSummary } from '@/types/scenario-composer'
import { getScenarioDraft } from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import type { RunPreset } from '@/api/scenario-composer'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { normalizeRegistry } from '@/utils/assertion-registry'
import { useInjectableSurface } from '@/composables/useInjectableSurface'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string

const dataSets = computed(() => store.dataSetsOfScenario(scenarioId))

// ── 断言条目区(spec v3 §5):draft 自取数(与编辑器同源)────────────
const registry = ref<AssertionRegistry>({ entries: [] })
const steps = ref<any[]>([])
/** 判定面(spec 架构收敛 §2.1):唯一消费面。本页只做展示(悬空灰显),
 *  与运行面板同口径 —— 读 composable 的**门控后死集**:契约未落定期间
 *  不把契约依赖条目标成悬空(它们不是"悬空",是"还没答案")。 */
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())
/** 悬空判定薄壳(模板按布尔消费:class / title / 摘要行) */
const deadOf = (e: AssertionRegistry['entries'][number]) =>
  surface.deadIds.value.includes(e.id)
function valueSummary(e: AssertionRegistry['entries'][number]): string {
  if (isLegacyEntry(e)) return '—'
  const v = (e as { value: unknown }).value
  if (v === null || v === undefined) return '—'
  return typeof v === 'string' ? v : JSON.stringify(v)
}

// ── 运行面板(spec v3 §6 数据集入口):preset 预填 ──────────────────
const panelOpen = ref(false)
const panelPreset = ref<RunPreset | null>(null)

/** 数据集卡「运行」:整库单选预填(行级在 DataSetEditor「运行此行」)*/
function runDataset(d: DataSetSummary) {
  panelPreset.value = { dataSetSelection: [{ datasetId: d.datasetId }] }
  panelOpen.value = true
}
function openEntryEditor() {
  router.push(scenarioAssertionsUrl(scenarioId))
}

onMounted(async () => {
  try {
    await store.fetchDataSets(scenarioId)
  } catch (e) {
    showError('加载数据集', e)
  }
  try {
    const draft = await getScenarioDraft(scenarioId)
    registry.value = normalizeRegistry(draft.assertion_registry)
    steps.value = (draft.definition.steps ?? []) as any[]
  } catch (e) {
    showError('加载断言条目', e)
  }
})

function open(d: DataSetSummary) {
  router.push(scenarioDataSetUrl(scenarioId, d.datasetId))
}

function onCreate() {
  router.push(scenarioDataSetUrl(scenarioId, 'new'))
}

async function remove(d: DataSetSummary) {
  const ok = await confirmAction(
    `删除数据集「${d.name}」?此操作不可恢复。`, '删除数据集',
    { confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await store.removeDataSet(scenarioId, d.datasetId)
    ElMessage.success('已删除')
  } catch (e) {
    showError('删除数据集', e)
  }
}

/** 把首 3 行的首 3 列拼成预览文案。模板层 `v-if="d.preview.length"` 已守卫,
 *  此处不再做空检查(死分支,且多一层模板拼字符串的浪费)。 */
function previewLabel(rows: DataSetRow[]) {
  const cols = Object.keys(rows[0])
  const head = cols.slice(0, 3).join('  ')
  const tail = rows.slice(0, 3).map((r) =>
    cols.slice(0, 3).map((c) => r[c] === undefined ? '' : String(r[c])).join('  '),
  ).join(' / ')
  return `${head}\n${tail}`
}
</script>

<style scoped>
.ds-list {
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

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.card {
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
}
.card:hover {
  border-color: var(--accent);
  box-shadow: 0 1px 6px rgba(67, 56, 202, 0.12);
}

.card-head {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.title h3 { margin: 0; font-size: 13px; font-weight: 700; }
.row-count {
  margin-left: 6px;
  padding: 1px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 3px;
}

.preview {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  margin: 8px 0;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.55;
  color: var(--color-text-secondary);
  white-space: pre;
  text-overflow: ellipsis;
}
.preview.empty {
  color: var(--color-text-tertiary);
  font-style: italic;
}

.card-foot {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-tertiary);
}
.ops { display: flex; gap: 6px; }

.add-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  background: #fafbff;
  border: 1px dashed var(--accent-soft-border);
}
.add-card:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}
.add-icon {
  font-size: 32px;
  font-weight: 300;
  color: var(--accent);
}
.add-text { font-size: 12px; color: var(--accent); }

/* 断言条目区(spec v3 §5):同页双区第二区 */
.td-entries { margin-top: 28px; }
.card.td-entry.is-dead { opacity: .55; }
.page-title.sub { font-size: 16px; }
</style>
