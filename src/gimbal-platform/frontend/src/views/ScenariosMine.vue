<!-- ScenariosMine.vue — 场景库 / 我的场景(编排工作台)。
     原 Scenarios.vue「我的编排」tab 拆出独立页:表格只负责列表浏览、
     方案快速预览、次数/并发轻量即时调整;深度编辑跳方案管理。 -->
<template>
  <section class="slib">
    <PageHead
      icon="folder"
      title="我的场景"
      :subtitle="pageSubtitle"
    />

    <div class="slib-toolbar">
      <!-- 分组态下展示值恒空(生效词是分组名,chip 高亮说明在搜什么);
           一敲键盘即退出分组态转手动搜索 -->
      <input
        :value="searchBox"
        class="slib-search"
        data-testid="mine-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索"
        @input="writeSearch(($event.target as HTMLInputElement).value)"
      />
      <FilterPopover v-model="filters" :pool="filterableRows" :facets="facets" />
      <button type="button" class="slib-create" data-testid="mine-create" @click="onCreate">+ 新建场景</button>
    </div>

    <!-- 筛选分组:当前搜索/筛选存为命名分组,点名 = 以分组名搜索(存服务端) -->
    <FilterGroups
      :groups="groups"
      :state="groupsState"
      :active-id="activeGroupId"
      :can-save="canSaveGroup"
      :busy="savingGroup"
      @apply="applyGroup"
      @remove="removeGroup"
      @save="saveGroup"
      @retry="loadGroups"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

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
                  <!-- F1:未读分享悬浮标签(unread resource_handoff 驱动,
                       进入场景即销账)—— hover title 给完整「来自 X 的分享」。 -->
                  <span
                    v-if="handoffSenders.has(row.meta.scenarioId)"
                    class="handoff-badge"
                    :data-testid="`handoff-badge-${row.meta.scenarioId}`"
                    :title="`来自 ${handoffSenders.get(row.meta.scenarioId)} 的分享`"
                  >分享</span>
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
              <td class="c-center"><span class="num">{{ row.varCount }}</span></td>
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
                  <DropdownMenuTrigger class="more-btn" @click.stop="openRowMenu(row)">⋯</DropdownMenuTrigger>
                  <DropdownMenuContent align="end" class="sl-menu">
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('detail', row)">查看详情</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('edit', row)">编辑场景</DropdownMenuItem>
                    <!-- F2(2026-09-23):重命名 —— 拉 draft 只改 meta.name 走既有
                         PUT(name 生成列自动重算,后端零新增);软校验,重名不拦。 -->
                    <DropdownMenuItem class="sl-menu-item" data-testid="rename-menu" @click="renameScenario(row)">重命名</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" data-testid="handoff-menu" @click="openHandoff(row)">分发给…</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="goSchemes(row)">方案管理</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" @click="onCmd('export', row)">导出 JSON</DropdownMenuItem>
                    <!-- 按方案导出(2026-09-22 重设计):原「导出 → 弹窗选方案」
                         两步改一步 —— 方案平铺为子菜单项,闭包持 scheme 对象
                         (同名方案以身份区分不串台)。打开行菜单即预取方案
                         (与内联展开共用缓存);无方案时项置灰说明。 -->
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger
                        class="sl-menu-item"
                        data-testid="export-sub-trigger"
                        :disabled="schemesLoadingId === row.meta.scenarioId"
                      >按方案导出</DropdownMenuSubTrigger>
                      <DropdownMenuSubContent class="sl-menu" data-testid="export-sub">
                        <DropdownMenuItem
                          v-if="schemesLoadingId === row.meta.scenarioId"
                          class="sl-menu-item"
                          disabled
                        >方案加载中…</DropdownMenuItem>
                        <template v-else>
                          <DropdownMenuItem
                            v-if="!schemesByScenario.get(row.meta.scenarioId)?.length"
                            class="sl-menu-item"
                            disabled
                          >该场景暂无方案</DropdownMenuItem>
                          <DropdownMenuItem
                            v-for="sc in schemesByScenario.get(row.meta.scenarioId) ?? []"
                            :key="sc.schemeId"
                            class="sl-menu-item"
                            :data-testid="`export-scheme-${sc.schemeId}`"
                            @click="exportByScheme(row, sc)"
                          >{{ sc.name }}</DropdownMenuItem>
                        </template>
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                    <DropdownMenuItem v-if="row.visibility !== 'public'" class="sl-menu-item" @click="onCmd('publish', row)">发布到公共库</DropdownMenuItem>
                    <DropdownMenuItem v-else class="sl-menu-item" @click="onCmd('unpublish', row)">下架为私有</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item danger" @click="onCmd('delete', row)">删除</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </td>
            </tr>
            <tr v-if="expandedId === row.meta.scenarioId" class="scheme-panel-row" @click.stop>
              <td :colspan="10">
                <div v-if="schemesLoadingId === row.meta.scenarioId" class="slib-loading">方案加载中…</div>
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
      <p>{{ filtering
        ? '没有匹配的场景 — 换个关键词,或清掉筛选条件'
        : '暂无场景 — 新建第一个场景开始编排' }}</p>
      <button v-if="!filtering" type="button" class="slib-create" @click="onCreate">+ 新建场景</button>
    </div>

    <Pagination
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      show-page-size
      show-jump
    />

    <p class="slib-note">
      「次数」「并发」是卡片底部两个独立的小徽章,平时只显示当前值,点一下变成可编辑输入框直接改数字;不需要额外弹一整层面板。更深的参数还是要进方案管理去改。方案卡片左上角的「默认」标记指这个场景的默认方案——关注页的执行健康趋势只统计默认方案的执行结果,不跨方案聚合。
    </p>

    <!-- F1(2026-09-23):分发给…(副本交接;结果面板在弹窗内) -->
    <HandoffDialog v-model:open="handoffOpen" :scenario="handoffTarget" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'
import {
  getScenarioDraft, listRunSchemes, updateRunScheme, runScenario, schemeToRunRequest,
  updateScenario,
  type SchemeV2,
} from '@/api/scenario-composer'
import { convertDraftToExecutable, schemeToOverlay } from '@/stores/scenario-draft'
import FilterGroups from '@/components/scenario-lib/FilterGroups.vue'
import HandoffDialog from '@/components/scenario-lib/HandoffDialog.vue'
import { getHandoffUnread } from '@/api/handoff'
import { markRead } from '@/api/notifications'
import { downloadFile } from '@/utils/download'
import { confirmAction, promptAction } from '@/utils/confirmAction'
import { composerUrl, scenarioDetailUrl, scenarioSchemesUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'
import { shortDateTime } from '@/utils/datetime'
import { useScenarioRuns } from '@/composables/useScenarioRuns'
import { FollowCapError } from '@/composables/useFollowLayout'
import { useScenarioListView } from '@/composables/useScenarioListView'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import SchemeCard from '@/components/scenario-lib/SchemeCard.vue'
import { Pagination } from '@/components/ui/pagination'
import FilterPopover from '@/components/FilterPopover.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSub,
  DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { ScenarioListItem } from '@/types/scenario-composer'

const PREVIEW_MAX = 3
const MAX = 3

const auth = useAuthStore()
const router = useRouter()
const runs = useScenarioRuns()

// 我的场景 = 私有桶(公共场景在独立页,两页分桶互补)。检索/筛选/分页
// 与筛选分组骨架全在 useScenarioListView,与公共页共用。
const {
  store, filters, page, paged, total, filtering, filterableRows, facets, load, pageSize, loading,
  searchBox, writeSearch,
  groups, groupsState, savingGroup, activeGroupId, canSaveGroup, loadGroups, applyGroup, saveGroup, removeGroup,
} = useScenarioListView('mine')

const expandedId = ref<string | null>(null)
const schemesLoadingId = ref<string | null>(null)
const schemesByScenario = reactive(new Map<string, SchemeV2[]>())

/** 展开行是否还有在途执行(queued/running)—— 非空即启动轮询。 */
const expandedInFlight = computed(() => {
  const id = expandedId.value
  if (!id) return null
  const any = runs.runsOf(id).value.some(
    (e) => e.status === 'running' || e.status === 'queued')
  return any ? id : null
})
// 面板开着等结果:在途期间每 10s 强刷,终态落地卡面自动翻「完成/失败」,
// 下一次刷新算出无在途 → computed 变 null → onCleanup 自停。
watch(expandedInFlight, (id, _prev, onCleanup) => {
  if (!id) return
  const timer = window.setInterval(() => { void runs.load(id, true) }, 10_000)
  onCleanup(() => window.clearInterval(timer))
})

/** 后端读侧「admin 全量;普通用户 = public + 自己的」→ 非 public 桶对管理员
 *  装的是全员的私有场景,副标题必须说实话,不能对管理员自称"你的"。 */
const pageSubtitle = computed(() =>
  auth.isAdmin
    ? `共 ${total.value} 个场景 · 管理员可见全员私有编排(含他人的)`
    : `共 ${total.value} 个场景 · 你创建或拥有的编排`,
)

const formatTime = shortDateTime

onMounted(load)
onMounted(loadHandoffBadges)

function openScenario(row: ScenarioListItem) {
  void consumeHandoffBadge(row.meta.scenarioId)
  router.push(composerUrl(row.meta.scenarioId))
}
function onCreate() {
  router.push('/composer/new?step=1')
}
function goSchemes(row: ScenarioListItem) {
  router.push(scenarioSchemesUrl(row.meta.scenarioId))
}

// ── 方案内联预览 ───────────────────────────────────────────────
async function toggleExpand(row: ScenarioListItem) {
  const id = row.meta.scenarioId
  if (expandedId.value === id) {
    expandedId.value = null
    return
  }
  expandedId.value = id
  // 执行状态每次展开都强刷(方案列表仍走缓存):runs 缓存是模块级、
  // 跨路由存活的,不强刷会一直显示发起时那份「执行中」旧照 ——
  // 执行早已完成、执行记录页也翻篇了,这里还钉在 running。
  const runsP = runs.load(id, true)
  if (schemesByScenario.has(id)) return
  schemesLoadingId.value = id
  try {
    const [schemes] = await Promise.all([listRunSchemes(id), runsP])
    schemesByScenario.set(id, schemes)
  } catch (e) {
    toast.error(`方案加载失败: ${(e as Error).message}`)
    schemesByScenario.set(id, [])
  } finally {
    // 只清自己的加载态:A 的慢请求回来时不得灭掉 B 正在显示的 spinner
    if (schemesLoadingId.value === id) schemesLoadingId.value = null
  }
}

function visibleSchemes(scenarioId: string): SchemeV2[] {
  return (schemesByScenario.get(scenarioId) || []).slice(0, PREVIEW_MAX)
}
function overflowCount(scenarioId: string): number {
  const n = (schemesByScenario.get(scenarioId) || []).length
  return n > PREVIEW_MAX ? n - PREVIEW_MAX : 0
}

async function updateScheme(row: ScenarioListItem, scheme: SchemeV2, patch: { nRuns?: number; parallel?: number }) {
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

async function runScheme(row: ScenarioListItem, scheme: SchemeV2) {
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
async function toggleStar(row: ScenarioListItem) {
  // 乐观翻转:行来自服务端分页(useServerList),store.invalidate 不会
  // 重拉当前页 —— 不翻行内状态,星星要等刷新页面才变(2026-09-23 修)
  const next = !row.starred
  row.starred = next
  try {
    await store.toggleStarWithCap(row.meta.scenarioId, next)
  } catch (e) {
    row.starred = !next // 回滚
    // 上限是预期分支 → 一句人话;其余才走通用错误兜底
    if (e instanceof FollowCapError) toast.error(e.message)
    else showError('关注', undefined, (e as Error).message)
  }
}

// ── 导出(2026-09-22 重设计:弹窗退役,方案平铺进行菜单子菜单)───
/** 打开行菜单时预取该场景方案(与内联展开共用 schemesByScenario 缓存);
 *  非属主读不到方案 → 空数组,子菜单显示「该场景暂无方案」。 */
function openRowMenu(row: ScenarioListItem): void {
  const id = row.meta.scenarioId
  if (schemesByScenario.has(id) || schemesLoadingId.value === id) return
  schemesLoadingId.value = id
  listRunSchemes(id)
    .then((schemes) => schemesByScenario.set(id, schemes))
    .catch(() => schemesByScenario.set(id, []))
    .finally(() => {
      // 只清自己的加载态:A 的慢请求回来时不得灭掉 B 正在显示的 spinner
      if (schemesLoadingId.value === id) schemesLoadingId.value = null
    })
}

async function downloadExecutable(
  row: ScenarioListItem,
  scheme: SchemeV2 | null,
): Promise<void> {
  const draft = await getScenarioDraft(row.meta.scenarioId)
  const converted = await convertDraftToExecutable(draft, scheme ? schemeToOverlay(scheme) : undefined)
  const filename = `${row.meta.scenarioId}-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`
  downloadFile(filename, JSON.stringify(converted, null, 2), 'application/json')
  toast.success(scheme ? `已按方案「${scheme.name}」导出 ${filename}` : `已导出 ${filename}`)
}

async function exportRow(row: ScenarioListItem): Promise<void> {
  try {
    await downloadExecutable(row, null)
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
  }
}

/** 按方案导出:方案的 serviceBindings 物化进导出文件(spec §8)。 */
async function exportByScheme(row: ScenarioListItem, scheme: SchemeV2): Promise<void> {
  try {
    await downloadExecutable(row, scheme)
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
  }
}

// ── F2(2026-09-23):重命名 ───────────────────────────────────────
/** 拉 draft 只改 meta.name 走既有 PUT(name 生成列自动重算,后端零新增)。
 * 软校验口径:与已有场景重名不拦(库里躺着历史重名,硬拦会卡死老数据)。 */
async function renameScenario(row: ScenarioListItem) {
  const id = row.meta.scenarioId
  const name = await promptAction(
    '场景名称(1–64 字符)', '重命名场景', { inputValue: row.meta.name })
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed || trimmed === row.meta.name) return
  if (trimmed.length > 64) return toast.error('名称最长 64 字符')
  try {
    const draft = await getScenarioDraft(id)
    draft.definition.meta = { ...draft.definition.meta, name: trimmed }
    await updateScenario(id, draft)
    toast.success(`已重命名为 ${trimmed}`)
    await load() // 当前页重拉(名称列/筛选索引同步)
  } catch (e) {
    showError('重命名', undefined, (e as Error).message)
  }
}

// ── F1(2026-09-23):分发给… + 「来自 X 的分享」悬浮标签 ──────────
const handoffOpen = ref(false)
const handoffTarget = ref<{ id: string; name: string } | null>(null)
/** scenarioId → 发送方昵称(unread resource_handoff;空 Map = 无标签)。 */
const handoffSenders = ref(new Map<string, string>())

async function loadHandoffBadges() {
  try {
    const { items } = await getHandoffUnread()
    handoffSenders.value = new Map(
      items
        .filter((i) => i.senderName)
        .map((i) => [i.resourceId, i.senderName as string]))
  } catch { /* 徽标是增强:失败静默留白 */ }
}

function openHandoff(row: ScenarioListItem) {
  handoffTarget.value = {
    id: row.meta.scenarioId,
    name: row.meta.name || row.meta.scenarioId,
  }
  handoffOpen.value = true
}

/** 进入场景即销账悬浮标签(方案 §1.4 消失时机):乐观摘牌 +
 *  按通知 id 标读;销账失败不拦导航。 */
async function consumeHandoffBadge(scenarioId: string) {
  if (!handoffSenders.value.has(scenarioId)) return
  handoffSenders.value = new Map(
    [...handoffSenders.value].filter(([k]) => k !== scenarioId))
  try {
    const { items } = await getHandoffUnread()
    const ids = items
      .filter((i) => i.resourceId === scenarioId)
      .map((i) => i.id)
    if (ids.length) await markRead(ids)
  } catch { /* 静默 */ }
}

async function onCmd(cmd: string, row: ScenarioListItem) {
  if (cmd === 'detail') {
    void consumeHandoffBadge(row.meta.scenarioId)
    return router.push(scenarioDetailUrl(row.meta.scenarioId))
  }
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
      await load() // 当前页重拉(store 退位后不再有全量乐观 upsert)
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
      await load()
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
      await load()
    } catch (e) {
      showError('删除', undefined, (e as Error).message)
    }
  }
}
</script>

<style scoped>
.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
.row-expired td { opacity: 0.55; }
/* F1:未读分享标签 —— hover title 由模板提供,这里只管形态 */
.handoff-badge {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 3px 8px;
  border-radius: 999px;
  color: #b45309;
  background: rgb(245 158 11 / 12%);
  border: 1px solid rgb(245 158 11 / 45%);
  cursor: help;
}
</style>
