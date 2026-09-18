<!-- Scenarios.vue — 场景库 v1
     场景即执行主体(Case 层已解散)· 与数据集的关系是 scenario 1 → dataSets N
     表格列对齐 pencil 原型：收藏 / 场景名 / 系统 / 模块 / 优先级 / 数据集数 / 步骤数 / 标签 / 更新时间
-->
<template>
  <ListPage
    title="场景库"
    width="wide"
    :subtitle="`共 ${store.scenarios.length} 个场景 · 1:N 数据集`"
  >
    <template #toolbar>
      <Input v-model="q" class="w-full max-w-[280px]" data-testid="scen-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索" />
      <!-- pool = filterableRows：module/author/priority 已从 meta.* 摊平的形状 -->
      <FilterPopover v-model="filters" :pool="filterableRows" />
      <Button data-testid="scen-create" @click="onCreate">+ 新建场景</Button>
    </template>

    <!-- Tabs (PRD §6.1) -->
    <template #tabs>
      <Tabs v-model="activeTab" data-testid="scen-tabs">
        <TabsList>
          <TabsTrigger value="mine">我的编排 ({{ myCount }})</TabsTrigger>
          <TabsTrigger value="public">公共编排 ({{ publicCount }})</TabsTrigger>
          <TabsTrigger value="favorite">收藏 ({{ favoriteCount }})</TabsTrigger>
        </TabsList>
      </Tabs>
    </template>

    <div v-if="store.scenariosStatus === 'loading'" class="loading-state">加载中…</div>
    <Table v-else-if="visible.length > 0" class="scenarios-table min-w-[1080px] table-fixed rounded-field border border-signal-line bg-signal-card">
      <TableHeader>
        <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
          <TableHead class="w-[3%]"></TableHead>
          <TableHead class="w-[24%] text-caption font-semibold text-muted-foreground">场景名</TableHead>
          <TableHead class="w-[10%] text-caption font-semibold text-muted-foreground">系统</TableHead>
          <TableHead class="w-[8%] text-caption font-semibold text-muted-foreground">模块</TableHead>
          <TableHead class="w-[6%] text-center text-caption font-semibold text-muted-foreground">优先级</TableHead>
          <TableHead class="w-[5%] text-center text-caption font-semibold text-muted-foreground">数据集</TableHead>
          <TableHead class="w-[5%] text-center text-caption font-semibold text-muted-foreground">步骤</TableHead>
          <TableHead class="w-[5%] text-center text-caption font-semibold text-muted-foreground">变量</TableHead>
          <TableHead class="w-[7%] text-caption font-semibold text-muted-foreground">作者</TableHead>
          <TableHead class="w-[9%] text-caption font-semibold text-muted-foreground">最后编辑</TableHead>
          <TableHead class="w-[10%] text-caption font-semibold text-muted-foreground">Tags</TableHead>
          <TableHead class="w-[8%] text-center text-caption font-semibold text-muted-foreground">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in paged" :key="rowKey(row)" :class="rowClassName({ row })" class="cursor-pointer" @click="openScenario(row)">
          <TableCell class="text-center">
            <button class="star-btn" :class="{ active: row.starred }" :aria-label="row.starred ? '取消收藏' : '收藏场景'" @click.stop="toggleStar(row)">
              <svg v-if="row.starred" width="18" height="18" viewBox="0 0 24 24" fill="#eab308"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/></svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/></svg>
            </button>
          </TableCell>
          <TableCell>
            <button class="name" @click.stop="openScenario(row)">{{ row.meta.name || row.meta.scenarioId }}</button>
            <span v-if="row.visibility === 'public'" class="vis-tag vis-public" title="公共:所有登录用户可读">公共</span>
            <span v-if="row.meta.expire" class="vis-tag vis-expired" title="已过期:① 基本信息中标记为过期的场景">已过期</span>
            <div class="sid">{{ row.meta.scenarioId }}</div>
            <div class="desc">{{ row.meta.description }}</div>
          </TableCell>
          <TableCell><div class="sys-list"><SystemChip v-for="sys in row.meta.system" :key="sys" :sys="sys" /></div></TableCell>
          <TableCell><TagPill :label="row.meta.module || '未分类'" /></TableCell>
          <TableCell class="text-center"><PriorityPill :priority="row.meta.priority" /></TableCell>
          <TableCell class="text-center"><span class="num">{{ row.dataSetCount }}</span></TableCell>
          <TableCell class="text-center"><span class="num">{{ row.stepCount }}</span></TableCell>
          <TableCell class="text-center"><span class="num">{{ Object.keys(row.config?.vars || {}).length }}</span></TableCell>
          <TableCell><span class="muted">{{ row.meta.author || row.meta.owner || '—' }}</span></TableCell>
          <TableCell><span class="muted">{{ formatTime(row.meta?.updateTime) }}</span></TableCell>
          <TableCell>
            <div v-if="row.tags.length" class="tag-list">
              <TagPill v-for="t in row.tags.slice(0, MAX)" :key="t" :label="t" tone="accent" />
              <TagPill v-if="row.tags.length > MAX" :label="`+${row.tags.length - MAX}`" />
            </div>
            <span v-else class="muted">—</span>
          </TableCell>
          <TableCell class="text-center">
            <div class="flex items-center justify-center gap-1">
              <button class="schemes-btn" data-testid="schemes-entry" type="button" @click.stop="router.push(scenarioSchemesUrl(row.meta.scenarioId))">
                方案<template v-if="row.schemeCount"> ·{{ row.schemeCount }}</template>
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" data-testid="scen-more" @click.stop>⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem data-testid="cmd-detail" @click="onCmd('detail', row)">查看详情</DropdownMenuItem>
                  <DropdownMenuItem data-testid="cmd-edit" @click="onCmd('edit', row)">编辑场景</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem data-testid="cmd-export" @click="onCmd('export', row)">导出 (JSON/YAML)</DropdownMenuItem>
                  <DropdownMenuItem data-testid="cmd-copy" @click="onCmd('copy', row)">复制到我的</DropdownMenuItem>
                  <DropdownMenuItem v-if="isMine(row) && row.visibility !== 'public'" data-testid="cmd-publish" @click="onCmd('publish', row)">发布到公共库</DropdownMenuItem>
                  <DropdownMenuItem v-if="isMine(row) && row.visibility === 'public'" @click="onCmd('unpublish', row)">下架为私有</DropdownMenuItem>
                  <DropdownMenuItem v-if="isMine(row)" class="text-signal-failed focus:bg-signal-failed/10 focus:text-signal-failed" data-testid="cmd-delete" @click="onCmd('delete', row)">删除</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <div v-else class="empty-state">
      <p>暂无场景 — 新建第一个场景开始编排</p>
      <Button variant="outline" size="sm" @click="onCreate">+ 新建场景</Button>
    </div>

<div v-if="total > pageSize" class="pager">
      <button type="button" class="pg-btn" :disabled="page <= 1" data-testid="pg-prev" @click="page--">&#8249;</button>
      <button
        v-for="p in pageCount"
        :key="p"
        type="button"
        class="pg-btn"
        :class="{ active: p === page }"
        @click="page = p"
      >{{ p }}</button>
      <button type="button" class="pg-btn" :disabled="page >= pageCount" data-testid="pg-next" @click="page++">&#8250;</button>
      <span class="pg-total">共 {{ total }} 条</span>
    </div>
  
    <!-- 按方案导出选择器(自绘轻量模态;替代原 ElMessageBox render-fn) -->
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
          <Button variant="outline" @click="settleExportPicker(undefined)">取消</Button>
          <Button data-testid="export-picker-ok" @click="confirmExportPicker">导出</Button>
        </div>
      </div>
    </div>
</ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { toast } from '@/utils/toast'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useAuthStore } from '@/stores/auth'
import { getScenarioDraft, listRunSchemes } from '@/api/scenario-composer'
import type { RunOverlay, SchemeV2 } from '@/api/scenario-composer'
import { convertDraftToExecutable, schemeToOverlay } from '@/stores/scenario-draft'
import { downloadFile } from '@/utils/download'
import { useListSearch } from '@/utils/useListSearch'
import { confirmAction } from '@/utils/confirmAction'
import { composerUrl, scenarioDetailUrl, scenarioSchemesUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'
import { shortDateTime, exportTimestamp } from '@/utils/datetime'
import FilterPopover from '@/components/FilterPopover.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import { applyFiltersToList, emptyFilters, type ScenarioFilters } from '@/utils/filters'
import type { Scenario } from '@/types/scenario-composer'

const store = useScenarioComposerStore()
const auth = useAuthStore()
const router = useRouter()
const MAX = 3
const pageSize = 20

const q = ref('')
const filters = ref<ScenarioFilters>(emptyFilters())
const page = ref(1)
const activeTab = ref<'mine' | 'public' | 'favorite'>('mine')

// Bind the header search box (v-model="q") INTO the composable — the
// old `{ filtered }`-only destructure left the composable's internal
// query permanently empty, so the search box was dead.
const { filtered } = useListSearch(
  () => store.scenarios,
  [
    'meta.name',
    'meta.scenarioId',
    'meta.module',
    'meta.description',
    'meta.system',
    'tags',
  ],
  q,
)

// Scenario keeps module/author/priority/updateTime nested under
// ``meta``, but the filter layer reads flat top-level fields.  Map each
// row once so FilterPopover's option lists and applyFiltersToList both
// see the expected shape (spread keeps every other field intact, so the
// table's row.meta.* bindings are unaffected).
const filterableRows = computed(() =>
  filtered.value.map((s) => ({
    ...s,
    module: s.meta.module,
    author: s.meta.author || s.meta.owner,
    priority: s.meta.priority,
    updated_at: s.meta.updateTime,
    system: s.meta.system,
    tags: s.meta.tags, // 真源 meta.tags(顶层 tags 是恒等镜像)
  })),
)

// P1 读侧收紧后:服务端只返回 public + 自己的;tab 在此基础上分桶。
// 'mine' = 私有(自己的),'public' = 公共,'favorite' = 星标。
const visible = computed(() => {
  // filter 层的 FilterRow 是最小形状;实际行是 Scenario 摊平超集
  // (starred/visibility 供 tab 分桶),收回窄类型。
  const rows = applyFiltersToList(filterableRows.value, filters.value) as typeof filterableRows.value
  if (activeTab.value === 'favorite') return rows.filter((r) => r.starred)
  if (activeTab.value === 'public') return rows.filter((r) => r.visibility === 'public')
  return rows.filter((r) => r.visibility !== 'public')
})
const total = computed(() => visible.value.length)
const pageCount = computed(() => Math.ceil(total.value / pageSize))

// Real pagination — slice for the current page (the pager used to
// render but never slice, so every page showed all rows).
const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return visible.value.slice(start, start + pageSize)
})

// Clamp the page when the filtered result shrinks (search/filter/delete)
// so we never sit on an empty page.
watch(total, () => {
  const maxPage = Math.max(1, Math.ceil(total.value / pageSize))
  if (page.value > maxPage) page.value = maxPage
})

const myCount = computed(
  () => store.scenarios.filter((s) => s.visibility !== 'public').length,
)
const publicCount = computed(
  () => store.scenarios.filter((s) => s.visibility === 'public').length,
)
const favoriteCount = computed(() => store.starredScenarios.length)

/** 属主判断(admin 全量;owner 与当前用户 display_name/username 名字比对,
 * 与后端 _ownership 的存量行回退规则一致;P2 回填 owner_id 后服务端
 * 比对为准,这里只是菜单显隐,服务端仍会 403 兜底)。 */
function isMine(row: Scenario): boolean {
  if (auth.isAdmin) return true
  const me = auth.currentUser?.display_name || auth.currentUser?.username || ''
  return !!me && me === (row.meta.owner || '')
}

onMounted(async () => {
  try {
    await store.fetchScenarios()
  } catch {
    showError('加载场景', undefined, store.lastError)
  }
})

function rowKey(row: Scenario) { return row.meta.scenarioId }

/** 过期行置灰:meta.expire → 行加 row-expired class(样式见 .row-expired)。
 *  过期只是视觉降级,行仍可点/可操作 — 与编排页顶栏的「已过期」pill 呼应。 */
function rowClassName({ row }: { row: Scenario }) {
  return row.meta.expire ? 'row-expired' : ''
}

const formatTime = shortDateTime

function openScenario(row: Scenario) {
  // 跳转到新的统一 CaseComposer 页面 (从 ① 基本信息 开始)
  router.push(composerUrl(row.meta.scenarioId))
}

function onCreate() {
  router.push('/composer/new?step=1')
}

/** 行级「按方案导出」选择器(spec §8):自绘轻量模态(radio 单选,
 *  原 ElMessageBox + render-fn 迁移;不经 Dialog Portal,原生控件
 *  行为可预期)。
 *  返回:SchemeV2 = 选中方案;null = 默认导出(不套方案);undefined = 取消。 */
const exportPicker = reactive<{
  open: boolean
  schemes: SchemeV2[]
  scenarioName: string
  chosen: string
  resolve: ((v: SchemeV2 | null | undefined) => void) | null
}>({ open: false, schemes: [], scenarioName: '', chosen: '', resolve: null })

function pickExportScheme(
  schemes: SchemeV2[],
  scenarioName: string,
): Promise<SchemeV2 | null | undefined> {
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
  settleExportPicker(
    chosen ? (exportPicker.schemes.find((s) => s.name === chosen) ?? null) : null,
  )
}

/** 行级导出 — 不污染共享 store 的"进行中"对象。
 *
 * 之前实现是先 loadFromSaved → exportJson,会把 store 当前持有的草稿覆盖掉,
 * 导致用户在 CaseComposer 里改了一半的其它场景被静默丢失。
 *
 * 这里直接走 plate preview-plate + 自己下载,store 状态完全不变。
 * 场景存有运行方案时先弹方案选择(可回退默认导出),选中后 overlay
 * ({serviceBindings})物化进导出(spec §8,envId 已随 D2 退役);无方案走原路径。
 */
async function exportRow(row: Scenario) {
  try {
    const draft = await getScenarioDraft(row.meta.scenarioId)
    // 按方案导出迁方案工作台 CRUD(阶段④:V1 sidecar 读侧回填下线)—
    // 方案列表属主可见,非属主(公共场景读者)403 → 静默降级默认导出
    // (与无方案场景同款路径,不阻断导出)。
    let schemes: SchemeV2[] = []
    try {
      schemes = await listRunSchemes(row.meta.scenarioId)
    } catch { /* 非属主读不到方案 — 默认导出 */ }
    let overlay: RunOverlay | undefined
    if (schemes.length) {
      const picked = await pickExportScheme(schemes, row.meta.name || row.meta.scenarioId)
      if (picked === undefined) return // 用户取消
      if (picked) overlay = schemeToOverlay(picked)
    }
    const converted = await convertDraftToExecutable(draft, overlay)
    const ts = exportTimestamp()
    const filename = `${row.meta.scenarioId}-${ts}.json`
    downloadFile(filename, JSON.stringify(converted, null, 2), 'application/json')
    toast.success(`已导出 ${filename}`)
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
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
  if (cmd === 'detail') return router.push(scenarioDetailUrl(row.meta.scenarioId))
  if (cmd === 'edit') return openScenario(row)
  if (cmd === 'copy') {
    try {
      const saved = await store.copyScenario(row.meta.scenarioId)
      toast.success(`已复制到我的场景：${saved.meta.name || saved.meta.scenarioId}`)
    } catch (e) {
      showError('复制', undefined, (e as Error).message)
    }
    return
  }
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
  if (cmd === 'export') return exportRow(row)
  if (cmd === 'delete') {
    const ok = await confirmAction(
      `确认删除场景 ${row.meta.name || row.meta.scenarioId}？其下所有用例与数据集将一并删除，操作不可撤销。`,
      '删除场景',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    if (!ok) return // 用户取消
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

.vis-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  font-size: 10px;
  vertical-align: 1px;
  border-radius: 3px;
}
.vis-public {
  color: #047857;
  background: #d1fae5;
}
.vis-expired {
  color: #64748b;
  background: #f1f5f9;
}

/* 过期条目整行置灰 — opacity 一次性压暗行内所有自带头色的小组件
 * (SystemChip/TagPill/PriorityPill…),比逐列改色一致。 */
:deep(tr.row-expired) { opacity: 0.55; }

.sid {
  margin-top: 2px;
  font-family: var(--font-mono, monospace);
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
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
}

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

/* 「方案」直接入口 —— 与 ⋯ dropdown 并列(操作列已放宽到 140);
 * 仿 .more-btn 但主色文字,把方案工作台从菜单里提为一级动作。 */
.schemes-btn {
  margin-right: 6px;
  padding: 3px 9px;
  font-size: 14px;
  color: var(--accent);
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 5px;
  cursor: pointer;
}
.schemes-btn:hover { border-color: var(--accent); }

.pager { justify-content: flex-end; margin-top: 12px; }

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
  width: min(440px, calc(100vw - 2rem));
  padding: 18px 20px; background: #fff;
  border-radius: 10px; box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}
.exp-panel h4 { margin: 0 0 6px; font-size: 14px; }
.exp-hint { margin: 0 0 12px; font-size: 12px; color: #5a6273; }
.exp-opt {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0; font-size: 12.5px; cursor: pointer;
}
.exp-opt input { accent-color: #2f6fed; }
.exp-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
