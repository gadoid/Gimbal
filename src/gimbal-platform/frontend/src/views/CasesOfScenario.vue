<!-- CasesOfScenario.vue — 场景编辑 · ③ 用例管理
     列出某个场景下的所有用例 (1:1 绑定)。
     顶部摘要 banner + 1:1 徽章 + 用例表格 + 新建按钮
-->
<template>
  <section class="cases-of">
    <header class="page-header">
      <div>
        <h2>📚 场景编辑 · {{ scenario?.meta.name || scenarioId }}</h2>
        <p>{{ scenarioId }} · ③ 用例管理</p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push(`/scenarios/${scenarioId}/steps`)">← ② 步骤编排</el-button>
        <el-button type="primary" @click="onCreateCase">+ 新建用例</el-button>
      </div>
    </header>

    <HeadStepper :steps="steps" :active-index="2" />

    <!-- 摘要 banner -->
    <div v-if="scenario" class="summary-banner">
      <div class="left">
        <h3>{{ scenario.meta.name }}</h3>
        <div class="sid">{{ scenario.meta.scenarioId }}</div>
        <div class="desc">{{ scenario.meta.description }}</div>
      </div>
      <div class="right">
        <div class="metric">
          <span class="num">{{ caseList.length }}</span>
          <span class="lbl">绑定用例</span>
          <span class="badge">1 : 1</span>
        </div>
        <div class="metric">
          <span class="num">{{ totalDataSets }}</span>
          <span class="lbl">数据集总数</span>
          <span class="badge">1 : N</span>
        </div>
        <div class="metric">
          <span class="num">{{ scenario.stepCount }}</span>
          <span class="lbl">步骤数</span>
        </div>
      </div>
    </div>

    <h3 style="margin: 18px 0 8px; font-size: 13px;">用例列表</h3>

    <el-table
      v-loading="store.casesStatus === 'loading'"
      :data="caseList"
      :row-key="rowKey"
      class="case-table"
      @row-click="openCase"
    >
      <el-table-column label="用例名" min-width="220">
        <template #default="{ row }">
          <button class="cname" @click.stop="openCase(row)">{{ row.name }}</button>
          <div class="cid">{{ row.caseId }}</div>
        </template>
      </el-table-column>

      <el-table-column label="优先级" width="80" align="center">
        <template #default="{ row }">
          <PriorityPill :priority="scenario?.meta.priority ?? null" />
        </template>
      </el-table-column>

      <el-table-column label="认证" width="120">
        <template #default="{ row }">
          <span class="mono">{{ row.auth.name }}</span>
          <span class="muted">· {{ row.auth.type }}</span>
        </template>
      </el-table-column>

      <el-table-column label="环境" width="110">
        <template #default="{ row }">
          <span class="mono">{{ row.env }}</span>
        </template>
      </el-table-column>

      <el-table-column label="数据集" width="90" align="center">
        <template #default="{ row }">
          <span class="num">{{ row.dataSetIds.length }}</span>
        </template>
      </el-table-column>

      <el-table-column label="创建人" width="90">
        <template #default="{ row }">
          <span class="muted">{{ row.createdBy }}</span>
        </template>
      </el-table-column>

      <el-table-column label="最后运行" width="130">
        <template #default="{ row }">
          <div v-if="row.lastRunStatus" class="run-cell">
            <StatusBadge :status="row.lastRunStatus" />
            <span class="muted small">{{ relTime(row.lastRunAt) }}</span>
          </div>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(c) => onCmd(c, row)">
            <button class="more-btn" @click.stop>⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="datasets">数据集</el-dropdown-item>
                <el-dropdown-item command="run">运行</el-dropdown-item>
                <el-dropdown-item divided command="delete" class="is-danger">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="caseList.length === 0 && store.casesStatus !== 'loading'"
      description="此场景还没有用例 · 点击右上角 + 新建用例"
    >
      <el-button type="primary" plain @click="onCreateCase">+ 新建用例</el-button>
    </el-empty>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import HeadStepper from '@/components/HeadStepper.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import type { Case } from '@/types/scenario-composer'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string

const steps = [
  { key: 'meta',  label: '① 基本信息', to: `/scenarios/${scenarioId}/edit` as RouteLocationRaw },
  { key: 'steps', label: '② 步骤编排', to: `/scenarios/${scenarioId}/steps` as RouteLocationRaw },
  { key: 'cases', label: '③ 用例管理', to: '' as RouteLocationRaw },
  { key: 'data',  label: '④ 数据集',   to: `/scenarios/${scenarioId}/data-sets` as RouteLocationRaw },
]

const scenario = computed(() => store.scenarioById(scenarioId))
const caseList = computed(() => store.casesOfScenario(scenarioId))
const totalDataSets = computed(() =>
  caseList.value.reduce((sum, c) => sum + c.dataSetIds.length, 0),
)

onMounted(async () => {
  try {
    if (!scenario.value) await store.fetchScenarios()
    await store.fetchCases({ scenarioId })
  } catch (e) {
    showError('加载用例', undefined, (e as Error).message)
  }
})

function rowKey(c: Case) { return c.caseId }

function openCase(c: Case) {
  router.push(`/cases/${encodeURIComponent(c.caseId)}/edit`)
}

function onCreateCase() {
  router.push(`/cases/new/edit?scenarioId=${encodeURIComponent(scenarioId)}`)
}

async function onCmd(cmd: string, row: Case) {
  if (cmd === 'edit')   return openCase(row)
  if (cmd === 'datasets') return router.push(`/cases/${row.caseId}/data-sets`)
  if (cmd === 'run')    return router.push(`/cases/${row.caseId}/run`)
  if (cmd === 'delete') {
    try {
      await store.removeCase(row.caseId)
      ElMessage.success(`已删除：${row.caseId}`)
    } catch (e) {
      showError('删除', undefined, (e as Error).message)
    }
  }
}

function relTime(v?: string) {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}m 前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h 前`
  return `${Math.floor(hr / 24)}d 前`
}
</script>

<style scoped>
.cases-of {
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
.header-actions { display: flex; gap: 8px; }

.summary-banner {
  display: flex;
  gap: 24px;
  align-items: stretch;
  justify-content: space-between;
  margin-top: 16px;
  padding: 18px 20px;
  background: linear-gradient(180deg, var(--accent-soft) 0%, #fff 100%);
  border: 1px solid var(--accent-soft-border);
  border-radius: 8px;
}
.summary-banner .left { flex: 1; min-width: 0; }
.summary-banner h3 { margin: 0; font-size: 16px; font-weight: 700; }
.summary-banner .sid {
  margin: 4px 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent);
}
.summary-banner .desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.summary-banner .right {
  display: flex;
  gap: 16px;
  align-items: center;
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
  padding: 8px 16px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.metric .num {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
}
.metric .lbl {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.metric .badge {
  margin-top: 2px;
  padding: 1px 6px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  color: #fff;
  background: var(--accent);
  border-radius: 10px;
}

.case-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  cursor: pointer;
}
.cname {
  display: block;
  padding: 0;
  font: inherit;
  font-weight: 600;
  text-align: left;
  color: var(--color-text-primary);
  background: transparent;
  border: 0;
  cursor: pointer;
}
.cname:hover { color: var(--accent); }
.cid {
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-tertiary);
}
.mono { font-family: var(--font-mono); font-size: 11px; }
.num  { font-family: var(--font-mono); font-weight: 700; }
.muted { color: var(--color-text-secondary); font-size: 11px; }
.muted.small { font-size: 10px; margin-left: 4px; }
.run-cell { display: flex; gap: 4px; align-items: center; }
.more-btn {
  padding: 3px 9px;
  font-size: 14px;
  color: #64748b;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 5px;
  cursor: pointer;
}

:deep(.el-table th.el-table__cell) {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  background: #f8fafc;
}
:deep(.el-table td.el-table__cell) { padding: 9px 0; font-size: 12px; }
:deep(.el-table__row:hover > td.el-table__cell) { background: var(--accent-soft) !important; }
:deep(.el-dropdown-menu__item.is-danger) { color: #b91c1c; }

@media (max-width: 900px) {
  .summary-banner { flex-direction: column; }
}
</style>
