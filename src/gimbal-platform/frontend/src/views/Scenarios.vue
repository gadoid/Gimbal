<!-- Scenarios.vue — 场景库 v1
     场景 = 1:1 绑定用例的"结构定义层" · 与 cases 的关系是 scenario 1 → case 1 → dataSets N
     表格列对齐 pencil 原型：⭐ / 场景名 / 系统 / 模块 / 优先级 / 用例数 / 数据集数 / 步骤数 / 标签 / 更新时间
-->
<template>
  <section class="scenarios">
    <header class="page-header">
      <div>
        <h2>📚 场景库</h2>
        <p>共 {{ store.scenarios.length }} 个场景 · 1:1 绑定用例 · 1:N 数据集</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="q"
          class="search-input"
          clearable
          placeholder="🔍 按名 / 模块 / scenarioId / tag 搜索"
        />
        <FilterPopover
          v-model="filters"
          :pool="store.scenarios"
          show-system show-module show-priority
        />
        <!-- 平台侧始终持有的进行中草稿入口 (来自 CaseComposer) — 任意 step 都可触发 -->
        <ScenarioExportMenu variant="ghost" />
        <el-button type="primary" @click="onCreate">+ 新建场景</el-button>
      </div>
    </header>

    <!-- Tabs (PRD §6.1) -->
    <el-tabs v-model="activeTab" class="home-tabs">
      <el-tab-pane :label="`我的编排 (${myCount})`" name="mine" />
      <el-tab-pane :label="`公共编排 (${publicCount})`" name="public" />
      <el-tab-pane :label="`收藏 (${favoriteCount})`" name="favorite" />
    </el-tabs>

    <el-table
      v-if="visible.length > 0"
      v-loading="store.scenariosStatus === 'loading'"
      :data="visible"
      :row-key="rowKey"
      class="scenarios-table"
      @row-click="openScenario"
    >
      <el-table-column label="⭐" width="54" align="center">
        <template #default="{ row }">
          <button
            class="star-btn"
            :class="{ active: row.starred }"
            :aria-label="row.starred ? '取消收藏' : '收藏场景'"
            @click.stop="toggleStar(row)"
          >{{ row.starred ? '★' : '☆' }}</button>
        </template>
      </el-table-column>

      <el-table-column label="场景名" min-width="240">
        <template #default="{ row }">
          <button class="name" @click.stop="openScenario(row)">
            {{ row.meta.name || row.meta.scenarioId }}
          </button>
          <div class="sid">{{ row.meta.scenarioId }}</div>
          <div class="desc">{{ row.meta.description }}</div>
        </template>
      </el-table-column>

      <el-table-column label="系统" width="160">
        <template #default="{ row }">
          <div class="sys-list">
            <SystemChip
              v-for="s in row.meta.system"
              :key="s"
              :sys="s"
            />
          </div>
        </template>
      </el-table-column>

      <el-table-column label="模块" width="110">
        <template #default="{ row }">
          <TagPill :label="row.meta.module || '未分类'" />
        </template>
      </el-table-column>

      <el-table-column label="优先级" width="80" align="center">
        <template #default="{ row }">
          <PriorityPill :priority="row.meta.priority" />
        </template>
      </el-table-column>

      <el-table-column label="用例" width="62" align="center">
        <template #default="{ row }">
          <span class="num">{{ row.caseCount }}</span>
        </template>
      </el-table-column>

      <el-table-column label="数据集" width="70" align="center">
        <template #default="{ row }">
          <span class="num">{{ row.dataSetCount }}</span>
        </template>
      </el-table-column>

      <el-table-column label="步骤" width="62" align="center">
        <template #default="{ row }">
          <span class="num">{{ row.stepCount }}</span>
        </template>
      </el-table-column>

      <el-table-column label="变量" width="62" align="center">
        <template #default="{ row }">
          <span class="num">{{ (row.config?.vars || []).length }}</span>
        </template>
      </el-table-column>

      <el-table-column label="作者" width="90">
        <template #default="{ row }">
          <span class="muted">{{ row.meta.author || row.meta.owner || '—' }}</span>
        </template>
      </el-table-column>

      <el-table-column label="最后编辑" width="110">
        <template #default="{ row }">
          <span class="muted small">{{ formatTime(row.meta?.updateTime || row.scenario?.updateTime) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="Tags" min-width="180">
        <template #default="{ row }">
          <div v-if="row.tags.length" class="tag-list">
            <TagPill
              v-for="t in row.tags.slice(0, MAX)"
              :key="t"
              :label="t"
              tone="accent"
            />
            <TagPill
              v-if="row.tags.length > MAX"
              :label="`+${row.tags.length - MAX}`"
            />
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
                <el-dropdown-item command="edit">编辑场景</el-dropdown-item>
                <el-dropdown-item command="cases">查看用例</el-dropdown-item>
                <el-dropdown-item command="export" divided>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:4px"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  导出 (JSON/YAML)
                </el-dropdown-item>
                <el-dropdown-item command="clone">克隆为副本</el-dropdown-item>
                <el-dropdown-item command="delete" class="is-danger">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else-if="store.scenariosStatus !== 'loading'" description="暂无场景 — 新建第一个场景开始编排">
      <el-button type="primary" plain @click="onCreate">+ 新建场景</el-button>
    </el-empty>

    <div v-else class="loading-state"><el-skeleton :rows="5" animated /></div>

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
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { useListSearch } from '@/utils/useListSearch'
import { showError } from '@/utils/errorFallback'
import FilterPopover from '@/components/FilterPopover.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import ScenarioExportMenu from '@/components/ScenarioExportMenu.vue'
import { applyFiltersToList, emptyFilters, type CaseFilters } from '@/utils/filters'
import type { Scenario } from '@/types/scenario-composer'

const store = useScenarioComposerStore()
const router = useRouter()
const MAX = 3
const pageSize = 20

const q = ref('')
const filters = ref<CaseFilters>(emptyFilters())
const page = ref(1)
const activeTab = ref<'mine' | 'public' | 'favorite'>('mine')

const { filtered } = useListSearch(() => store.scenarios, [
  'meta.name',
  'meta.scenarioId',
  'meta.module',
  'meta.description',
  'tags',
])

const visible = computed(() =>
  applyFiltersToList(filtered.value, filters.value),
)

const total = computed(() => visible.value.length)

const myCount = computed(() => store.scenarios.filter(s => true).length)
const publicCount = computed(() => 0)  // v1: 暂未实现
const favoriteCount = computed(() => store.starredScenarios.length)

onMounted(async () => {
  try {
    await store.fetchScenarios()
  } catch {
    showError('加载场景', undefined, store.lastError)
  }
})

function rowKey(row: Scenario) { return row.meta.scenarioId }

function formatTime(t?: string | Date) {
  if (!t) return '—'
  const d = typeof t === 'string' ? new Date(t) : t
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function openScenario(row: Scenario) {
  // 跳转到新的统一 CaseComposer 页面 (从 ① 基本信息 开始)
  router.push(`/composer/${encodeURIComponent(row.meta.scenarioId)}?step=1`)
}

function onCreate() {
  router.push('/composer/new?step=1')
}

/** 行级导出 — 把已保存场景的整稿加载到 draft store,弹出菜单 */
const draftStore = useScenarioDraftStore()
const exportingRowId = ref<string | null>(null)
async function exportRow(row: Scenario) {
  exportingRowId.value = row.meta.scenarioId
  try {
    await draftStore.loadFromSaved(row.meta.scenarioId)
    // 复用 store 的 export 方法,直接弹下载 — 用户也可以再去 Scenarios 工具栏的"导出"按 JSON/YAML
    await draftStore.exportJson()
  } catch (e) {
    ElMessage.error(`加载草稿失败: ${(e as Error).message}`)
  } finally {
    exportingRowId.value = null
  }
}

async function toggleStar(row: Scenario) {
  try {
    await store.toggleStar(row.meta.scenarioId)
  } catch (e) {
    showError('收藏', undefined, (e as Error).message)
  }
}

async function onCmd(cmd: string, row: Scenario) {
  if (cmd === 'edit') return openScenario(row)
  if (cmd === 'cases') return router.push(`/scenarios/${row.meta.scenarioId}/cases`)
  if (cmd === 'clone') {
    ElMessage.info(`克隆 ${row.meta.scenarioId} (待后端支持)`)
    return
  }
  if (cmd === 'export') return exportRow(row)
  if (cmd === 'delete') {
    try {
      await store.removeScenario(row.meta.scenarioId)
      ElMessage.success(`已删除：${row.meta.scenarioId}`)
    } catch (e) {
      showError('删除', undefined, (e as Error).message)
    }
  }
}
</script>

<style scoped>
.home-tabs {
  margin-bottom: 8px;
}
.home-tabs :deep(.el-tabs__nav-wrap)::after { background: transparent; }
.home-tabs :deep(.el-tabs__item) {
  font-size: 14px; font-weight: 600; color: #5a6273;
  padding: 0 20px 12px;
}
.home-tabs :deep(.el-tabs__item.is-active) { color: #4f46e5; }
.home-tabs :deep(.el-tabs__active-bar) { background: #4f46e5; height: 2px; }

.scenarios {
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
.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.25;
}
.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.search-input { width: 280px; }

.scenarios-table {
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

.name {
  display: block;
  width: 100%;
  padding: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font: inherit;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
  text-overflow: ellipsis;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.name:hover { color: var(--accent); }

.sid {
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-tertiary);
}
.desc {
  margin-top: 2px;
  overflow: hidden;
  font-size: 11px;
  color: var(--color-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sys-list, .tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.num {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.muted { color: var(--color-text-secondary); font-size: 11px; }
.more-btn {
  padding: 3px 9px;
  font-size: 14px;
  color: #64748b;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 5px;
  cursor: pointer;
}
.more-btn:hover { color: var(--accent); border-color: var(--accent); }

.loading-state {
  padding: 28px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}

.pager { justify-content: flex-end; margin-top: 12px; }

:deep(.el-table th.el-table__cell) {
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  background: #f8fafc;
}
:deep(.el-table td.el-table__cell) { padding: 9px 0; font-size: 12px; }
:deep(.el-table__row:hover > td.el-table__cell) { background: var(--accent-soft) !important; }
:deep(.el-dropdown-menu__item) {
  padding: 8px 14px;
  font-size: 12px;
  text-align: left;
}
:deep(.el-dropdown-menu__item.is-danger) { color: #b91c1c; }

@media (max-width: 900px) {
  .scenarios { padding: 20px 16px 36px; }
  .page-header { flex-direction: column; align-items: flex-start; }
}
</style>
