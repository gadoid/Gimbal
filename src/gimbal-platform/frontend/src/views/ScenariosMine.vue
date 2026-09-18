<!-- ScenariosMine.vue — 场景库 / 我的场景(编排工作台)。
     原 Scenarios.vue「我的编排」tab 拆出独立页:表格只负责列表浏览、
     方案快速预览、次数/并发轻量即时调整;深度编辑跳方案管理。 -->
<template>
  <section class="slib">
    <PageHead
      icon="folder"
      title="我的场景"
      :subtitle="`共 ${rows.length} 个场景 · 你创建或拥有的编排`"
    />

    <div class="slib-toolbar">
      <input v-model="q" class="slib-search" data-testid="mine-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索" />
      <FilterPopover v-model="filters" :pool="filterableRows" />
      <button type="button" class="slib-create" data-testid="mine-create" @click="onCreate">+ 新建场景</button>
    </div>

    <div v-if="store.scenariosStatus === 'loading'" class="slib-loading">加载中…</div>

    <div v-else-if="paged.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>场景名</th>
            <th style="width:120px">系统</th>
            <th style="width:90px">模块</th>
            <th style="width:70px" class="c-center">优先级</th>
            <th style="width:60px" class="c-center">数据集</th>
            <th style="width:54px" class="c-center">步骤</th>
            <th style="width:54px" class="c-center">变量</th>
            <th style="width:100px">最后编辑</th>
            <th>Tags</th>
            <th style="width:56px" class="c-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in paged" :key="row.meta.scenarioId">
            <tr class="slib-row" :class="{ 'row-expired': row.meta.expire }" @click="openScenario(row)">
              <td>
                <div class="sl-name">
                  <StarToggle :starred="!!row.starred" @toggle="toggleStar(row)" />
                  <button type="button" class="nm" :title="row.meta.name || row.meta.scenarioId" @click.stop="openScenario(row)">
                    {{ row.meta.name || row.meta.scenarioId }}
                  </button>
                  <button
                    v-if="row.schemeCount"
                    type="button"
                    class="schemes-chip"
                    :class="{ open: expandedId === row.meta.scenarioId }"
                    :data-testid="`mine-schemes-${row.meta.scenarioId}`"
                    @click.stop="toggleExpand(row)"
                  >▾ {{ row.schemeCount }} 个方案</button>
                  <button v-else type="button" class="create-scheme-chip" @click.stop="goSchemes(row)">+ 创建方案</button>
                </div>
                <div class="sl-sid">{{ row.meta.scenarioId }}</div>
                <div v-if="row.meta.description" class="sl-desc">{{ row.meta.description }}</div>
              </td>
              <td><div class="sys-list"><SystemChip v-for="sys in row.meta.system" :key="sys" :sys="sys" /></div></td>
              <td><TagPill :label="row.meta.module || '未分类'" /></td>
              <td class="c-center"><PriorityPill :priority="row.meta.priority" /></td>
              <td class="c-center"><span class="num">{{ row.dataSetCount }}</span></td>
              <td class="c-center"><span class="num">{{ row.stepCount }}</span></td>
              <td class="c-center"><span class="num">{{ Object.keys(row.config?.vars || {}).length }}</span></td>
              <td><span class="muted">{{ formatTime(row.meta?.updateTime) }}</span></td>
              <td>
                <div v-if="row.tags.length" class="sys-list">
                  <TagPill v-for="t in row.tags.slice(0, MAX)" :key="t" :label="t" tone="accent" />
                  <TagPill v-if="row.tags.length > MAX" :label="`+${row.tags.length - MAX}`" />
                </div>
                <span v-else class="muted">—</span>
              </td>
              <td class="c-center">
                <DropdownMenu>
                  <DropdownMenuTrigger class="more-btn" @click.stop>⋯</DropdownMenuTrigger>
                  <DropdownMenuContent align="end" class="sl-menu">
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('detail', row)">查看详情</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('edit', row)">编辑场景</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="goSchemes(row)">方案管理</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('export', row)">导出 (JSON/YAML)</DropdownMenuItem>
                    <DropdownMenuItem v-if="row.visibility !== 'public'" class="sl-menu-item" @click="onCmd('publish', row)">发布到公共库</DropdownMenuItem>
                    <DropdownMenuItem v-else class="sl-menu-item" @click="onCmd('unpublish', row)">下架为私有</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item danger" @click="onCmd('delete', row)">删除</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </td>
            </tr>
            <tr v-if="expandedId === row.meta.scenarioId" class="scheme-panel-row" @click.stop>
              <td :colspan="10">
                <div v-if="schemesLoading" class="slib-loading">方案加载中…</div>
                <div v-else class="scheme-panel">
                  <SchemeCard
                    v-for="sc in visibleSchemes(row.meta.scenarioId)"
                    :key="sc.schemeId"
                    :scheme="sc"
                    :last-run="runs.lastRunOfScheme(row.meta.scenarioId, sc.schemeId)"
                    @run="runScheme(row, sc)"
                    @update="(_s, patch) => updateScheme(row, sc, patch)"
                  />
                  <router-link class="scheme-manage-tile" :to="scenarioSchemesUrl(row.meta.scenarioId)" @click.stop>
                    <span>→</span>
                    <span>方案管理</span>
                    <span v-if="overflowCount(row.meta.scenarioId)" class="more">还有 {{ overflowCount(row.meta.scenarioId) }} 个</span>
                  </router-link>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-else class="slib-empty">
      <p>暂无场景 — 新建第一个场景开始编排</p>
      <button type="button" class="slib-create" @click="onCreate">+ 新建场景</button>
    </div>

    <div v-if="total > pageSize" class="pager">
      <button type="button" class="pg-btn" :disabled="page <= 1" @click="page--">&#8249;</button>
      <button v-for="p in pageCount" :key="p" type="button" class="pg-btn" :class="{ active: p === page }" @click="page = p">{{ p }}</button>
      <button type="button" class="pg-btn" :disabled="page >= pageCount" @click="page++">&#8250;</button>
      <span class="pg-total">共 {{ total }} 条</span>
    </div>

    <p class="slib-note">
      「次数」「并发」是卡片底部两个独立的小徽章,平时只显示当前值,点一下变成可编辑输入框直接改数字;不需要额外弹一整层面板。更深的参数还是要进方案管理去改。方案卡片左上角的「默认」标记指这个场景的默认方案——关注页的执行健康趋势只统计默认方案的执行结果,不跨方案聚合。
    </p>

    <!-- 按方案导出选择器 -->
    <div v-if="exportPicker.open" class="exp-modal" data-testid="export-picker">
      <div class="exp-panel">
        <h4>导出场景 {{ exportPicker.scenarioName }}</h4>
        <p class="exp-hint">该场景存有运行方案 — 按方案导出会把方案的服务绑定物化进导出文件。</p>
        <label class="exp-opt">
          <input v-model="exportPicker.chosen" type="radio" value="" /> 默认导出(不套方案)
        </label>
        <label v-for="sc in exportPicker.schemes" :key="sc.name" class="exp-opt">
          <input v-model="exportPicker.chosen" type="radio" :value="sc.name" /> 按方案导出 · {{ sc.name }}
        </label>
        <div class="exp-foot">
          <button type="button" class="ghost-btn" @click="settleExportPicker(undefined)">取消</button>
          <button type="button" class="primary-btn" @click="confirmExportPicker">导出</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import {
  getScenarioDraft, listRunSchemes, updateRunScheme, runScenario, schemeToRunRequest,
  type SchemeV2, type RunOverlay,
} from '@/api/scenario-composer'
import { convertDraftToExecutable, schemeToOverlay } from '@/stores/scenario-draft'
import { downloadFile } from '@/utils/download'
import { useListSearch } from '@/utils/useListSearch'
import { confirmAction } from '@/utils/confirmAction'
import { composerUrl, scenarioDetailUrl, scenarioSchemesUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'
import { shortDateTime } from '@/utils/datetime'
import { applyFiltersToList, emptyFilters, type ScenarioFilters } from '@/utils/filters'
import { useScenarioRuns } from '@/composables/useScenarioRuns'
import { FOLLOW_CAP } from '@/composables/useFollowLayout'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import SchemeCard from '@/components/scenario-lib/SchemeCard.vue'
import FilterPopover from '@/components/FilterPopover.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import type { Scenario } from '@/types/scenario-composer'

const PREVIEW_MAX = 3
const MAX = 3
const pageSize = 20

const store = useScenarioComposerStore()
const router = useRouter()
const runs = useScenarioRuns()

const q = ref('')
const filters = ref<ScenarioFilters>(emptyFilters())
const page = ref(1)
const expandedId = ref<string | null>(null)
const schemesLoading = ref(false)
const schemesByScenario = reactive(new Map<string, SchemeV2[]>())

const { filtered } = useListSearch(
  () => store.scenarios,
  ['meta.name', 'meta.scenarioId', 'meta.module', 'meta.description', 'meta.system', 'tags'],
  q,
)

const filterableRows = computed(() =>
  filtered.value.map((s) => ({
    ...s,
    module: s.meta.module,
    author: s.meta.author || s.meta.owner,
    priority: s.meta.priority,
    updated_at: s.meta.updateTime,
    system: s.meta.system,
    tags: s.meta.tags,
  })),
)

// 我的场景 = 私有(自己的);公共场景在独立页。
const rows = computed(() =>
  (applyFiltersToList(filterableRows.value, filters.value) as typeof filterableRows.value)
    .filter((r) => r.visibility !== 'public'),
)
const total = computed(() => rows.value.length)
const pageCount = computed(() => Math.ceil(total.value / pageSize))
const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return rows.value.slice(start, start + pageSize)
})
watch(total, () => {
  const maxPage = Math.max(1, Math.ceil(total.value / pageSize))
  if (page.value > maxPage) page.value = maxPage
})

const formatTime = shortDateTime

onMounted(async () => {
  try {
    await store.fetchScenarios()
  } catch {
    showError('加载场景', undefined, store.lastError)
  }
})

function openScenario(row: Scenario) {
  router.push(composerUrl(row.meta.scenarioId))
}
function onCreate() {
  router.push('/composer/new?step=1')
}
function goSchemes(row: Scenario) {
  router.push(scenarioSchemesUrl(row.meta.scenarioId))
}

// ── 方案内联预览 ───────────────────────────────────────────────
async function toggleExpand(row: Scenario) {
  const id = row.meta.scenarioId
  if (expandedId.value === id) {
    expandedId.value = null
    return
  }
  expandedId.value = id
  if (schemesByScenario.has(id)) return
  schemesLoading.value = true
  try {
    const [schemes] = await Promise.all([listRunSchemes(id), runs.load(id)])
    schemesByScenario.set(id, schemes)
  } catch (e) {
    toast.error(`方案加载失败: ${(e as Error).message}`)
    schemesByScenario.set(id, [])
  } finally {
    schemesLoading.value = false
  }
}

function visibleSchemes(scenarioId: string): SchemeV2[] {
  return (schemesByScenario.get(scenarioId) || []).slice(0, PREVIEW_MAX)
}
function overflowCount(scenarioId: string): number {
  const n = (schemesByScenario.get(scenarioId) || []).length
  return n > PREVIEW_MAX ? n - PREVIEW_MAX : 0
}

async function updateScheme(row: Scenario, scheme: SchemeV2, patch: { nRuns?: number; parallel?: number }) {
  const id = row.meta.scenarioId
  try {
    const { schemeId, isDefault, ...rest } = { ...scheme, ...patch }
    await updateRunScheme(id, schemeId, rest)
    schemesByScenario.set(id, await listRunSchemes(id))
    toast.success(`已更新 ${scheme.name}`)
  } catch (e) {
    showError('更新方案', undefined, (e as Error).message)
  }
}

async function runScheme(row: Scenario, scheme: SchemeV2) {
  const id = row.meta.scenarioId
  try {
    const res = await runScenario(schemeToRunRequest(scheme, id))
    toast.success(`已发起执行 ${res.runId}`)
    runs.invalidate(id)
    await runs.load(id, true)
  } catch (e) {
    toast.error(`执行失败: ${(e as Error).message}`)
  }
}

// ── 关注(20 上限)─────────────────────────────────────────────
async function toggleStar(row: Scenario) {
  if (!row.starred && store.starredScenarios.length >= FOLLOW_CAP) {
    toast.error(`关注上限 ${FOLLOW_CAP} 个 — 请先在关注页取消部分关注`)
    return
  }
  try {
    await store.toggleStar(row.meta.scenarioId)
  } catch (e) {
    showError('关注', undefined, (e as Error).message)
  }
}

// ── 行级导出(沿用原 Scenarios 逻辑)───────────────────────────
const exportPicker = reactive<{
  open: boolean
  schemes: SchemeV2[]
  scenarioName: string
  chosen: string
  resolve: ((v: SchemeV2 | null | undefined) => void) | null
}>({ open: false, schemes: [], scenarioName: '', chosen: '', resolve: null })

function pickExportScheme(schemes: SchemeV2[], scenarioName: string): Promise<SchemeV2 | null | undefined> {
  exportPicker.schemes = schemes
  exportPicker.scenarioName = scenarioName
  exportPicker.chosen = ''
  exportPicker.open = true
  return new Promise((resolve) => { exportPicker.resolve = resolve })
}
function settleExportPicker(v: SchemeV2 | null | undefined) {
  exportPicker.open = false
  exportPicker.resolve?.(v)
  exportPicker.resolve = null
}
function confirmExportPicker() {
  const chosen = exportPicker.chosen
  settleExportPicker(chosen ? (exportPicker.schemes.find((s) => s.name === chosen) ?? null) : null)
}

async function exportRow(row: Scenario) {
  try {
    const draft = await getScenarioDraft(row.meta.scenarioId)
    let schemes: SchemeV2[] = []
    try {
      schemes = await listRunSchemes(row.meta.scenarioId)
    } catch { /* 非属主读不到方案 — 默认导出 */ }
    let overlay: RunOverlay | undefined
    if (schemes.length) {
      const picked = await pickExportScheme(schemes, row.meta.name || row.meta.scenarioId)
      if (picked === undefined) return
      if (picked) overlay = schemeToOverlay(picked)
    }
    const converted = await convertDraftToExecutable(draft, overlay)
    const filename = `${row.meta.scenarioId}-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`
    downloadFile(filename, JSON.stringify(converted, null, 2), 'application/json')
    toast.success(`已导出 ${filename}`)
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
  }
}

async function onCmd(cmd: string, row: Scenario) {
  if (cmd === 'detail') return router.push(scenarioDetailUrl(row.meta.scenarioId))
  if (cmd === 'edit') return openScenario(row)
  if (cmd === 'export') return exportRow(row)
  if (cmd === 'publish') {
    const ok = await confirmAction(
      `确认发布场景 ${row.meta.name || row.meta.scenarioId} 到公共库？发布后所有登录用户可见。`,
      '发布到公共库',
      { type: 'info', confirmButtonText: '发布', cancelButtonText: '取消' },
    )
    if (!ok) return
    try {
      await store.publishScenario(row.meta.scenarioId)
      toast.success('已发布')
    } catch (e) {
      showError('发布', undefined, (e as Error).message)
    }
    return
  }
  if (cmd === 'unpublish') {
    const ok = await confirmAction(
      `确认下架场景 ${row.meta.name || row.meta.scenarioId}？下架后仅自己可见,他人列表将立即移除。`,
      '下架为私有',
      { type: 'warning', confirmButtonText: '下架', cancelButtonText: '取消' },
    )
    if (!ok) return
    try {
      await store.unpublishScenario(row.meta.scenarioId)
      toast.success('已下架为私有')
    } catch (e) {
      showError('下架', undefined, (e as Error).message)
    }
    return
  }
  if (cmd === 'delete') {
    const ok = await confirmAction(
      `确认删除场景 ${row.meta.name || row.meta.scenarioId}？其下所有用例与数据集将一并删除，操作不可撤销。`,
      '删除场景',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    if (!ok) return
    try {
      await store.removeScenario(row.meta.scenarioId)
      toast.success(`已删除：${row.meta.name || row.meta.scenarioId}`)
    } catch (e) {
      showError('删除', undefined, (e as Error).message)
    }
  }
}
</script>

<style scoped>
.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
.row-expired td { opacity: 0.55; }
.pager { display: flex; justify-content: flex-end; align-items: center; margin-top: 12px; }
.pg-btn {
  min-width: 28px; height: 28px; margin-right: 4px;
  font-size: 12px; text-align: center;
  color: #374151; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 6px;
  cursor: pointer;
}
.pg-btn.active { color: #fff; background: #2f6fed; border-color: #2f6fed; font-weight: 600; }
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-total { font-size: 11.5px; color: #64748b; margin-left: 6px; }
.exp-modal {
  position: fixed; inset: 0; z-index: 2000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(16, 21, 28, 0.4);
}
.exp-panel {
  width: 440px; max-width: calc(100vw - 32px);
  padding: 18px 20px; background: #fff;
  border-radius: 10px; box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}
.exp-panel h4 { margin: 0 0 6px; font-size: 14px; }
.exp-hint { margin: 0 0 12px; font-size: 12px; color: #5a6273; }
.exp-opt { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 12.5px; cursor: pointer; }
.exp-opt input { accent-color: #2f6fed; }
.exp-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.ghost-btn {
  padding: 6px 14px; font-size: 12.5px; color: #5a6273;
  background: transparent; border: 1px solid #e1e5eb; border-radius: 8px; cursor: pointer;
}
.primary-btn {
  padding: 6px 16px; font-size: 12.5px; font-weight: 600; color: #fff;
  background: #2f6fed; border: none; border-radius: 8px; cursor: pointer;
}
.primary-btn:hover { background: #265fd4; }
</style>
