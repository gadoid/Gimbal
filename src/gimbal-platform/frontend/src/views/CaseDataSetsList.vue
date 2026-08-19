<!-- CaseDataSetsList.vue — 用例 · ④ 数据集列表
     卡片网格：每个数据集 = 一组独立运行的字段值
     卡片显示：名称 / 行数 / 预览前 3 行 / 最近运行 / 单条运行入口
-->
<template>
  <section class="ds-list">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>数据集列表</h2>
        <p>用例 <code class="sid">{{ caseId }}</code> · 共 {{ dataSets.length }} 个数据集 · 1 : N</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(caseViewUrl(caseId))">用例详情</el-button>
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
          <StatusBadge v-if="d.lastRunStatus" :status="d.lastRunStatus" />
        </header>

        <p v-if="d.preview.length" class="preview">
          {{ previewLabel(d.preview) }}
        </p>
        <p v-else class="preview empty">还没有行数据</p>

        <footer class="card-foot">
          <span class="last-run">
            最近 · {{ d.lastRunAt ? relTime(d.lastRunAt) : '从未运行' }}
          </span>
          <div class="ops" @click.stop>
            <el-button size="small" plain @click="copy(d)">复制</el-button>
            <el-button size="small" type="primary" plain @click="runOne(d)"><el-icon style="margin-right:3px"><VideoPlay /></el-icon>单条</el-button>
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
      description="此用例还没有数据集 · 新建数据集开始数据驱动"
    >
      <el-button type="primary" plain @click="onCreate">+ 新建数据集</el-button>
    </el-empty>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Back, DataAnalysis, VideoPlay } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { caseViewUrl, caseDataSetUrl, composerUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'
import type { DataSetSummary } from '@/types/scenario-composer'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const caseId = route.params.caseId as string

const dataSets = computed(() => store.dataSetsOfCase(caseId))

onMounted(async () => {
  try {
    await store.fetchDataSets(caseId)
  } catch (e) {
    showError('加载数据集', undefined, (e as Error).message)
  }
})

function open(d: DataSetSummary) {
  router.push(caseDataSetUrl(caseId, d.datasetId))
}

function onCreate() {
  router.push(caseDataSetUrl(caseId, 'new'))
}

async function copy(d: DataSetSummary) {
  ElMessage.info(`复制 ${d.name} (待后端支持)`)
}

/** 运行统一走编排器的 RunDialog(可在其中勾选该数据集发起运行) */
async function runOne(_d: DataSetSummary) {
  let c = store.caseById(caseId)
  if (!c) {
    try { await store.fetchCases() } catch { /* 忽略,回退到详情页 */ }
    c = store.caseById(caseId)
  }
  if (c?.scenarioId) router.push(composerUrl(c.scenarioId))
  else router.push(caseViewUrl(caseId))
}

function previewLabel(rows: Record<string, any>[]) {
  const cols = Object.keys(rows[0] ?? {})
  const head = cols.slice(0, 3).join('  ')
  const tail = rows.slice(0, 3).map((r) =>
    cols.slice(0, 3).map((c) => String(r[c])).join('  '),
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
.last-run { font-size: 11px; color: var(--color-text-secondary); }
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
</style>
