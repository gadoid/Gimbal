<!-- SuiteLibrary.vue — 我的用例集(原型 02,Suite 层重构第 2 步;
     2026-10-10 IA 调整:侧栏「用例集」组,页面更名)。
     页头 + 浏览镜头(admin 全员视角)/ 搜索 / 模式筛选 + 表格
     (Suite · 模式 · 成员 · 最近运行 · 操作)。草稿带「草稿」标记;
     「共享给我的」独立分区(§7.11);「公共用例集」链接到独立公共页。
     行点击进 20(本人最近一次发起的运行失败则进 21);行内「运行」
     开 30 预检;⋯ 重命名 / 复制 / 分享 / 发布(下架)/ 删除。 -->
<template>
  <section class="slib">
    <PageHead icon="stack" title="我的用例集" :subtitle="subtitle" />

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
      <button
        v-if="lensAvailable"
        type="button"
        class="slib-lens"
        :class="{ on: lensAll }"
        :data-testid="lensAll ? 'suite-lens-all-on' : 'suite-lens-all-off'"
        :title="lensAll
          ? '当前:全员视角 —— 点按回「我的」'
          : '当前:我的 —— 点按切「全员视角」看全部 Suite'"
        @click="toggleLens"
      >{{ lensAll ? '◉ 全员视角' : '○ 全员视角' }}</button>
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
    <div v-else-if="!filtered.length" class="card-empty">
      <p>还没有 Suite —— 新建一个,把场景归组并编排它们怎么跑</p>
    </div>

    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>Suite</th>
            <th style="width:100px">模式</th>
            <th style="width:70px">成员</th>
            <th v-if="lensAll" style="width:80px">归属</th>
            <th style="width:170px">最近运行</th>
            <th style="width:170px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in filtered"
            :key="s.suiteId"
            class="slib-row"
            :data-testid="`suite-row-${s.suiteId}`"
            @click="openSuite(s)"
          >
            <td>
              <div class="sl-name">
                <span class="nm">{{ s.name }}</span>
                <span v-if="s.isDraft" class="draft-chip" title="草稿:不出现在发布 / 分享;空草稿 30 天自动清理">草稿</span>
                <span v-if="s.visibility === 'public'" class="pub-chip" title="已发布到公共库">公共</span>
                <span
                  v-if="sharedOutSuites.has(s.suiteId)"
                  class="ref-badge"
                  title="此 Suite 正被引用分享(改动即时生效)"
                >已引用分享</span>
              </div>
              <div class="sl-sid">{{ s.description || '—' }}</div>
            </td>
            <td><span class="mode-chip" :class="s.mode">{{ MODE_LABEL[s.mode] || s.mode }}</span></td>
            <td><span class="num">{{ s.memberCount }}</span></td>
            <td v-if="lensAll">
              <span v-if="s.visibility === 'public'" class="pub-chip">公共</span>
              <span v-else class="muted">—</span>
            </td>
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
                  <DropdownMenuItem class="sl-menu-item danger" @click="removeSuite(s)">删除</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 「共享给我的」独立分区(§7.11:不进镜头) -->
    <div v-if="sharedInSuites.length" class="shared-in" data-testid="shared-in-suites">
      <p class="shared-in-label">共享给我的(引用)</p>
      <div
        v-for="r in sharedInSuites"
        :key="r.id"
        class="shared-row"
        :data-testid="`shared-suite-${r.suiteId}`"
      >
        <span class="su-name">
          {{ r.suiteName || `#${r.suiteId}` }}
          <span class="ref-in-badge">引用 · 来自 {{ r.grantedByName }}</span>
        </span>
        <span class="su-members">{{ r.memberCount ?? '—' }} 个场景</span>
        <button class="cta" :data-testid="`shared-suite-open-${r.suiteId}`"
                @click="$router.push(`/suites/${r.suiteId}`)">打开</button>
        <button class="unsub-btn" :data-testid="`shared-suite-unsub-${r.suiteId}`"
                @click="unsubscribe(r)">退订</button>
      </div>
    </div>

    <!-- 运行预检(30):从列表行发起 -->
    <SuiteRunPreflight
      v-model:open="preflightOpen"
      :suite-id="preflightId"
      :running="running"
      @run="onRun"
      @locate="() => preflightOpen = false"
    />

    <!-- 分享弹窗(P2 组件;changed 后刷新「已引用分享」徽标) -->
    <ShareDialog
      v-model:open="shareOpen"
      :resource="shareTarget ? {
        type: 'suite' as const,
        id: String(shareTarget.suiteId),
        name: shareTarget.name,
      } : null"
      @changed="void loadShareBadges"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SuiteRunPreflight from '@/components/suites/SuiteRunPreflight.vue'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  deleteSuite, deleteSuitePublish, forkPublicSuite, getSuite, listSuites,
  patchSuite, postSuitePublish, runSuite, suiteErrDetail,
  type SuiteLatestRun, type SuiteSummary,
} from '@/api/suites'
import { listShares, deleteShare, type ShareRefItem } from '@/api/shares'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'
import { promptAction, confirmAction } from '@/utils/confirmAction'
import { executionsBatchUrl } from '@/utils/links'
import { MODE_LABEL, runStatusTone } from '@/utils/suiteStructure'

const router = useRouter()
const auth = useAuthStore()

const q = ref('')
const status = ref<'loading' | 'ready' | 'error'>('loading')
const items = ref<SuiteSummary[]>([])
const modeFilter = ref('')

// 浏览镜头(§5.1):默认我的;admin 可切全员视角(记本地)
const lensAll = ref(false)
const lensAvailable = computed(() => !!auth.isAdmin)
function toggleLens(): void {
  lensAll.value = !lensAll.value
  void load()
}

const modeFilters = [
  { key: '', label: '全部' },
  { key: 'aggregate', label: MODE_LABEL.aggregate },
  { key: 'chain', label: MODE_LABEL.chain },
  { key: 'fanout', label: MODE_LABEL.fanout },
  { key: 'compose', label: MODE_LABEL.compose },
]

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return items.value
    .filter((s) => !modeFilter.value || s.mode === modeFilter.value)
    .filter((s) => !needle
      || s.name.toLowerCase().includes(needle)
      || (s.description || '').toLowerCase().includes(needle))
})

const subtitle = computed(() => lensAll.value
  ? `一组场景及其运行编排 · 共 ${filtered.value.length} 个 · 全员视角`
  : `一组场景及其运行编排 · 共 ${filtered.value.length} 个 · 你创建的(草稿也在这里,带「草稿」标记)`)

async function load(): Promise<void> {
  status.value = 'loading'
  try {
    const env = await listSuites({
      scope: lensAll.value ? 'all' : 'mine', page_size: 100,
    })
    items.value = env.items
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

// ── P2 徽标 + 共享给我的(§7.11)────────────────────────────────
const sharedOutSuites = ref(new Set<number>())
const sharedInSuites = ref<ShareRefItem[]>([])

// ── 分享(列表行直达;口径同管理页 ⋯ 菜单:非公共、草稿禁用)─────
const shareOpen = ref(false)
const shareTarget = ref<SuiteSummary | null>(null)

function openShare(s: SuiteSummary): void {
  shareTarget.value = s
  shareOpen.value = true
}

async function loadShareBadges() {
  try {
    const [out, inn] = await Promise.all([
      listShares({ direction: 'out' }).catch(() => []),
      listShares({ direction: 'in', resourceType: 'suite' }).catch(() => []),
    ])
    sharedOutSuites.value = new Set(
      out.filter((r) => r.resourceType === 'suite' && r.suiteId)
        .map((r) => r.suiteId as number))
    sharedInSuites.value = inn
  } catch { /* 静默留白 */ }
}

async function unsubscribe(r: ShareRefItem) {
  try {
    await deleteShare(r.id)
    sharedInSuites.value = sharedInSuites.value.filter((x) => x.id !== r.id)
    toast.success('已退订该引用')
  } catch (e) {
    toast.error(`退订失败:${(e as Error).message}`)
  }
}

onMounted(() => void load())
onMounted(() => void loadShareBadges())
</script>

<style scoped>
.slib { display: flex; flex-direction: column; gap: 14px; }
.slib-toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.slib-search {
  flex: none; width: 300px; padding: 8px 12px; font-size: 13px;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 8px;
  background: transparent; color: inherit;
}
.slib-modes {
  display: inline-flex; border: 1px solid rgb(100 116 139 / 25%);
  border-radius: 8px; overflow: hidden;
}
.slib-mode {
  padding: 6px 12px; font-size: 12.5px; cursor: pointer;
  border: none; background: transparent; color: inherit;
  border-right: 1px solid rgb(100 116 139 / 18%); white-space: nowrap;
}
.slib-mode:last-child { border-right: none; }
.slib-mode.on { background: var(--accent-soft); color: #4338ca; font-weight: 600; }
.slib-lens {
  flex: none; font-size: 12px; padding: 7px 12px; border-radius: 8px;
  cursor: pointer; color: var(--sl-ink-soft, #64748b); background: transparent;
  border: 1px solid rgb(100 116 139 / 35%); white-space: nowrap;
}
.slib-lens.on {
  color: #1d4ed8; border-color: rgb(59 130 246 / 55%);
  background: rgb(59 130 246 / 10%);
}
.slib-public-link {
  font-size: 12.5px; color: #4338ca; text-decoration: none; white-space: nowrap;
  padding: 7px 10px; border-radius: 8px; border: 1px solid var(--accent-soft-border);
}
.slib-create {
  margin-left: auto; padding: 8px 14px; font-size: 13px; font-weight: 600;
  white-space: nowrap; border-radius: 8px; border: none; cursor: pointer;
  color: #fff; background: #4338ca;
}
.slib-create:hover { background: var(--accent-hover); }
.slib-create:disabled { opacity: .5; cursor: not-allowed; }
.lib-card { border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px; overflow: hidden; }
.slib-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.slib-table th {
  text-align: left; font-weight: 500; font-size: 12px; color: rgb(100 116 139);
  padding: 8px 14px; background: rgb(100 116 139 / 6%);
  border-bottom: 1px solid rgb(100 116 139 / 15%);
}
.slib-row { cursor: pointer; }
.slib-row td { padding: 9px 14px; border-bottom: 1px solid rgb(100 116 139 / 10%); }
.slib-row:hover { background: rgb(59 130 246 / 5%); }
.slib-row:last-child td { border-bottom: none; }
.sl-name { display: flex; align-items: center; gap: 6px; min-width: 0; }
.nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sl-sid { font-size: 11.5px; color: rgb(100 116 139); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-chip {
  flex: none; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  color: #b45309; background: rgb(245 158 11 / 10%);
  border: 1px solid rgb(245 158 11 / 40%);
}
.pub-chip {
  flex: none; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  color: #15803d; background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%);
}
.ref-badge {
  flex: none; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  color: #6d28d9; background: rgb(139 92 246 / 10%);
  border: 1px solid rgb(139 92 246 / 40%);
}
.mode-chip {
  font-size: 11.5px; padding: 2px 9px; border-radius: 999px;
  white-space: nowrap;
  color: rgb(100 116 139); background: rgb(100 116 139 / 8%);
  border: 1px solid rgb(100 116 139 / 22%);
}
.mode-chip.chain, .mode-chip.fanout, .mode-chip.compose {
  color: #6d28d9; background: rgb(139 92 246 / 8%); border-color: rgb(139 92 246 / 30%);
}
.num { font-size: 12.5px; }
.muted { color: rgb(100 116 139); font-size: 12px; }
.last-run { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: rgb(100 116 139); }
.dot { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }
.dot.ok { background: rgb(34 197 94 / 75%); }
.dot.bad { background: rgb(220 38 38 / 80%); }
.dot.run { background: rgb(59 130 246 / 80%); }
.dot.muted { background: rgb(100 116 139 / 35%); }
.ops { display: flex; gap: 8px; align-items: center; }
.run-btn {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.run-btn:disabled { opacity: .4; cursor: not-allowed; }
.more-btn {
  width: 26px; height: 24px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
  font-size: 12px; padding: 0;
}
.shared-in { margin-top: 22px; }
.shared-in-label { font-size: 13px; color: rgb(100 116 139); margin: 8px 0; }
.shared-row {
  display: grid; grid-template-columns: minmax(160px, 1fr) auto auto auto;
  gap: 12px; align-items: center; padding: 9px 14px;
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  margin-bottom: 6px;
}
.su-name { font-weight: 600; font-size: 13px; }
.su-members { font-size: 12px; color: rgb(100 116 139); white-space: nowrap; }
.ref-in-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 999px; margin-left: 6px;
  color: #15803d; background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); font-weight: 400;
}
.cta { color: #4338ca; background: none; border: none; cursor: pointer; font-size: 13px; }
.unsub-btn {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #b45309; background: rgb(245 158 11 / 8%);
  border: 1px solid rgb(245 158 11 / 35%);
}
.card-empty { padding: 34px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.sl-menu-item.danger { color: var(--sl-bad, #dc2626); }
</style>
