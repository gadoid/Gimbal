<!-- SuiteManage.vue — Suite 管理页(原型 20 编排页签 + 21 运行记录页签)。
     单实体重构后的详情页:模式条 + 三栏(我的场景抽屉 / 前置·主体·后置 /
     运行参数·判定门·横切断言);800ms 防抖自动保存(rev 乐观锁,冲突
     409 拉最新);只读态(ref/public);被引用/公共的首改提示 + 常驻横幅
     (§7.11);三处「运行」先过预检(30)。取代原 SuiteDetail.vue。 -->
<template>
  <section v-if="status === 'loading'" class="sm-loading">加载中…</section>
  <section v-else-if="status === 'error'" class="sm-empty">
    <p>加载失败或不存在</p>
    <button type="button" class="btn-primary" @click="load">重试</button>
  </section>

  <section v-else-if="detail" class="sm" data-testid="suite-manage">
    <!-- 页头 -->
    <div class="sm-head">
      <PageBack to="/suites" label="Suite" testid="suite-manage-back" />
      <div class="sm-head-main">
        <div class="sm-title-row">
          <span class="icon-badge" aria-hidden="true"><SlibIcon name="stack" :size="15" /></span>
          <h1 class="sm-title" data-testid="suite-manage-name">
            {{ detail.name }}
            <span v-if="detail.isDraft" class="sm-draft-chip" title="草稿:不出现在发布/分享,空草稿 30 天自动清理">草稿</span>
            <span v-if="detail.visibility === 'public'" class="sm-pub-chip">公共</span>
            <span v-if="detail.access === 'ref'" class="sm-ref-chip">引用</span>
          </h1>
          <p class="sm-meta">
            {{ detail.members.length }} 个成员 ·
            <template v-if="saveState === 'saving'">保存中…</template>
            <template v-else-if="saveState === 'dirty'">未保存的改动…</template>
            <template v-else>已自动保存 {{ savedAt }}</template>
          </p>
        </div>
      </div>
      <div class="sm-head-actions">
        <button
          v-if="canRun"
          type="button"
          class="sm-run"
          data-testid="suite-manage-run"
          :disabled="!detail.members.length"
          @click="openPreflight"
        >
          <span class="sm-run-main">▶ 运行</span>
          <span class="sm-run-sub">{{ channelDesc }}</span>
        </button>
        <button
          v-else-if="detail.access === 'public'"
          type="button"
          class="btn-secondary"
          data-testid="suite-public-fork"
          @click="forkPublic"
        >复制到我的</button>
        <button
          type="button"
          class="sm-more"
          data-testid="suite-manage-menu"
          @click="menuOpen = !menuOpen"
        >⋯</button>
      </div>
    </div>

    <!-- 只读 / 防误伤横幅 -->
    <div v-if="readonlyBanner" class="sm-banner" :class="readonlyBanner.tone" data-testid="suite-readonly-banner">
      <span>{{ readonlyBanner.text }}</span>
      <span v-if="detail.access === 'ref'" class="sm-banner-ops">
        <button type="button" data-testid="suite-ref-fork" @click="forkRef">转为副本</button>
        <button type="button" data-testid="suite-ref-unsub" @click="unsubRef">退订</button>
      </span>
    </div>
    <div v-else-if="liveBanner" class="sm-banner warn" data-testid="suite-live-banner">
      {{ liveBanner }}
    </div>
    <div v-if="conflictFlag" class="sm-banner bad" data-testid="suite-conflict-banner">
      Suite 已被其他页面修改 —— 已拉取最新编排,请基于最新内容再改
    </div>

    <!-- 草稿转正 -->
    <div v-if="detail.isDraft && canEdit" class="sm-banner draft" data-testid="suite-draft-banner">
      这是个草稿。命名后转正(转正后才可发布 / 分享)。
      <button type="button" data-testid="suite-draft-name" @click="finishDraft">完成编排 · 命名转正</button>
    </div>

    <!-- 页签 -->
    <Tabs v-model="tab" class="sm-tabs">
      <TabsList>
        <TabsTrigger value="compose">编排</TabsTrigger>
        <TabsTrigger value="runs">运行记录</TabsTrigger>
      </TabsList>

      <TabsContent value="compose" class="sm-pane">
        <ModeBar
          :mode="mode" :readonly="!canEdit"
          @change="switchMode" @guide="guideOpen = true"
          @open-canvas="openCanvas"
        />
        <div class="sm-cols">
          <ScenarioDrawer
            v-if="canEdit"
            :member-ids="memberIds"
            @add="onDrawerAdd"
          />
          <MemberZone
            :detail="zoneDetail"
            :config="config"
            :readonly="!canEdit"
            :highlighted="highlightId"
            :run-cap="runCap"
            @add-member="onDropAdd"
            @remove-member="onRemoveMember"
            @move-member="onMoveMember"
            @set-role="onSetRole"
            @unit-config="onUnitConfig"
            @stepto="stepTo = $event"
          />
          <GatesPanel
            :config="config"
            :members="mainMembers"
            :roster="detail.members"
            :mode="mode"
            :readonly="!canEdit"
            :run-cap="runCap"
            @patch="onConfigPatch"
          />
        </div>
      </TabsContent>

      <TabsContent value="runs" class="sm-pane" :force-mount="true">
        <SuiteRunsTab
          v-show="tab === 'runs'"
          ref="runsTab"
          :suite-id="detail.suiteId"
          :members="detail.members"
          @locate="locateMember"
          @reran="onReran"
        />
      </TabsContent>
    </Tabs>

    <!-- ⋯ 菜单 -->
    <div v-if="menuOpen" class="sm-menu-mask" @click="menuOpen = false" />
    <div v-if="menuOpen" class="sm-menu" data-testid="suite-manage-menu-panel">
      <button v-if="canEdit" type="button" @click="rename">重命名</button>
      <button
        v-if="canShare && detail.visibility !== 'public'"
        type="button" :disabled="detail.isDraft"
        :title="detail.isDraft ? '草稿不可分享 —— 完成编排后可分享' : ''"
        @click="shareOpen = true"
      >分享…</button>
      <button
        v-if="(detail.access === 'owner' || detail.access === 'admin') && detail.visibility !== 'public'"
        type="button" :disabled="detail.isDraft"
        :title="detail.isDraft ? '草稿不可发布 —— 完成编排后可发布' : ''"
        data-testid="suite-publish-menu"
        @click="publish"
      >发布到公共库</button>
      <button
        v-else-if="(detail.access === 'owner' || detail.access === 'admin') && detail.visibility === 'public'"
        type="button" @click="unpublish"
      >下架为私有</button>
      <button v-if="canEdit" type="button" class="danger" data-testid="suite-delete" @click="remove">删除</button>
    </div>

    <!-- 运行预检(30) -->
    <SuiteRunPreflight
      v-model:open="preflightOpen"
      :suite-id="detail.suiteId"
      :running="running"
      @run="onRun"
      @locate="locateFromPreflight"
    />

    <!-- 四种结构说明(原型 11,画布/管理页共用) -->
    <StructureGuideDialog v-model="guideOpen" />

    <!-- 分享弹窗(P2 已落地组件) -->
    <ShareDialog
      v-model:open="shareOpen"
      :resource="shareResource"
      @changed="void loadShareMeta"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import ModeBar from '@/components/suites/ModeBar.vue'
import ScenarioDrawer from '@/components/suites/ScenarioDrawer.vue'
import MemberZone from '@/components/suites/MemberZone.vue'
import GatesPanel from '@/components/suites/GatesPanel.vue'
import SuiteRunPreflight from '@/components/suites/SuiteRunPreflight.vue'
import StructureGuideDialog from '@/components/suites/StructureGuideDialog.vue'
import PageBack from '@/components/chrome/PageBack.vue'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import SuiteRunsTab from '@/components/suites/SuiteRunsTab.vue'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import {
  deleteSuite, deleteSuitePublish, forkPublicSuite, getSuite,
  patchSuite, postSuitePublish, putSuiteComposition, runSuite,
  suiteErrDetail,
  type MemberRole, type SuiteDetail, type SuiteMode, type SuiteModeConfig,
  type SuiteUnitConfig,
} from '@/api/suites'
import { listShares, forkShare, deleteShare } from '@/api/shares'
import { toast } from '@/utils/toast'
import { promptAction, confirmAction } from '@/utils/confirmAction'
import { executionsBatchUrl } from '@/utils/links'
import { modeMeta } from '@/utils/suiteStructure'

const AUTOSAVE_MS = 800
const RUN_CAP = 1000
const runCap = RUN_CAP

const route = useRoute()
const router = useRouter()

const status = ref<'loading' | 'ready' | 'error'>('loading')
const detail = ref<SuiteDetail | null>(null)
const tab = ref((route.query.tab === 'runs' ? 'runs' : 'compose'))
const menuOpen = ref(false)
const shareOpen = ref(false)
const preflightOpen = ref(false)
const guideOpen = ref(false)

/** 大改依赖结构 → 画布(12);保存后回到管理页。 */
function openCanvas(): void {
  if (!detail.value) return
  void router.push(`/suites/${detail.value.suiteId}/compose`)
}
const running = ref(false)

// ── 可编辑本地态(显式突变 → 标脏;load 时整包替换)──────────────
const mode = ref<SuiteMode>('aggregate')
const members = ref<{ scenarioId: string; role: MemberRole }[]>([])
const config = ref<SuiteModeConfig>({})
const stepTo = ref<string | null>(null)
const highlightId = ref<string | null>(null)

const saveState = ref<'clean' | 'dirty' | 'saving'>('clean')
const savedAt = ref('—')
const conflictFlag = ref(false)
let saveTimer: number | null = null
let suppressSave = false

const canEdit = computed(() => !!detail.value?.canEdit)
const canRun = computed(() => !!detail.value?.canRun)
const canShare = computed(() => !!detail.value?.canShare)
const memberIds = computed(() => new Set(members.value.map((m) => m.scenarioId)))
const mainMembers = computed(() =>
  members.value.filter((m) => m.role === 'main').map((m) => m.scenarioId)
    .map((id) => ({ scenarioId: id })))
const channelDesc = computed(() => {
  if (!detail.value) return ''
  const m = modeMeta(mode.value)
  const n = detail.value.members.length
  return mode.value === 'aggregate' ? `聚合 · ${n} 个独立执行 · 一个批次` : m.channel
})

/** MemberZone 需要带名称的成员;从 detail 同步顺序/角色到本地态。 */
const zoneDetail = computed<SuiteDetail>(() => {
  const d = detail.value as SuiteDetail
  const byId = new Map(d.members.map((m) => [m.scenarioId, m]))
  return {
    ...d,
    mode: mode.value,
    members: members.value
      .map((m) => byId.get(m.scenarioId))
      .filter((m): m is SuiteDetail['members'][number] => !!m)
      .map((m) => ({ ...m, role: members.value.find(
        (x) => x.scenarioId === m.scenarioId)?.role ?? m.role })),
  }
})

async function load(): Promise<void> {
  status.value = 'loading'
  try {
    const d = await getSuite(Number(route.params.id))
    applyDetail(d)
    status.value = 'ready'
    void loadShareMeta()
  } catch {
    status.value = 'error'
  }
}

function applyDetail(d: SuiteDetail): void {
  suppressSave = true
  detail.value = d
  mode.value = (d.mode as SuiteMode) || 'aggregate'
  members.value = d.members.map((m) => ({ scenarioId: m.scenarioId, role: m.role }))
  const cfg: SuiteModeConfig = { ...(d.modeConfig ?? {}) }
  delete cfg.draft
  config.value = cfg
  suppressSave = false
  saveState.value = 'clean'
}

function markDirty(): void {
  if (suppressSave) return
  saveState.value = 'dirty'
  if (saveTimer !== null) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save() }, AUTOSAVE_MS)
}

async function save(publishUnpublished = false): Promise<void> {
  const d = detail.value
  if (!d || !canEdit.value || saveState.value !== 'dirty') return
  saveState.value = 'saving'
  try {
    // 被引用 / 公共 Suite 首改提示(§7.11):第一次落盘前弹一次
    if (!sessionConfirmed && liveBanner.value) {
      const ok = await confirmFirstEdit()
      if (!ok) {
        saveState.value = 'dirty'
        return
      }
    }
    const out = await putSuiteComposition(d.suiteId, {
      rev: d.rev, mode: mode.value, members: members.value,
      modeConfig: config.value, publishUnpublished,
    })
    detail.value = out
    const cfg: SuiteModeConfig = { ...(out.modeConfig ?? {}) }
    delete cfg.draft
    config.value = cfg
    savedAt.value = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit', minute: '2-digit' })
    saveState.value = 'clean'
    conflictFlag.value = false
  } catch (e) {
    const det = suiteErrDetail(e)
    if (det?.code === 'suite_rev_conflict') {
      conflictFlag.value = true
      toast.error('Suite 已被修改,已拉取最新编排(你的未保存改动被放弃)')
      if (det.latest) applyDetail(det.latest as SuiteDetail)
      else void load()
      return
    }
    if (det?.code === 'suite_member_publish_required') {
      const pending = (det.pendingPublish as string[]) ?? []
      const ok = await confirmAction(
        `这是公共 Suite:加入的私有成员及其数据集将一并公开(${pending.join('、')})。确认公开并加入?`,
        '发布确认',
        { type: 'warning', confirmButtonText: '公开并加入', cancelButtonText: '不加入' },
      )
      if (ok) {
        saveState.value = 'dirty'
        await save(true)
      } else {
        // 不公开 → 回滚本次成员改动到服务端现状
        await load()
        toast.info('已取消:未加入该成员')
      }
      return
    }
    saveState.value = 'dirty'
    toast.error(`保存失败:${(det?.message as string) || (e as Error).message}`)
    if (saveTimer === null) {
      saveTimer = window.setTimeout(() => { saveTimer = null; void save() }, 3000)
    }
  }
}

// ── 成员 / 单元 / 配置突变 ─────────────────────────────────────
function onDrawerAdd(scenarioId: string, role: MemberRole = 'main'): void {
  if (memberIds.value.has(scenarioId)) return
  members.value = [...members.value, { scenarioId, role }]
  markDirty()
}

function onDropAdd(scenarioId: string, role: MemberRole): void {
  onDrawerAdd(scenarioId, role)
}

function onRemoveMember(scenarioId: string): void {
  members.value = members.value.filter((m) => m.scenarioId !== scenarioId)
  const units = { ...(config.value.units ?? {}) }
  delete units[scenarioId]
  const cfg = { ...config.value, units }
  for (const [id, u] of Object.entries(units)) {
    if (u.needs?.includes(scenarioId)) {
      units[id] = { ...u, needs: u.needs.filter((n) => n !== scenarioId) }
    }
  }
  config.value = cfg
  markDirty()
}

function onMoveMember(scenarioId: string, delta: number): void {
  const list = members.value.slice()
  const idx = list.findIndex((m) => m.scenarioId === scenarioId)
  const j = idx + delta
  if (idx < 0 || j < 0 || j >= list.length) return
  ;[list[idx], list[j]] = [list[j], list[idx]]
  members.value = list
  markDirty()
}

function onSetRole(scenarioId: string, role: MemberRole): void {
  members.value = members.value.map((m) =>
    m.scenarioId === scenarioId ? { ...m, role } : m)
  markDirty()
}

function onUnitConfig(scenarioId: string, patch: Partial<SuiteUnitConfig>): void {
  const units = { ...(config.value.units ?? {}) }
  units[scenarioId] = { ...(units[scenarioId] ?? {}), ...patch }
  config.value = { ...config.value, units }
  markDirty()
}

function onConfigPatch(patch: Partial<SuiteModeConfig>): void {
  config.value = { ...config.value, ...patch }
  markDirty()
}

// ── 模式切换(交互规则:切聚合丢 needs 先确认)───────────────────
async function switchMode(next: SuiteMode): Promise<void> {
  if (next === mode.value || !detail.value) return
  const units = config.value.units ?? {}
  const needsEdges = Object.entries(units)
    .filter(([, u]) => (u.needs?.length ?? 0) > 0)
  if (mode.value === 'compose' && next !== 'compose' && needsEdges.length) {
    const affected = needsEdges.map(([id]) => id).join('、')
    const ok = await confirmAction(
      `切换到「${modeMeta(next).label.replace(/^\S+\s/, '')}」会丢弃已有连线(needs),受影响单元:${affected}。继续?`,
      '切换模式',
      { type: 'warning', confirmButtonText: '切换并丢弃连线', cancelButtonText: '取消' },
    )
    if (!ok) return
  }
  const nextUnits: Record<string, SuiteUnitConfig> = {}
  for (const [id, u] of Object.entries(units)) {
    nextUnits[id] = next === 'compose' ? u : { ...u, needs: [] }
  }
  mode.value = next
  config.value = { ...config.value, units: nextUnits }
  markDirty()
}

// ── 运行(先过预检;聚合 → 批次视图,编排 → 执行详情)────────────
function openPreflight(): void {
  if (saveState.value === 'dirty') void save()
  preflightOpen.value = true
}

async function onRun(): Promise<void> {
  const d = detail.value
  if (!d || running.value) return
  running.value = true
  try {
    if (saveState.value === 'dirty') await save()
    const control: { only?: string[]; toNode?: string } = {}
    if (mode.value === 'chain' && stepTo.value) control.toNode = stepTo.value
    const r = await runSuite(d.suiteId, Object.keys(control).length ? control : undefined)
    preflightOpen.value = false
    if ('started' in r) {
      if (r.skipped.length) toast.error(`${r.skipped.length} 个成员被跳过(原因见批次)`)
      toast.success(`批次已发起:${r.started.length} 个执行`)
      void router.push(executionsBatchUrl(r.batchId))
    } else {
      toast.success(`编排执行已发起(#${r.executionId},${r.units} 个单元)`)
      void router.push(`/executions/${r.executionId}`)
    }
  } catch (e) {
    const det = suiteErrDetail(e)
    toast.error(`运行失败:${(det?.message as string) || (e as Error).message}`)
  } finally {
    running.value = false
  }
}

// ── 定位(预检 / 运行记录 → 编排页签高亮成员)───────────────────
function locateMember(scenarioId: string): void {
  if (!scenarioId) return
  tab.value = 'compose'
  highlightId.value = scenarioId
  window.setTimeout(() => { highlightId.value = null }, 2500)
}

function locateFromPreflight(scenarioId: string): void {
  preflightOpen.value = false
  locateMember(scenarioId)
}

function onReran(r: { executionId: number }): void {
  void router.push(`/executions/${r.executionId}`)
}

// ── 引用 / 公共横幅与首改提示(§7.11 / D-1)────────────────────
const referrers = ref<{ name: string; shareId: number }[]>([])
const shareIn = ref<{ id: number; grantedByName: string } | null>(null)
let sessionConfirmed = false

const liveBanner = computed<string | null>(() => {
  const d = detail.value
  if (!d || d.access !== 'owner') return null
  if (d.visibility === 'public') return '此 Suite 已公开,改动立即对所有人可见'
  if (referrers.value.length) {
    return `此 Suite 正被 ${referrers.value.length} 人引用(${referrers.value.map((r) => r.name).join('、')}),改动即时生效`
  }
  return null
})

const readonlyBanner = computed<{ text: string; tone: string } | null>(() => {
  const d = detail.value
  if (!d || d.access === 'owner') return null
  if (d.access === 'admin') return { text: '管理员视角:治理只读(下架 / 删除走 ⋯ 菜单)', tone: 'info' }
  if (d.access === 'ref') {
    return {
      text: `来自 ${shareIn.value?.grantedByName ?? '他人'} 的引用分享 —— 只读,可运行(引用覆盖全部成员)`,
      tone: 'info',
    }
  }
  if (d.access === 'public') {
    return { text: '公共 Suite —— 只读;先「复制到我的」,在副本上运行或编辑', tone: 'info' }
  }
  return null
})

async function loadShareMeta(): Promise<void> {
  const d = detail.value
  if (!d) return
  try {
    const [out, inn] = await Promise.all([
      listShares({ direction: 'out', resourceType: 'suite', resourceId: String(d.suiteId) })
        .catch(() => []),
      listShares({ direction: 'in', resourceType: 'suite' }).catch(() => []),
    ])
    referrers.value = out.map((r) => ({ name: r.granteeName, shareId: r.id }))
    shareIn.value = inn.find((r) => r.suiteId === d.suiteId)
      ? { id: inn.find((r) => r.suiteId === d.suiteId)!.id,
          grantedByName: inn.find((r) => r.suiteId === d.suiteId)!.grantedByName }
      : null
  } catch { /* 横幅是增强,失败静默 */ }
}

async function confirmFirstEdit(): Promise<boolean> {
  const ok = await confirmAction(
    `${liveBanner.value}。本次编辑会话此后不再提示,自动保存照常进行。继续?`,
    '首次改动提示',
    { type: 'warning', confirmButtonText: '继续编辑', cancelButtonText: '暂停保存' },
  )
  if (ok) sessionConfirmed = true
  return ok
}

// ── ⋯ 菜单动作 ────────────────────────────────────────────────
const shareResource = computed(() => detail.value ? {
  type: 'suite' as const, id: String(detail.value.suiteId), name: detail.value.name,
} : null)

async function rename(): Promise<void> {
  menuOpen.value = false
  const d = detail.value
  if (!d) return
  const name = await promptAction('Suite 名称(1–128 字符)', '重命名 Suite',
    { inputValue: d.name })
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed || trimmed === d.name) return
  try {
    const out = await patchSuite(d.suiteId, { name: trimmed })
    detail.value = { ...detail.value, ...out } as SuiteDetail
    toast.success(`已重命名为 ${trimmed}`)
  } catch (e) {
    toast.error(`重命名失败:${(e as Error).message}`)
  }
}

async function finishDraft(): Promise<void> {
  const d = detail.value
  if (!d) return
  const name = await promptAction('给这个 Suite 起个正式名称(完成编排)', '完成编排 · 命名转正',
    { inputValue: d.name.startsWith('未命名') ? '' : d.name })
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed) return
  try {
    const out = await patchSuite(d.suiteId, { name: trimmed, clearDraft: true })
    detail.value = { ...detail.value, ...out, isDraft: false } as SuiteDetail
    toast.success(`「${trimmed}」已完成编排,可发布 / 分享`)
  } catch (e) {
    toast.error(`转正失败:${(e as Error).message}`)
  }
}

async function publish(): Promise<void> {
  menuOpen.value = false
  const d = detail.value
  if (!d) return
  const privates = d.members.filter((m) => m.visibility !== 'public')
  const msg = privates.length
    ? `发布到公共库?以下 ${privates.length} 个未发布成员及其数据集将一并公开:${privates.map((m) => m.name).join('、')}`
    : '发布到公共库?所有成员均已公开。'
  const ok = await confirmAction(msg, '发布到公共库',
    { type: 'warning', confirmButtonText: '发布', cancelButtonText: '取消' })
  if (!ok) return
  try {
    const out = await postSuitePublish(d.suiteId)
    const cascaded = (out.publishedMembers ?? []).length
    toast.success(cascaded ? `已发布(级联公开了 ${cascaded} 个成员)` : '已发布到公共库')
    await load()
  } catch (e) {
    toast.error(`发布失败:${(e as Error).message}`)
  }
}

async function unpublish(): Promise<void> {
  menuOpen.value = false
  const ok = await confirmAction('下架 Suite?成员场景的公共状态独立保留。', '下架为私有',
    { type: 'warning', confirmButtonText: '下架', cancelButtonText: '取消' })
  if (!ok || !detail.value) return
  try {
    await deleteSuitePublish(detail.value.suiteId)
    toast.success('已下架为私有')
    await load()
  } catch (e) {
    toast.error(`下架失败:${(e as Error).message}`)
  }
}

async function remove(): Promise<void> {
  menuOpen.value = false
  const d = detail.value
  if (!d) return
  const refN = referrers.value.length
  const ok = await confirmAction(
    `删除 Suite「${d.name}」?成员场景不受影响${refN ? `;${refN} 位引用者将失去访问(会收到通知)` : ''}。`,
    '删除 Suite',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  if (!ok) return
  try {
    await deleteSuite(d.suiteId)
    toast.success('Suite 已删除')
    void router.push('/suites')
  } catch (e) {
    toast.error(`删除失败:${(e as Error).message}`)
  }
}

async function forkPublic(): Promise<void> {
  const d = detail.value
  if (!d) return
  try {
    const out = await forkPublicSuite(d.suiteId)
    toast.success(`已复制为我的 Suite「${out.suiteName}」(${out.memberCount} 个成员)`)
    void router.push(`/suites/${out.suiteId}`)
  } catch (e) {
    toast.error(`复制失败:${(e as Error).message}`)
  }
}

async function forkRef(): Promise<void> {
  if (!shareIn.value) return
  try {
    const out = await forkShare(shareIn.value.id)
    if (out.suiteId) {
      toast.success(`已转为我的副本「${out.suiteName}」`)
      void router.push(`/suites/${out.suiteId}`)
    }
  } catch (e) {
    toast.error(`转为副本失败:${(e as Error).message}`)
  }
}

async function unsubRef(): Promise<void> {
  if (!shareIn.value) return
  const ok = await confirmAction('退订该引用分享?属主不会收到通知,可再次被分享。', '退订',
    { type: 'warning', confirmButtonText: '退订', cancelButtonText: '取消' })
  if (!ok) return
  try {
    await deleteShare(shareIn.value.id)
    toast.success('已退订该引用')
    void router.push('/suites')
  } catch (e) {
    toast.error(`退订失败:${(e as Error).message}`)
  }
}

// tab 同步到 URL(?tab=runs;21 页深链)
watch(tab, (v) => {
  if (route.query.tab !== v) {
    void router.replace({ query: v === 'runs' ? { tab: 'runs' } : {} })
  }
})

onMounted(() => void load())
onBeforeUnmount(() => { if (saveTimer !== null) window.clearTimeout(saveTimer) })
</script>

<style scoped>
/* 容器与列表/工作台页同款节奏(.slib 规范:1480 居中 + 56/32/48) */
.sm {
  box-sizing: border-box; max-width: 1480px; min-width: 0;
  margin: 0 auto; padding: 56px 32px 48px;
  display: flex; flex-direction: column; gap: 14px; position: relative;
}
.sm-head { display: flex; align-items: flex-start; gap: 14px; }
.sm-head-main { flex: 1; min-width: 0; }
.sm-title-row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sm-title {
  margin: 0; font-size: 22px; font-weight: 600; line-height: 1.25;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.sm-meta { margin: 0; font-size: 12px; color: var(--color-text-secondary); }
.sm-draft-chip {
  font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 999px;
  color: #b45309; background: rgb(245 158 11 / 10%); border: 1px solid rgb(245 158 11 / 40%);
}
.sm-pub-chip {
  font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 999px;
  color: #15803d; background: rgb(34 197 94 / 10%); border: 1px solid rgb(34 197 94 / 40%);
}
.sm-ref-chip {
  font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 999px;
  color: #6d28d9; background: rgb(139 92 246 / 10%); border: 1px solid rgb(139 92 246 / 40%);
}
.sm-head-actions { display: flex; align-items: center; gap: 8px; }
/* 运行主按钮(原型 20):44px 双行 indigo,副行浅 indigo */
.sm-run {
  display: flex; flex-direction: column; align-items: flex-start; justify-content: center;
  gap: 1px; box-sizing: border-box; height: 44px; padding: 0 18px;
  border: none; border-radius: 6px; cursor: pointer; line-height: 1.2;
  color: #fff; background: #4338ca;
}
.sm-run:hover:not(:disabled) { background: var(--accent-hover); }
.sm-run:disabled { opacity: .5; cursor: not-allowed; }
.sm-run-main { font-size: 13px; font-weight: 600; }
.sm-run-sub { font-size: 11px; color: var(--accent-soft-border); }
.sm-more {
  width: 36px; height: 36px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--color-border-tertiary); background: #fff; color: inherit;
  font-size: 15px;
}
.sm-banner {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 8px 14px; border-radius: 8px; font-size: 12.5px;
}
.sm-banner.info {
  color: #1d4ed8; background: rgb(59 130 246 / 8%);
  border: 1px solid rgb(59 130 246 / 35%);
}
.sm-banner.warn {
  color: #b45309; background: rgb(245 158 11 / 8%);
  border: 1px solid rgb(245 158 11 / 40%);
}
.sm-banner.bad {
  color: #dc2626; background: rgb(220 38 38 / 6%);
  border: 1px solid rgb(220 38 38 / 35%);
}
.sm-banner.draft {
  color: #475569; background: rgb(100 116 139 / 6%);
  border: 1px solid rgb(100 116 139 / 30%);
}
.sm-banner-ops { margin-left: auto; display: flex; gap: 8px; }
.sm-banner-ops button, .sm-banner.draft button {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.sm-tabs { display: flex; flex-direction: column; gap: 12px; }
/* 页签 = 原型 20 下划线式(灰底胶囊是组件默认样式,按 role 覆写) */
.sm-tabs :deep([role='tablist']) {
  display: flex; gap: 20px; border-bottom: 1px solid var(--color-border-tertiary);
  background: transparent; border-radius: 0; padding: 0;
}
.sm-tabs :deep([role='tab']) {
  padding: 8px 2px; margin-bottom: -1px; border-radius: 0;
  background: transparent; box-shadow: none;
  font-size: 13px; color: var(--color-text-secondary);
}
.sm-tabs :deep([role='tab'][data-state='active']) {
  border-bottom: 2px solid #4338ca; font-weight: 600;
  color: var(--color-text-primary); box-shadow: none;
}
.sm-pane { display: flex; flex-direction: column; gap: 12px; }
.sm-cols {
  display: grid; grid-template-columns: 220px minmax(0, 1fr) 300px;
  gap: 12px; align-items: start;
}
@media (max-width: 1100px) {
  .sm-cols { grid-template-columns: 200px minmax(0, 1fr); }
  .sm-cols > :nth-child(3) { grid-column: 1 / -1; }
}
.sm-menu-mask { position: fixed; inset: 0; z-index: 30; }
.sm-menu {
  position: absolute; right: 32px; top: 132px; z-index: 31;
  display: flex; flex-direction: column; min-width: 170px;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 10px;
  background: var(--c-bg, #fff); box-shadow: 0 8px 24px rgb(15 23 42 / 14%);
  padding: 4px;
}
.sm-menu button {
  text-align: left; padding: 8px 12px; font-size: 13px; cursor: pointer;
  border: none; background: transparent; color: inherit; border-radius: 6px;
}
.sm-menu button:hover:not(:disabled) { background: rgb(59 130 246 / 8%); }
.sm-menu button:disabled { opacity: .45; cursor: not-allowed; }
.sm-menu .danger { color: var(--sl-bad, #dc2626); }
.sm-loading, .sm-empty { padding: 40px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.btn-primary {
  padding: 7px 16px; font-size: 13px; font-weight: 600; border: none;
  border-radius: 8px; cursor: pointer; color: #fff; background: #4338ca;
}
.btn-secondary {
  padding: 7px 14px; font-size: 13px; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--accent-soft-border); color: #4338ca; background: var(--accent-soft);
}
</style>
