<!-- SuiteLibrary.vue — 场景集(原型 02,Suite 层重构第 2 步;2026-10-10
     IA:独立成组;2026-11-10 IA:并入侧栏「我的」组,页面更名场景集)。
     页头 + 搜索 / 模式筛选 + 表格
     (Suite · 模式 · 成员 · 最近运行 · 操作)。草稿带「草稿」标记;
     「共享给我的」独立分区(§7.11);「公共用例集」链接到独立公共页。
     行点击进 20(本人最近一次发起的运行失败则进 21);行内「运行」
     开 30 预检;⋯ 重命名 / 复制 / 分享 / 发布(下架)/ 删除。 -->
<template>
  <section class="slib">
    <PageHead icon="stack" title="场景集" :count="`共 ${total} 个`" :subtitle="subtitle" />

    <div class="slib-toolbar">
      <input
        v-model="q"
        class="slib-search"
        data-testid="suite-search"
        placeholder="按名称 / 描述 / 成员场景搜索"
      />
      <div class="slib-modes" data-testid="suite-mode-filter">
        <button
          v-for="m in modeFilters"
          :key="m.key"
          type="button"
          class="slib-mode"
          :class="{ on: modeFilter === m.key }"
          :data-testid="`suite-filter-${m.key || 'all'}`"
          @click="modeFilter = m.key"
        >{{ m.label }}</button>
      </div>
      <router-link class="slib-public-link" to="/suites/public" data-testid="suite-public-link">公共用例集</router-link>
      <button
        type="button"
        class="slib-create"
        data-testid="suite-create"
        :disabled="creating"
        @click="onCreate"
      >+ 新建 Suite</button>
    </div>

    <div v-if="status === 'loading'" class="slib-loading">加载中…</div>
    <div v-else-if="status === 'error'" class="card-empty">
      <p>加载失败</p>
      <button type="button" class="cta" @click="load">重试</button>
    </div>
    <div v-else-if="!items.length" class="card-empty">
      <p>还没有 Suite —— 新建一个,把场景归组并编排它们怎么跑</p>
    </div>

    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>Suite</th>
            <th style="width:6.25rem">模式</th>
            <th style="width:4.375rem">成员</th>
            <th style="width:10.625rem">最近运行</th>
            <th style="width:10.625rem">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in items"
            :key="s.suiteId"
            class="slib-row"
            :data-testid="`suite-row-${s.suiteId}`"
            @click="openSuite(s)"
          >
            <td>
              <div class="sl-name">
                <span class="nm">{{ s.name }}</span>
                <span v-if="s.isDraft" class="draft-chip" title="草稿:不出现在发布 / 分享;空草稿 30 天自动清理">草稿</span>
                <!-- pub/proj 徽标与「归属」列随「全员视角」镜头退役移除:本页
                     恒 scope=private(我名下且未加入项目),两分支结构性不可达。 -->
              </div>
              <div class="sl-sid">{{ s.description || '—' }}</div>
            </td>
            <td><span class="mode-chip" :class="s.mode">{{ MODE_LABEL[s.mode] || s.mode }}</span></td>
            <td><span class="num">{{ s.memberCount }}</span></td>
            <td>
              <span v-if="s.latestRun" class="last-run">
                <i class="dot" :class="runStatusTone(s.latestRun.status ?? '')"></i>
                {{ latestRunText(s.latestRun) }}
              </span>
              <span v-else class="muted">—</span>
            </td>
            <td class="ops" @click.stop>
              <button
                type="button"
                class="run-btn"
                :data-testid="`suite-row-run-${s.suiteId}`"
                :disabled="!s.memberCount"
                title="运行(先过预检)"
                @click="openPreflight(s)"
              >运行</button>
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" :data-testid="`suite-row-more-${s.suiteId}`">⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" @click="renameSuite(s)">重命名</DropdownMenuItem>
                  <DropdownMenuItem
                    class="sl-menu-item"
                    :disabled="s.isDraft"
                    :data-testid="`suite-row-copy-${s.suiteId}`"
                    :title="s.isDraft ? '草稿无需复制 —— 完成编排后可复制' : '深拷贝为一份自己的副本(含编排)'"
                    @click="copySuite(s)"
                  >复制</DropdownMenuItem>
                  <DropdownMenuItem
                    v-if="s.visibility !== 'public'"
                    class="sl-menu-item"
                    :disabled="s.isDraft"
                    :data-testid="`suite-row-share-${s.suiteId}`"
                    :title="s.isDraft ? '草稿不可分享 —— 完成编排后可分享' : ''"
                    @click="openShare(s)"
                  >分享…</DropdownMenuItem>
                  <DropdownMenuItem
                    v-if="s.visibility !== 'public'"
                    class="sl-menu-item"
                    :disabled="s.isDraft"
                    :data-testid="`suite-row-publish-${s.suiteId}`"
                    :title="s.isDraft ? '草稿不可发布 —— 完成编排后可发布' : '发布到公共库(成员及其数据集一并公开)'"
                    @click="publishSuite(s)"
                  >发布到公共库</DropdownMenuItem>
                  <DropdownMenuItem
                    v-else
                    class="sl-menu-item"
                    :data-testid="`suite-row-unpublish-${s.suiteId}`"
                    @click="unpublishSuite(s)"
                  >下架为私有</DropdownMenuItem>
                  <!-- S7.2:加入普通项目(私有套件;公共走「发布」) -->
                  <DropdownMenuItem
                    v-if="s.projectId == null"
                    class="sl-menu-item"
                    :data-testid="`suite-row-promote-${s.suiteId}`"
                    @click="promoTarget = s"
                  >加入项目…</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item danger" @click="removeSuite(s)">删除</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination
      v-if="pageCount > 1"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      show-page-size
      show-jump
    />

    <!-- 运行预检(30):从列表行发起 -->
    <SuiteRunPreflight
      v-model:open="preflightOpen"
      :suite-id="preflightId"
      :running="running"
      @run="onRun"
      @locate="() => preflightOpen = false"
    />

    <!-- 分享弹窗(S7.4 后仅副本模式) -->
    <ShareDialog
      v-model:open="shareOpen"
      :resource="shareTarget ? {
        type: 'suite' as const,
        id: String(shareTarget.suiteId),
        name: shareTarget.name,
      } : null"
    />
  
  <!-- S7.2:加入项目对话框 -->
  <PromotionDialog
    :open="!!promoTarget"
    kind="suite"
    :source-id="promoTarget ? String(promoTarget.suiteId) : ''"
    :source-name="promoTarget?.name ?? ''"
    @close="promoTarget = null"
    @done="load"
  />
</section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SuiteRunPreflight from '@/components/suites/SuiteRunPreflight.vue'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import { Pagination } from '@/components/ui/pagination'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  deleteSuite, deleteSuitePublish, forkPublicSuite, getSuite, listSuites,
  patchSuite, postSuitePublish, runSuite, suiteErrDetail,
  type SuiteLatestRun, type SuiteSummary,
} from '@/api/suites'
import PromotionDialog from '@/components/project/PromotionDialog.vue'
import { usePagerSize } from '@/composables/usePagerSize'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'
import { promptAction, confirmAction } from '@/utils/confirmAction'
import { executionsBatchUrl } from '@/utils/links'
import { MODE_LABEL, runStatusTone } from '@/utils/suiteStructure'

const router = useRouter()

// S7.2:加入项目(析出分析 → 直通复制 / 冲突转审批)
const promoTarget = ref<SuiteSummary | null>(null)

const q = ref('')
const status = ref<'loading' | 'ready' | 'error'>('loading')
const items = ref<SuiteSummary[]>([])
const modeFilter = ref('')
// 服务端分页(搜索/模式过滤也走服务端 —— 客户端只过滤当前页会跨页丢行)
const total = ref(0)
const page = ref(1)
const { pageSize } = usePagerSize('suite-library', 10)

const modeFilters = [
  { key: '', label: '全部' },
  { key: 'aggregate', label: MODE_LABEL.aggregate },
  { key: 'chain', label: MODE_LABEL.chain },
  { key: 'fanout', label: MODE_LABEL.fanout },
  { key: 'compose', label: MODE_LABEL.compose },
]

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

// 计数走 count 常驻;说明收进问号悬浮(2026-11-05 说明统一轮)。
// 「全员视角」镜头退役:本页恒 scope=private,所有角色同一句说明。
const subtitle = '一组场景及其运行编排 · 你创建的(草稿也在这里,带「草稿」标记)'

// 搜索(防抖)/模式筛选 → 回第 1 页重拉;翻页直接拉
let qTimer: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(qTimer)
  qTimer = setTimeout(() => {
    if (page.value !== 1) page.value = 1
    else void load()
  }, 300)
})
watch(modeFilter, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})
watch(page, () => void load())
watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})

async function load(): Promise<void> {
  status.value = 'loading'
  try {
    const env = await listSuites({
      // S7.0 口径:「我的用例集」= 我名下且未加入任何项目
      scope: 'private' as const,
      q: q.value.trim() || undefined,
      mode: modeFilter.value || undefined,
      page: page.value, page_size: pageSize.value,
    })
    items.value = env.items
    total.value = env.total
    // 末页被删空 → 回收到有效页(与 AdaptationCenter 批次表同款)
    if (env.items.length === 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(env.total / pageSize.value))
      return
    }
    status.value = 'ready'
  } catch {
    status.value = 'error'
  }
}

/** 行点击:进管理页;本人最近一次发起的运行失败 → 直接进运行记录页签。 */
function openSuite(s: SuiteSummary): void {
  const failed = s.latestRun
    && ['failed', 'error', 'halted'].includes(s.latestRun.status ?? '')
  void router.push(failed ? `/suites/${s.suiteId}?tab=runs` : `/suites/${s.suiteId}`)
}

function latestRunText(r: SuiteLatestRun): string {
  const t = r.finishedAt || r.createdAt
  const when = t ? shortDateTime(t) : ''
  // Suite 专属视图:只认 suite_graph 直接比较(N3 拆判定,评审 §3.2)
  const kind = r.kind === 'suite_graph' ? '编排' : '批次'
  return `${kind} · ${when}`
}

// ── 新建:直接进画布(原型 02→10);不落库,首次拖入才建草稿 ────
const creating = ref(false)
async function onCreate(): Promise<void> {
  if (creating.value) return
  creating.value = true
  try {
    await router.push('/suites/new')
  } finally {
    creating.value = false
  }
}

// ── 行内操作 ──────────────────────────────────────────────────
async function renameSuite(s: SuiteSummary): Promise<void> {
  const name = await promptAction('Suite 名称(1–128 字符)', '重命名 Suite',
    { inputValue: s.name })
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed || trimmed === s.name) return
  try {
    await patchSuite(s.suiteId, { name: trimmed })
    s.name = trimmed
    toast.success(`已重命名为 ${trimmed}`)
  } catch (e) {
    toast.error(`重命名失败:${(e as Error).message}`)
  }
}

async function removeSuite(s: SuiteSummary): Promise<void> {
  const ok = await confirmAction(
    `删除 Suite「${s.name}」?成员场景不受影响。`, '删除 Suite',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  if (!ok) return
  try {
    await deleteSuite(s.suiteId)
    items.value = items.value.filter((x) => x.suiteId !== s.suiteId)
    toast.success('Suite 已删除')
  } catch (e) {
    toast.error(`删除失败:${(e as Error).message}`)
  }
}

/** ⋯ 复制(02 规格):fork 端点属主自复制 —— 深拷贝含编排(约束 8),
 *  成员场景一并复制为副本;草稿由菜单禁用挡住。 */
async function copySuite(s: SuiteSummary): Promise<void> {
  try {
    const out = await forkPublicSuite(s.suiteId)
    toast.success(`已复制为「${out.suiteName}」`)
    void load()
  } catch (e) {
    toast.error(`复制失败:${(e as Error).message}`)
  }
}

/** ⋯ 发布(2026-10-10 补,对齐管理页口径):确认前按成员 visibility
 *  列出将被级联公开的成员(§7.9 不做静默级联),再调 publish。 */
async function publishSuite(s: SuiteSummary): Promise<void> {
  try {
    const d = await getSuite(s.suiteId)
    const privates = d.members.filter((m) => m.visibility !== 'public')
    const msg = privates.length
      ? `发布到公共库?以下 ${privates.length} 个未发布成员及其数据集将一并公开:${privates.map((m) => m.name).join('、')}`
      : '发布到公共库?所有成员均已公开。'
    const ok = await confirmAction(msg, '发布到公共库',
      { type: 'warning', confirmButtonText: '发布', cancelButtonText: '取消' })
    if (!ok) return
    const out = await postSuitePublish(s.suiteId)
    const cascaded = (out.publishedMembers ?? []).length
    toast.success(cascaded ? `已发布(级联公开了 ${cascaded} 个成员)` : '已发布到公共库')
    s.visibility = 'public'
  } catch (e) {
    toast.error(`发布失败:${(e as Error).message}`)
  }
}

async function unpublishSuite(s: SuiteSummary): Promise<void> {
  const ok = await confirmAction('下架 Suite?成员场景的公共状态独立保留。', '下架为私有',
    { type: 'warning', confirmButtonText: '下架', cancelButtonText: '取消' })
  if (!ok) return
  try {
    await deleteSuitePublish(s.suiteId)
    toast.success('已下架为私有')
    s.visibility = 'private'
  } catch (e) {
    toast.error(`下架失败:${(e as Error).message}`)
  }
}

// ── 运行(预检 → 分流跳转)────────────────────────────────────
const preflightOpen = ref(false)
const preflightId = ref(0)
const running = ref(false)

function openPreflight(s: SuiteSummary): void {
  preflightId.value = s.suiteId
  preflightOpen.value = true
}

async function onRun(): Promise<void> {
  if (!preflightId.value || running.value) return
  running.value = true
  try {
    const r = await runSuite(preflightId.value)
    preflightOpen.value = false
    if ('started' in r) {
      if (r.skipped.length) toast.error(`${r.skipped.length} 个成员被跳过(原因见批次)`)
      toast.success(`批次已发起:${r.started.length} 个执行`)
      void router.push(executionsBatchUrl(r.batchId))
    } else {
      toast.success(`编排执行已发起(#${r.executionId})`)
      void router.push(`/executions/${r.executionId}`)
    }
  } catch (e) {
    const det = suiteErrDetail(e)
    toast.error(`运行失败:${(det?.message as string) || (e as Error).message}`)
  } finally {
    running.value = false
  }
}

// ── 分享(列表行直达;口径同管理页 ⋯ 菜单:非公共、草稿禁用)─────
const shareOpen = ref(false)
const shareTarget = ref<SuiteSummary | null>(null)

function openShare(s: SuiteSummary): void {
  shareTarget.value = s
  shareOpen.value = true
}

onMounted(() => void load())
</script>

<style scoped>
/* Suite 表行含描述行(~72px/行):列表卡定高档 ≈ 10.5 行(分页位置轮) */
.slib { --lib-card-max: 51.25rem; }
.slib { display: flex; flex-direction: column; gap: 0.875rem; }
.slib-toolbar { display: flex; gap: 0.625rem; align-items: center; flex-wrap: wrap; }
.slib-search {
  flex: none; width: 18.75rem; padding: 0.5rem 0.75rem; font-size: 0.8125rem;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 0.5rem;
  background: transparent; color: inherit;
}
.slib-modes {
  display: inline-flex; border: 1px solid rgb(100 116 139 / 25%);
  border-radius: 0.5rem; overflow: hidden;
}
.slib-mode {
  padding: 0.375rem 0.75rem; font-size: 0.78125rem; cursor: pointer;
  border: none; background: transparent; color: inherit;
  border-right: 1px solid rgb(100 116 139 / 18%); white-space: nowrap;
}
.slib-mode:last-child { border-right: none; }
.slib-mode.on { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.slib-public-link {
  font-size: 0.78125rem; color: var(--accent); text-decoration: none; white-space: nowrap;
  padding: 0.4375rem 0.625rem; border-radius: 0.5rem; border: 1px solid var(--accent-soft-border);
}
.slib-create {
  margin-left: auto; padding: 0.5rem 0.875rem; font-size: 0.8125rem; font-weight: 600;
  white-space: nowrap; border-radius: 0.5rem; border: none; cursor: pointer;
  color: #fff; background: var(--accent);
}
.slib-create:hover { background: var(--accent-hover); }
.slib-create:disabled { opacity: .5; cursor: not-allowed; }
/* overflow 交给全局 .lib-card(卡内滑轨,分页位置轮);这里只压边框圆角 */
.lib-card { border: 1px solid rgb(100 116 139 / 22%); border-radius: 0.625rem; }
.slib-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
.slib-table th {
  text-align: left; font-weight: 500; font-size: 0.75rem; color: rgb(100 116 139);
  padding: 0.5rem 0.875rem; background: rgb(100 116 139 / 6%);
  border-bottom: 1px solid rgb(100 116 139 / 15%);
}
.slib-row { cursor: pointer; }
.slib-row td { padding: 0.5625rem 0.875rem; border-bottom: 1px solid rgb(100 116 139 / 10%); }
.slib-row:hover { background: rgb(59 130 246 / 5%); }
.slib-row:last-child td { border-bottom: none; }
.sl-name { display: flex; align-items: center; gap: 0.375rem; min-width: 0; }
.nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sl-sid { font-size: 0.71875rem; color: rgb(100 116 139); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-chip {
  flex: none; font-size: 0.6875rem; padding: 0.125rem 0.5rem; border-radius: 62.4375rem;
  color: var(--sl-warn); background: rgb(245 158 11 / 10%);
  border: 1px solid rgb(245 158 11 / 40%);
}
/* proj-chip / pub-chip 样式随「全员视角」镜头退役移除(私有桶恒不可达) */
.mode-chip {
  font-size: 0.71875rem; padding: 0.125rem 0.5625rem; border-radius: 62.4375rem;
  white-space: nowrap;
  color: rgb(100 116 139); background: rgb(100 116 139 / 8%);
  border: 1px solid rgb(100 116 139 / 22%);
}
.mode-chip.chain, .mode-chip.fanout, .mode-chip.compose {
  color: #6d28d9; background: rgb(139 92 246 / 8%); border-color: rgb(139 92 246 / 30%);
}
.num { font-size: 0.78125rem; }
.muted { color: rgb(100 116 139); font-size: 0.75rem; }
.last-run { display: inline-flex; align-items: center; gap: 0.375rem; font-size: 0.75rem; color: rgb(100 116 139); }
.dot { width: 0.5625rem; height: 0.5625rem; border-radius: 0.1875rem; display: inline-block; }
.dot.ok { background: rgb(34 197 94 / 75%); }
.dot.bad { background: rgb(220 38 38 / 80%); }
.dot.run { background: rgb(59 130 246 / 80%); }
.dot.muted { background: rgb(100 116 139 / 35%); }
.ops { display: flex; gap: 0.5rem; align-items: center; }
.run-btn {
  font-size: 0.75rem; padding: 0.25rem 0.75rem; border-radius: 0.375rem; cursor: pointer;
  color: var(--accent); background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.run-btn:disabled { opacity: .4; cursor: not-allowed; }
.more-btn {
  width: 1.625rem; height: 1.5rem; border-radius: 0.375rem; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
  font-size: 0.75rem; padding: 0;
}
.ref-in-badge {
  font-size: 0.6875rem; padding: 0.125rem 0.5rem; border-radius: 62.4375rem; margin-left: 0.375rem;
  color: var(--sl-ok); background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); font-weight: 400;
}
.cta { color: var(--accent); background: none; border: none; cursor: pointer; font-size: 0.8125rem; }
.card-empty { padding: 2.125rem 0; text-align: center; color: rgb(100 116 139); font-size: 0.8125rem; }
.sl-menu-item.danger { color: var(--sl-bad, var(--sl-bad)); }
</style>
