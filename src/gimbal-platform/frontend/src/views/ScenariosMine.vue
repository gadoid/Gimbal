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
      <!-- 浏览镜头(方案 §5.1):admin 默认「我的」,显式切「全员视角」
           恢复全量。镜头是查询偏好(记本地),不动权限边界。 -->
      <button
        v-if="lensAvailable"
        type="button"
        class="slib-lens"
        :class="{ on: lensAll }"
        :data-testid="lensAll ? 'mine-lens-all-on' : 'mine-lens-all-off'"
        :title="lensAll
          ? '当前:全员视角(全部场景)——点按回「我的」'
          : '当前:我的——点按切「全员视角」看全部场景'"
        @click="toggleLens"
      >{{ lensAll ? '◉ 全员视角' : '○ 全员视角' }}</button>
      <!-- P1 尾巴①:批量加入 suite。仅「我的」镜头可选行(成员须是
           suite 属主自己的场景,§6.3);全员视角(admin)含他人场景,
           勾选禁用以免必 404。 -->
      <button
        type="button"
        class="slib-addsuite"
        data-testid="mine-add-to-suite"
        :disabled="!selectable || !selectedCount"
        :title="!selectable
          ? '「全员视角」下含他人场景,不能加入自己的 Suite —— 切回「我的」再操作'
          : selectedCount
            ? `把勾选的 ${selectedCount} 个场景加入一个 Suite`
            : '勾选场景后加入 Suite'"
        @click="atsOpen = true"
      >加入 Suite{{ selectedCount ? ` (${selectedCount})` : '' }}</button>
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
            <th v-if="selectable" style="width:30px" class="c-center">
              <input
                type="checkbox"
                data-testid="mine-select-page"
                :checked="pageAllSelected"
                title="全选/清空本页"
                @change="togglePage"
              />
            </th>
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
              <td v-if="selectable" class="c-center" @click.stop>
                <input
                  type="checkbox"
                  :data-testid="`mine-select-${row.meta.scenarioId}`"
                  :checked="selection.has(row.meta.scenarioId)"
                  @change="toggleRow(row)"
                />
              </td>
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
                  <!-- 已发布徽标(§5.2):mine 镜头含自己的已发布场景,
                       徽标替代「发布后从我的页消失」的旧缺陷。 -->
                  <span
                    v-if="row.visibility === 'public'"
                    class="pub-badge"
                    :data-testid="`pub-badge-${row.meta.scenarioId}`"
                    title="已发布到公共库"
                  >公共</span>
                  <!-- P2 徽标(§7.11)+ D-1 补遗:属主「已引用分享」(布尔,
                       不显人数);名单含经由所属 Suite 的间接引用
                       (数据源 /shares/referrers)。 -->
                  <span
                    v-if="sharedOutIds.has(row.meta.scenarioId)"
                    class="ref-badge"
                    :data-testid="`ref-out-badge-${row.meta.scenarioId}`"
                    title="此场景正被引用分享(保存后对方立即生效)"
                  >已引用分享</span>
                  <span
                    v-if="sharedInMeta.get(row.meta.scenarioId)"
                    class="ref-in-badge"
                    :data-testid="`ref-in-badge-${row.meta.scenarioId}`"
                    :title="`引用 · 来自 ${sharedInMeta.get(row.meta.scenarioId)}`"
                  >引用</span>
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
                    <DropdownMenuItem class="sl-menu-item" data-testid="share-menu" @click="openShare(row)">分享…</DropdownMenuItem>
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
              <td :colspan="selectable ? 11 : 10">
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

    <!-- 「共享给我的(引用)」区块(Suite 层重构第 2 步,原 P2 尾巴):
         与 Suite 列表同款分区与退订口径;引用 ⇒ 可读可运行,行点击进
         场景详情;拷贝分享得到的是副本、归自己名下,不进该区块。 -->
    <div v-if="sharedInScenarios.length" class="shared-in" data-testid="shared-in-scenarios">
      <p class="shared-in-label">共享给我的(引用)</p>
      <div
        v-for="r in sharedInScenarios"
        :key="r.id"
        class="shared-row"
        :data-testid="`shared-scenario-${r.scenarioId}`"
      >
        <span class="su-name">
          {{ r.scenarioName || r.scenarioId }}
          <span class="ref-in-badge">引用 · 来自 {{ r.grantedByName }}</span>
        </span>
        <button
          class="cta"
          :data-testid="`shared-scenario-open-${r.scenarioId}`"
          @click="router.push(scenarioDetailUrl(r.scenarioId as string))"
        >打开</button>
        <button
          class="unsub-btn"
          :data-testid="`shared-scenario-unsub-${r.scenarioId}`"
          @click="unsubscribeScenario(r)"
        >退订</button>
      </div>
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

    <!-- P2:分享弹窗(引用/副本;现有引用可撤销) -->
    <ShareDialog
      v-model:open="shareOpen"
      :resource="shareTarget"
      @changed="loadShareBadges"
    />

    <!-- P1 尾巴①:批量加入 Suite(目标选择弹窗;成功后清勾选) -->
    <AddToSuiteDialog
      v-model:open="atsOpen"
      :scenarios="selectedScenarios"
      @added="onAddedToSuite"
    />
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
import AddToSuiteDialog from '@/components/suites/AddToSuiteDialog.vue'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import { listShares, deleteShare, listScenarioReferrers } from '@/api/shares'
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
  lensAll, lensAvailable, toggleLens,
  searchBox, writeSearch,
  groups, groupsState, savingGroup, activeGroupId, canSaveGroup, loadGroups, applyGroup, saveGroup, removeGroup,
} = useScenarioListView('mine')

const expandedId = ref<string | null>(null)
const schemesLoadingId = ref<string | null>(null)
const schemesByScenario = reactive(new Map<string, SchemeV2[]>())

// ── P1 尾巴①:批量勾选 + 加入 Suite ────────────────────────────
// 勾选只在「我的」镜头开放(成员须是 suite 属主自己的场景,§6.3);
// 全员视角(admin)行内含他人场景,勾选列整个隐藏。
const selectable = computed(() => !lensAll.value)
const selection = ref(new Set<string>())
const atsOpen = ref(false)
const selectedCount = computed(() => selection.value.size)
const pageAllSelected = computed(() =>
  selectable.value && paged.value.length > 0
  && paged.value.every((r) => selection.value.has(r.meta.scenarioId)))
/** 弹窗入参:勾选的场景(名称从已加载行找,跨页勾选兜底用 id)。 */
const selectedScenarios = computed(() =>
  [...selection.value].map((id) => ({
    id,
    name: filterableRows.value.find((r) => r.meta.scenarioId === id)
      ?.meta?.name || id,
  })))

function toggleRow(row: ScenarioListItem): void {
  const next = new Set(selection.value)
  const id = row.meta.scenarioId
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selection.value = next
}

function togglePage(): void {
  const ids = paged.value.map((r) => r.meta.scenarioId)
  const all = ids.every((id) => selection.value.has(id))
  const next = new Set(selection.value)
  for (const id of ids) {
    if (all) next.delete(id)
    else next.add(id)
  }
  selection.value = next
}

/** 加入成功:清空勾选(下一批从零开始);行内 suite 归属不回显
 *  (反查在场景详情页,尾巴②)。 */
function onAddedToSuite(): void {
  selection.value = new Set()
}

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
    ? (lensAll.value
        ? `共 ${total.value} 个场景 · 全员视角(全量)`
        : `共 ${total.value} 个场景 · 我的(切「全员视角」看全部)`)
    : `共 ${total.value} 个场景 · 你创建或拥有的编排`,
)

const formatTime = shortDateTime

onMounted(load)
onMounted(loadHandoffBadges)
onMounted(loadShareBadges)

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

// ── P2:分享弹窗 + 徽标数据(§7.11)─────────────────────────────
const shareOpen = ref(false)
const shareTarget = ref<{
  type: 'scenario' | 'suite'; id: string; name: string
} | null>(null)
/** 属主侧:被引用的场景 id 集(「已引用分享」徽标,布尔不显人数)。 */
const sharedOutIds = ref(new Set<string>())
/** 被分享人侧:scenarioId → 分享者名(「引用 · 来自 X」徽标)。 */
const sharedInMeta = ref(new Map<string, string>())

function openShare(row: ScenarioListItem) {
  shareTarget.value = {
    type: 'scenario',
    id: row.meta.scenarioId,
    name: row.meta.name || row.meta.scenarioId,
  }
  shareOpen.value = true
}

async function loadShareBadges() {
  // 增强信息:失败静默留白(与 handoff 徽标同口径)
  try {
    const inn = await listShares({ direction: 'in', resourceType: 'scenario' })
      .catch(() => [])
    sharedInMeta.value = new Map(
      inn.filter((r) => r.scenarioId)
        .map((r) => [r.scenarioId as string, r.grantedByName]))
    sharedInScenarios.value = inn.filter((r) => r.scenarioId)
    // 「已引用分享」徽标(D-1 补遗):改用 /shares/referrers —— 含经由
    // 所属 Suite 的间接引用(此前只查直接引用,Suite 场景下徽标落空)。
    // 只对当前页的行发起(每场景一次轻查询)。
    const ids = paged.value.map((r) => r.meta.scenarioId)
    const results = await Promise.all(ids.map((id) =>
      listScenarioReferrers(id).then(({ items }) => [id, items.length > 0] as const)
        .catch(() => [id, false] as const)))
    const next = new Set(sharedOutIds.value)
    for (const [id, hit] of results) {
      if (hit) next.add(id)
    }
    sharedOutIds.value = next
  } catch { /* 静默 */ }
}

/** 被引用场景(id 非空断言由模板过滤保证)。 */
const sharedInScenarios = ref<Array<{
  id: number; scenarioId: string | null; scenarioName: string | null
  grantedByName: string
}>>([])

async function unsubscribeScenario(r: { id: number; scenarioName?: string | null }): Promise<void> {
  try {
    await deleteShare(r.id)
    sharedInScenarios.value = sharedInScenarios.value.filter((x) => x.id !== r.id)
    toast.success('已退订该引用')
  } catch (e) {
    toast.error(`退订失败:${(e as Error).message}`)
  }
}

// ── 「来自 X 的分享」悬浮标签(未读 resource_handoff;销账走通知)──
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

/* 已发布徽标(§5.2):mine 镜头里自己的公共场景。 */
.pub-badge {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 3px 8px;
  border-radius: 999px;
  color: #15803d;
  background: rgb(34 197 94 / 12%);
  border: 1px solid rgb(34 197 94 / 45%);
  cursor: help;
}

/* 浏览镜头开关(§5.1):admin 的显式「全员视角」。 */
.slib-lens {
  flex: none;
  font-size: 12px;
  line-height: 1;
  padding: 7px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--sl-ink-soft, #64748b);
  background: transparent;
  border: 1px solid rgb(100 116 139 / 35%);
  white-space: nowrap;
}
.slib-lens:hover { border-color: rgb(100 116 139 / 70%); }
.slib-lens.on {
  color: #1d4ed8;
  border-color: rgb(59 130 246 / 55%);
  background: rgb(59 130 246 / 10%);
}

/* P2 徽标(§7.11) */
.ref-badge {
  flex: none; font-size: 11px; line-height: 1; padding: 3px 8px;
  border-radius: 999px; color: #6d28d9;
  background: rgb(139 92 246 / 10%); border: 1px solid rgb(139 92 246 / 40%);
  cursor: help;
}
.ref-in-badge {
  flex: none; font-size: 11px; line-height: 1; padding: 3px 8px;
  border-radius: 999px; color: #15803d;
  background: rgb(34 197 94 / 10%); border: 1px solid rgb(34 197 94 / 40%);
  cursor: help;
}

/* P1 尾巴①:批量加入 Suite 入口(与镜头/新建同排)。 */
.slib-addsuite {
  flex: none;
  font-size: 12px;
  line-height: 1;
  padding: 7px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #15803d;
  background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 45%);
  white-space: nowrap;
}
.slib-addsuite:disabled {
  cursor: not-allowed;
  color: var(--c-text-tertiary, #94a3b8);
  background: transparent;
  border-color: rgb(100 116 139 / 25%);
}
.slib-addsuite:not(:disabled):hover { background: rgb(34 197 94 / 18%); }

/* 「共享给我的(引用)」区块(与 Suite 列表同款样式口径) */
.shared-in { margin-top: 22px; }
.shared-in-label { font-size: 13px; color: rgb(100 116 139); margin: 8px 0; }
.shared-row {
  display: grid; grid-template-columns: minmax(200px, 1fr) auto auto;
  gap: 12px; align-items: center; padding: 9px 14px;
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  margin-bottom: 6px;
}
.su-name { font-weight: 600; font-size: 13px; }
.ref-in-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 999px; margin-left: 6px;
  color: #15803d; background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); font-weight: 400;
}
.cta { color: #2563eb; background: none; border: none; cursor: pointer; font-size: 13px; }
.unsub-btn {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #b45309; background: rgb(245 158 11 / 8%);
  border: 1px solid rgb(245 158 11 / 35%);
}
</style>
