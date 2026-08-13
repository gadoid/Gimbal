<!-- Cases.vue — 全部用例跨场景总览
     表格列：⭐ / 用例名 / 场景 / 系统 / 模块 / 优先级 / 认证 / 环境 / 数据集数 / 创建人 / 最后运行
-->
<template>
  <section class="cases-all">
    <header class="page-header">
      <div>
        <h2>📋 全部用例</h2>
        <p>共 {{ store.cases.length }} 条 · 跨 {{ scenarioCount }} 个场景 · 1:1 绑定 / 1:N 数据集</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="q"
          class="search-input"
          clearable
          placeholder="🔍 按名 / 场景 / 标签"
        />
        <FilterPopover v-model="filters" :pool="store.cases" show-system show-module />
        <el-button type="primary" @click="router.push('/scenarios')">从场景新建</el-button>
      </div>
    </header>

    <el-table
      v-if="visible.length > 0"
      v-loading="store.casesStatus === 'loading'"
      :data="visible"
      :row-key="rowKey"
      class="case-table"
      @row-click="openCase"
    >
      <el-table-column label="⭐" width="54" align="center">
        <template #default="{ row }">
          <button
            class="star-btn"
            :class="{ active: row.starred }"
            @click.stop="toggleStar(row)"
          >{{ row.starred ? '★' : '☆' }}</button>
        </template>
      </el-table-column>

      <el-table-column label="用例名" min-width="220">
        <template #default="{ row }">
          <button class="cname" @click.stop="openCase(row)">{{ row.name }}</button>
          <div class="cid">{{ row.caseId }}</div>
        </template>
      </el-table-column>

      <el-table-column label="场景" width="180">
        <template #default="{ row }">
          <button class="sid-link" @click.stop="goScenario(row.scenarioId)">
            {{ row.scenarioId }}
          </button>
        </template>
      </el-table-column>

      <el-table-column label="系统" width="140">
        <template #default="{ row }">
          <div class="sys-list">
            <SystemChip
              v-for="s in systemsOf(row.scenarioId)"
              :key="s"
              :sys="s"
            />
          </div>
        </template>
      </el-table-column>

      <el-table-column label="模块" width="100">
        <template #default="{ row }">
          <TagPill :label="moduleOf(row.scenarioId)" />
        </template>
      </el-table-column>

      <el-table-column label="优先级" width="80" align="center">
        <template #default="{ row }">
          <PriorityPill :priority="priorityOf(row.scenarioId)" />
        </template>
      </el-table-column>

      <el-table-column label="认证" width="100">
        <template #default="{ row }">
          <span class="mono">{{ row.auth.name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="环境" width="100">
        <template #default="{ row }">
          <span class="mono">{{ row.env }}</span>
        </template>
      </el-table-column>

      <el-table-column label="数据集" width="74" align="center">
        <template #default="{ row }">
          <span class="num">{{ row.dataSetIds.length }}</span>
        </template>
      </el-table-column>

      <el-table-column label="创建人" width="86">
        <template #default="{ row }">
          <span class="muted">{{ row.createdBy }}</span>
        </template>
      </el-table-column>

      <el-table-column label="最后运行" width="140">
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

    <el-empty v-else-if="store.casesStatus !== 'loading'" description="暂无用例 · 从场景新建第一个">
      <el-button type="primary" plain @click="router.push('/scenarios')">前往场景库</el-button>
    </el-empty>

    <el-pagination
      v-if="total > pageSize"
      class="pager"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next, total"
      background
      @current-change="(p) => (page = p)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import FilterPopover from '@/components/FilterPopover.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useListSearch } from '@/utils/useListSearch'
import { applyFiltersToList, emptyFilters, type CaseFilters } from '@/utils/filters'
import { showError } from '@/utils/errorFallback'
import type { Case } from '@/types/scenario-composer'

const store = useScenarioComposerStore()
const router = useRouter()
const pageSize = 20

const q = ref('')
const filters = ref<CaseFilters>(emptyFilters())
const page = ref(1)

const { filtered } = useListSearch(() => store.cases, [
  'name', 'caseId', 'scenarioId',
])

const visible = computed(() => applyFiltersToList(filtered.value, filters.value))
const total = computed(() => visible.value.length)

const scenarioCount = computed(() => {
  const set = new Set(store.cases.map((c) => c.scenarioId))
  return set.size
})

function systemsOf(scenarioId: string) {
  return store.scenarioById(scenarioId)?.meta.system ?? []
}
function moduleOf(scenarioId: string) {
  return store.scenarioById(scenarioId)?.meta.module ?? '未分类'
}
function priorityOf(scenarioId: string) {
  return store.scenarioById(scenarioId)?.meta.priority ?? null
}

onMounted(async () => {
  try {
    if (!store.scenarios.length) await store.fetchScenarios()
    await store.fetchCases()
  } catch (e) {
    showError('加载用例', undefined, (e as Error).message)
  }
})

function rowKey(c: Case) { return c.caseId }

function openCase(c: Case) {
  router.push(`/cases/${encodeURIComponent(c.caseId)}/edit`)
}

function goScenario(scenarioId: string) {
  router.push(`/scenarios/${scenarioId}/edit`)
}

function toggleStar(c: Case) {
  ElMessage.info(`收藏用例 ${c.caseId} (待 store 支持)`)
}

async function onCmd(cmd: string, row: Case) {
  if (cmd === 'edit')     return openCase(row)
  if (cmd === 'datasets') return router.push(`/cases/${row.caseId}/data-sets`)
  if (cmd === 'run')      return router.push(`/cases/${row.caseId}/run`)
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
.cases-all {
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
.header-actions { display: flex; gap: 8px; align-items: center; }
.search-input { width: 280px; }

.case-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  cursor: pointer;
}

.star-btn {
  padding: 2px;
  font-size: 19px;
  line-height: 1;
  color: #cbd5e1;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.star-btn.active { color: #d97706; }

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
.sid-link {
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent);
  background: transparent;
  border: 0;
  border-radius: 3px;
  cursor: pointer;
}
.sid-link:hover { background: var(--accent-soft); }

.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
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

.pager { justify-content: flex-end; margin-top: 12px; }

:deep(.el-table th.el-table__cell) {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  background: #f8fafc;
}
:deep(.el-table td.el-table__cell) { padding: 9px 0; font-size: 12px; }
:deep(.el-table__row:hover > td.el-table__cell) { background: var(--accent-soft) !important; }
:deep(.el-dropdown-menu__item.is-danger) { color: #b91c1c; }
</style>
