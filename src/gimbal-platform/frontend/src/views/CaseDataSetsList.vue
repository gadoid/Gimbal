<!-- CaseDataSetsList.vue — 场景 · 测试数据页(spec v3 §5 同页双区)

     两区**各用其形**,因为它们是两类不同的东西:
       - 数据集 = 可打开、可编辑的资产(一组独立运行的字段值)→ 卡片网格,
         卡片回答"这组数据长什么样"(字段 + 该列前几行的取值)
       - 断言条目 = 一批字段齐整的配置记录(注入路径/注入值/绑定断言)
         → 紧凑表格,一行一条;一条一张卡会用画廊去装一张表

     数据源分离:
       - 数据集走 store(list 端 DataSetSummary,含 preview 前 3 行)
       - 断言条目走 GET /draft 自取数(与断言管理编辑器同源),draft 里
         同时取 definition.steps 喂判定面

     交互纪律:
       - 断言条目点击 → 跳断言管理编辑器(编辑入口在此页)
       - 悬空/旧版条目灰显不可执行,悬空判定与运行面板同口径
         (useInjectableSurface 的门控后死集)
-->
<template>
  <section class="ds-list">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>测试数据</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code></p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(composerUrl(scenarioId))">编排器</el-button>
        <el-button type="primary" @click="onCreate">+ 新建数据集</el-button>
      </div>
    </header>

    <!-- ── 区一:数据集(卡片网格)───────────────────────────── -->
    <section class="zone">
      <header class="zone-head">
        <h3 class="zone-name">数据集</h3>
        <span class="zone-count">{{ dataSets.length }}</span>
        <span class="zone-note">每组数据的每一行 = 一次独立运行</span>
      </header>

      <div v-loading="store.dataSetsStatus === 'loading'" class="grid">
        <article
          v-for="d in dataSets"
          :key="d.datasetId"
          class="card ds-card"
          @click="open(d)"
        >
          <header class="card-head">
            <h4 class="card-name">{{ d.name }}</h4>
            <span class="row-count">{{ d.rowCount }} 条</span>
          </header>

          <!-- 预览 = 列清单(转置):左列字段名定宽 ⇒ 无论多少列都对齐;
               右列该字段在前几行的取值,行数多于预览时尾缀 … -->
          <table v-if="previewCols(d).length" class="pv">
            <tbody>
              <tr v-for="c in previewCols(d)" :key="c">
                <th :title="c">{{ c }}</th>
                <td>{{ previewVals(d, c) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="pv-empty">还没有行数据</p>
          <p v-if="hiddenColCount(d)" class="pv-more">…另 {{ hiddenColCount(d) }} 个字段</p>

          <footer class="card-foot">
            <div class="ops" @click.stop>
              <el-button size="small" plain @click="open(d)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="remove(d)">删除</el-button>
              <el-button size="small" type="primary" plain @click="runDataset()"><el-icon style="margin-right:3px"><VideoPlay /></el-icon>运行</el-button>
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
    </section>

    <!-- ── 区二:断言条目(紧凑表格)─────────────────────────────
         一条一行:条目 / 步骤 / 注入路径 / 注入值 / 绑定断言 / 状态。
         旧版条目无 path(形状已退化)→ 三格填空;悬空与旧版都以
         「整行半透明 + 状态列标签」表达,不再各占一张卡。 -->
    <section class="zone">
      <header class="zone-head">
        <h3 class="zone-name">断言条目</h3>
        <span class="zone-count">{{ registry.entries.length }}</span>
        <span class="zone-note">注入路径 + 注入值 + 绑定断言 · 与数据集行交叉执行</span>
        <span class="zone-spacer"></span>
        <el-button :icon="Back" @click="router.push(scenarioAssertionsUrl(scenarioId))">管理断言</el-button>
      </header>

      <div v-if="registry.entries.length" class="atbl-wrap">
        <table class="atbl">
          <thead>
            <tr>
              <th>条目</th>
              <th class="col-step">步骤</th>
              <th>注入路径</th>
              <th>注入值</th>
              <th class="col-asserts">绑定断言</th>
              <th class="col-state">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="e in registry.entries"
              :key="e.id"
              class="atbl-row"
              :class="{ 'is-dead': isLegacyEntry(e) || deadOf(e) }"
              :title="isLegacyEntry(e) ? '旧版条目,请重建' : deadOf(e) ? '悬空条目 — 不可执行' : '点击编辑'"
              @click="openEntryEditor(e.id)"
            >
              <td class="nm">{{ e.name }}</td>
              <template v-if="isLegacyEntry(e)">
                <td class="dim">—</td>
                <td class="dim">旧版条目,请重建</td>
                <td class="dim">—</td>
              </template>
              <template v-else>
                <td class="mono">{{ e.path.stepIndex + 1 }}</td>
                <td class="mono pj">{{ e.path.jsonpath }}</td>
                <td class="mono vv">{{ valueSummary(e) }}</td>
              </template>
              <td class="num">{{ e.asserts?.length ?? 0 }} 条</td>
              <td>
                <span v-if="isLegacyEntry(e)" class="tag">旧版</span>
                <span v-else-if="deadOf(e)" class="tag warn">不进运行</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="atbl-empty">
        还没有断言条目 —
        <button class="linklike" @click="openEntryEditor()">去新建一条</button>
      </p>
    </section>

    <!-- 运行面板宿主(阶段③ v2):整库/单行预填已随 preset 退役
         (数据集勾选区移入方案工作台),入口保留为打开运行面板 -->
    <RunPanelHost v-if="panelOpen" :scenario-id="scenarioId" @close="panelOpen = false" />
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
import type { DataSetSummary } from '@/types/scenario-composer'
import { getScenarioDraft } from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { normalizeRegistry } from '@/utils/assertion-registry'
import { valueJson } from '@/utils/value-display'
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
/** 悬空判定薄壳(模板按布尔消费:class / title / 状态列) */
const deadOf = (e: AssertionRegistry['entries'][number]) =>
  surface.deadIds.value.includes(e.id)
function valueSummary(e: AssertionRegistry['entries'][number]): string {
  if (isLegacyEntry(e)) return '—'
  const v = (e as { value: unknown }).value
  if (v === null || v === undefined) return '—'
  return valueJson(v)   // 容器紧凑 JSON / 标量原样(value-display 共享收口)
}

// ── 数据集卡片预览(列清单)──────────────────────────────────
/** 预览列上限:再多卡片会被撑高,尾部收成「…另 N 个字段」 */
const MAX_PREVIEW_COLS = 4
/** 预览列 = 首个预览行的键序,截到上限(无预览行 = 无列) */
function previewCols(d: DataSetSummary): string[] {
  const first = d.preview?.[0]
  return first ? Object.keys(first).slice(0, MAX_PREVIEW_COLS) : []
}
function hiddenColCount(d: DataSetSummary): number {
  const first = d.preview?.[0]
  return first ? Math.max(0, Object.keys(first).length - MAX_PREVIEW_COLS) : 0
}
/** 该列在预览行里的取值,` · ` 连接;行数多于预览行数时尾缀 `…`
 *  (后端 preview 上限 3 行,rowCount 是整库行数) */
function previewVals(d: DataSetSummary, col: string): string {
  const vals = d.preview.map((r) => (r[col] === undefined ? '' : String(r[col])))
  return vals.join(' · ') + (d.rowCount > vals.length ? ' …' : '')
}

// ── 运行面板(spec v3 §6 数据集入口;阶段③:预填退役,保留打开面板)──
const panelOpen = ref(false)

/** 数据集卡「运行」(阶段③ v2:无整库预填 — 数据集勾选区移入方案工作台;
 *  行级在 DataSetEditor「运行」同款退役) */
function runDataset() {
  panelOpen.value = true
}
/** 点某一行 ⇒ 编辑器「聚焦单条」;不给 id(空列表的「去新建一条」、
 *  区标题的「管理断言」)⇒ 全量视图 */
function openEntryEditor(entryId?: string) {
  router.push(scenarioAssertionsUrl(scenarioId, entryId))
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
  margin-bottom: 6px;
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

/* ── 区(两区共用同一套标题语言,形状各自不同)───────────── */
.zone { margin-top: 26px; }
.zone-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.zone-name {
  margin: 0;
  padding-left: 10px;
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text-primary);
  border-left: 3px solid var(--accent);
}
.zone-count {
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 3px;
}
.zone-note { font-size: 11px; color: var(--color-text-tertiary); }
.zone-spacer { flex: 1; }

/* ── 数据集卡片网格 ─────────────────────────────────────── */
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
.card-name { margin: 0; font-size: 13px; font-weight: 700; }
.row-count {
  padding: 1px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 3px;
  white-space: nowrap;
}

/* 预览 = 列清单:左列定宽(字段名),右列该字段的取值样本 */
.pv { width: 100%; border-collapse: collapse; }
.pv th {
  width: 84px;
  padding: 3px 10px 3px 0;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  text-align: left;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}
.pv td {
  padding: 3px 0;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-secondary);
  word-break: break-word;
}
.pv-empty {
  margin: 2px 0;
  font-size: 11px;
  font-style: italic;
  color: var(--color-text-tertiary);
}
.pv-more {
  margin: 4px 0 0;
  font-size: 10.5px;
  color: var(--color-text-tertiary);
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

/* ── 断言条目表格 ───────────────────────────────────────── */
.atbl-wrap {
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.atbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.atbl th {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-align: left;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border-tertiary);
  white-space: nowrap;
}
.atbl td {
  padding: 8px 12px;
  color: var(--color-text-primary);
  border-bottom: 1px solid #f1f5f9;
}
.atbl tr:last-child td { border-bottom: none; }
.atbl .col-step { width: 56px; }
.atbl .col-asserts { width: 84px; }
.atbl .col-state { width: 90px; }

.atbl-row { cursor: pointer; }
.atbl-row:hover td { background: #f8faff; }
.atbl-row.is-dead { opacity: 0.55; }

.atbl .nm { font-weight: 600; }
.atbl .mono { font-family: var(--font-mono); }
.atbl .pj { color: var(--accent); word-break: break-all; }
.atbl .vv { color: var(--color-text-secondary); word-break: break-all; }
.atbl .dim { color: var(--color-text-tertiary); }
.atbl .num { color: var(--color-text-secondary); white-space: nowrap; }

.tag {
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 3px;
  white-space: nowrap;
}
.tag.warn { color: #b45309; background: #fef3c7; }

.atbl-empty {
  margin: 0;
  padding: 22px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  text-align: center;
  background: #fff;
  border: 1px dashed var(--color-border-tertiary);
  border-radius: 8px;
}
.linklike {
  padding: 0;
  font: inherit;
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}
</style>
