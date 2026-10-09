<!-- SuiteCompose.vue — 新建/改结构画布(原型 10–13;第 4 步)。
     最小闭环:拖入(抽屉 → 画布/节点/前后置条)、连线(节点右侧圆点
     拉到目标)、环拒绝(就地提示)、结构状态条(五条规则实时推断);
     右侧检查器复用 UnitSettings;「完成编排」命名转正并落管理页。
     规则:打开 /suites/new 不落库,首次拖入创建草稿并换 URL;
     非 canEdit 访问 /suites/:id/compose 重定向到管理页只读态。 -->
<template>
  <div v-if="loaded" class="scp" data-testid="suite-compose">
    <!-- 页头:草稿名可改;试跑选中段 + 完成编排(原型 12/13) -->
    <header class="scp-head">
      <div class="scp-head-main">
        <PageBack to="/suites" label="Suite" testid="suite-compose-back" />
        <div class="scp-title-row">
          <span class="icon-badge" aria-hidden="true"><SlibIcon name="stack" :size="15" /></span>
          <input
            v-model="name"
            class="scp-name"
            aria-label="Suite 名称"
            data-testid="suite-compose-name"
            @change="onNameChange"
          />
          <span class="scp-save">{{ saveText }}</span>
        </div>
      </div>
      <div class="scp-actions">
        <button
          type="button"
          class="scp-ghost"
          data-testid="suite-compose-tryrun"
          :disabled="!canTryRun"
          :title="canTryRun ? '运行所选单元及其全部上游' : '先在画布选中一个单元'"
          @click="tryRunSelected"
        >试跑选中段</button>
        <button
          type="button"
          class="scp-primary"
          data-testid="suite-compose-finish"
          :disabled="!mainIds.length"
          @click="openFinish"
        >完成编排</button>
      </div>
    </header>

    <div class="scp-cols">
      <!-- 左:场景抽屉(复用管理页组件) -->
      <ScenarioDrawer :member-ids="memberIdSet" @add="onDrawerAdd" />

      <!-- 中:前置条 / 画布 / 后置条 / 结构状态条 -->
      <section class="scp-center" aria-label="编排画布">
        <div
          class="scp-strip"
          data-testid="suite-compose-before"
          @dragover.prevent
          @drop.prevent="onStripDrop($event, 'before')"
        >
          <span class="scp-strip-title">前置区</span>
          <span class="scp-strip-hint">把节点拖进来就成为 setup,先于整个主体执行</span>
          <span v-for="sid in beforeIds" :key="sid" class="scp-strip-chip">
            <span class="mono">{{ refOf(sid) }}</span>{{ nameOf(sid) }}
            <button type="button" aria-label="移除前置" @click="removeMember(sid)">×</button>
          </span>
        </div>

        <div class="scp-canvas" @dragover.prevent @drop.prevent="onCanvasDrop">
          <VueFlow
            :nodes="flowNodes"
            :edges="flowEdges"
            :nodes-connectable="true"
            :min-zoom="0.3"
            :max-zoom="1"
            fit-view-on-init
            @connect="onConnect"
            @node-drag-stop="onDragStop"
            @node-click="onNodeClick"
            @edge-click="onEdgeClick"
            @pane-click="clearSelection"
          >
            <template #node-unit="p">
              <div
                class="scu" :class="{ sel: selection?.kind === 'unit' && selection.id === p.id }"
                :data-testid="`suite-compose-node-${p.id}`"
                @drop.stop.prevent="onNodeDrop($event, String(p.id))"
              >
                <span class="scu-ref mono">{{ p.data.ref }}</span>
                <span class="scu-name">{{ p.data.name }}</span>
                <Handle type="target" :position="Position.Left" class="scu-handle-in" />
                <Handle type="source" :position="Position.Right" class="scu-handle" />
              </div>
            </template>
            <template #node-slot="p">
              <div
                class="scs" :data-testid="`suite-compose-slot-${p.id}`"
                @drop.stop.prevent="onSlotDrop($event, String(p.id))"
              >
                <span class="scs-label">{{ p.data.label }}</span>
                <button type="button" class="scs-x" aria-label="移除空位" @click.stop="removeSlot(String(p.id))">×</button>
                <Handle type="target" :position="Position.Left" class="scu-handle-in" />
                <Handle type="source" :position="Position.Right" class="scu-handle" />
              </div>
            </template>
            <template #node-start="p">
              <div class="scstart" data-testid="suite-compose-start">{{ p.data.label }}</div>
            </template>
          </VueFlow>
          <div v-if="!mainIds.length && !slots.length" class="scp-empty" data-testid="suite-compose-empty">
            <strong>把入口场景拖到这里</strong>
            <span>通常是登录、准备数据这类第一步</span>
          </div>
          <div v-if="cycleMsg" role="status" class="scp-cycle" data-testid="suite-compose-cycle">{{ cycleMsg }}</div>
        </div>

        <div
          class="scp-strip"
          data-testid="suite-compose-after"
          @dragover.prevent
          @drop.prevent="onStripDrop($event, 'after')"
        >
          <span class="scp-strip-title">后置区</span>
          <span class="scp-strip-hint">teardown,主体失败也执行</span>
          <span v-for="sid in afterIds" :key="sid" class="scp-strip-chip">
            <span class="mono">{{ refOf(sid) }}</span>{{ nameOf(sid) }}
            <button type="button" aria-label="移除后置" @click="removeMember(sid)">×</button>
          </span>
        </div>

        <!-- 结构状态条:模式由结构推断(五条规则) -->
        <div class="scp-status" role="status" data-testid="suite-compose-status">
          <span class="scp-status-label">当前结构</span>
          <span class="scp-mode-chip">{{ MODE_LABEL[inference.mode] }}</span>
          <span class="mono scp-stats">{{ statsText }}</span>
          <span class="scp-why">{{ inference.reason }}</span>
          <button
            type="button" class="scp-q" aria-label="四种结构说明"
            data-testid="suite-compose-guide" @click="guideOpen = true"
          >?</button>
        </div>
      </section>

      <!-- 右:检查器(空态三步引导 / 选中单元 / 选中连线) -->
      <aside class="scp-rail" aria-label="检查器">
        <template v-if="!selection">
          <h2 class="scp-rail-title">三个动作搭一个 Suite</h2>
          <ol class="scp-steps">
            <li><b>拖入</b>:左侧场景拖到画布,成为一个单元</li>
            <li><b>连线</b>:从节点右侧圆点拉到下一个节点,表示「它跑完再跑这个」</li>
            <li><b>不连</b>:互不相连的单元彼此独立</li>
          </ol>
          <p class="scp-rail-note">不用先选模式:画出来的结构就是模式,底部状态条会实时告诉你。</p>
          <button type="button" class="scp-linklike" @click="guideOpen = true">四种结构分别是什么 →</button>
        </template>

        <template v-else-if="selection.kind === 'edge'">
          <span class="scp-rail-cap">选中连线</span>
          <div class="scp-sel-title mono">{{ selEdgeText }}</div>
          <p class="scp-rail-note">删除连线即移除这条 needs 依赖;单元保留。</p>
          <button
            type="button" class="scp-danger"
            data-testid="suite-compose-del-edge" @click="removeSelectedEdge"
          >删除这条连线</button>
        </template>

        <template v-else>
          <span class="scp-rail-cap">选中单元</span>
          <div class="scp-sel-title">{{ nameOf(selUnitId) }}</div>
          <div class="scp-sel-sid mono">{{ selUnitId }}</div>
          <label class="scp-field">别名 ref
            <input
              v-model="refDraft" class="mono scp-ref-in"
              data-testid="suite-compose-ref" @change="onRefChange"
            />
          </label>
          <div class="scp-field"><span class="scp-field-label">依赖</span>{{ needsText }}</div>
          <UnitSettings
            :member="selMember" :unit="units[selUnitId] || {}"
            :orchestrate="inference.mode === 'compose'"
            :schemes="schemeList" :dataset-rows="datasetRows" :loading="schemesLoading"
            @patch="(p) => onUnitPatch(selUnitId, p)"
          />
          <button
            type="button" class="scp-danger"
            data-testid="suite-compose-remove" @click="removeMember(selUnitId)"
          >从画布移除</button>
        </template>
      </aside>
    </div>

    <!-- 四种结构说明(原型 11) -->
    <StructureGuideDialog
      v-model="guideOpen"
      @start-skeleton="placeSkeleton"
      @dont-show-again="rememberGuideOff"
    />

    <!-- 试跑/完成后的预检(原型 30,复用) -->
    <SuiteRunPreflight
      :open="preflightOpen" :suite-id="suiteId ?? 0"
      @update:open="preflightOpen = $event"
      @close="preflightOpen = false"
      @run="onPreflightRun"
      @locate="onLocate"
    />

    <!-- 完成编排(原型 13 面板) -->
    <Teleport to="body">
      <Transition name="pop">
  <div v-if="finishOpen" class="scp-fmask" data-testid="suite-compose-finish-mask" @click.self="finishOpen = false">
        <div role="dialog" aria-labelledby="scp-fin-title" class="scp-finish">
          <h2 id="scp-fin-title">完成编排</h2>
          <label class="scp-field">名称
            <input v-model="finishName" data-testid="suite-compose-finish-name" />
          </label>
          <span v-if="finishNameErr" class="scp-ferr">{{ finishNameErr }}</span>
          <label class="scp-field">描述(可选)
            <input v-model="finishDesc" placeholder="这组场景验证什么" data-testid="suite-compose-finish-desc" />
          </label>
          <div class="scp-fsummary" data-testid="suite-compose-finish-summary">{{ finishSummary }}</div>
          <div v-if="finishCheck" class="scp-fcheck" :class="{ bad: finishCheckErr > 0 }">{{ finishCheck }}</div>
          <fieldset class="scp-fafter">
            <legend>保存后</legend>
            <label><input v-model="finishAfter" type="radio" value="manage" />进入管理页</label>
            <label><input v-model="finishAfter" type="radio" value="run" />立即运行(先过预检)</label>
          </fieldset>
          <div class="scp-facts">
            <button type="button" class="scp-ghost" @click="finishOpen = false">继续编辑</button>
            <button
              type="button" class="scp-primary"
              data-testid="suite-compose-finish-save" :disabled="finishing"
              @click="saveFinish"
            >保存</button>
          </div>
        </div>
      </div>
    </Transition>
    </Teleport>
  </div>
  <div v-else class="scp-loading">加载中…</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Handle, Position, VueFlow } from '@vue-flow/core'
import type { Connection, Edge, Node, NodeDragEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import {
  createSuite, getSuite, patchSuite, putSuiteComposition, runSuite,
  suiteErrDetail, validateSuite,
  type MemberRole, type SuiteModeConfig, type SuiteUnitConfig,
} from '@/api/suites'
import { listShares } from '@/api/shares'
import { executionsBatchUrl } from '@/utils/links'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import {
  MODE_LABEL, canvasEdgesFromSuite, edgeMakesCycle, estimateOrchRuns,
  inferStructure, orderByStructure,
} from '@/utils/suiteStructure'
import { useSuiteSchemes } from '@/composables/useSuiteSchemes'
import type { SchemeV2 } from '@/api/scenario-composer'
import ScenarioDrawer from '@/components/suites/ScenarioDrawer.vue'
import PageBack from '@/components/chrome/PageBack.vue'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import UnitSettings from '@/components/suites/UnitSettings.vue'
import StructureGuideDialog from '@/components/suites/StructureGuideDialog.vue'
import SuiteRunPreflight from '@/components/suites/SuiteRunPreflight.vue'

const GUIDE_OFF_KEY = 'suite-compose-guide-off'
const AUTOSAVE_MS = 800

const route = useRoute()
const router = useRouter()

// ── 状态 ────────────────────────────────────────────────────────
const loaded = ref(false)
const suiteId = ref<number | null>(
  route.params.id ? Number(route.params.id) : null)
const rev = ref(0)
const isDraft = ref(true)
const name = ref('未命名 Suite')
const description = ref('')
const visibility = ref('private')
const members = ref<{ scenarioId: string; role: MemberRole }[]>([])
const units = ref<Record<string, SuiteUnitConfig>>({})
/** 主体连线:consumer → [producer…](保存时按模式落 needs 或成员顺序)。 */
const edges = ref<Record<string, string[]>>({})
/** 画布节点坐标(mode_config.canvas 持久化;新单元自动布局)。 */
const positions = ref<Record<string, { x: number; y: number }>>({})
const memberNames = ref<Record<string, string>>({})
/** 骨架空位(原型 11「用这个结构开始」):纯本地,不落库。 */
const slots = ref<{ id: string; label: string; x: number; y: number }[]>([])
const slotEdges = ref<string[]>([])
const selection = ref<{ kind: 'unit' | 'edge'; id: string } | null>(null)
const cycleMsg = ref('')
const guideOpen = ref(false)
const preflightOpen = ref(false)
const saveState = ref<'clean' | 'dirty' | 'saving'>('clean')
let saveTimer: number | null = null
let suppressSave = false
let sessionConfirmed = false
let firstEditBanner: string | null = null

const beforeIds = computed(() =>
  members.value.filter((m) => m.role === 'before').map((m) => m.scenarioId))
const afterIds = computed(() =>
  members.value.filter((m) => m.role === 'after').map((m) => m.scenarioId))
const mainIds = computed(() =>
  members.value.filter((m) => m.role === 'main').map((m) => m.scenarioId))
const memberIdSet = computed(() => new Set(members.value.map((m) => m.scenarioId)))

const inference = computed(() => inferStructure(mainIds.value, edges.value))

const statsText = computed(() => {
  const n = mainIds.value.length
  if (inference.value.mode === 'aggregate') return `${n} 单元`
  const runs = estimateOrchRuns(
    mainIds.value.map((scenarioId) => ({ scenarioId })),
    { units: units.value })
  if (inference.value.mode === 'compose') {
    let layers = 0
    const seen = new Set<string>()
    const depth = (id: string): number => {
      if (seen.has(id)) return 0
      seen.add(id)
      const ups = (edges.value[id] || []).filter((u) => mainIds.value.includes(u))
      return ups.length ? Math.max(...ups.map(depth)) + 1 : 0
    }
    for (const id of mainIds.value) layers = Math.max(layers, depth(id) + 1)
    return `${n} 单元 · ${layers} 层 · ${runs} runs`
  }
  return `${n} 单元 · ${runs} runs`
})

const saveText = computed(() => {
  if (!suiteId.value) return '未保存 · 拖入第一个场景后自动创建草稿'
  if (saveState.value === 'saving') return '保存中…'
  if (saveState.value === 'dirty') return '未保存的改动…'
  return isDraft.value ? '草稿 · 已自动保存' : '已自动保存'
})

const canTryRun = computed(() =>
  !!suiteId.value && selection.value?.kind === 'unit'
  && mainIds.value.includes(selection.value.id))

// ── 画布节点/边(computed 只读;坐标在 applyDetail/addUnit 一次性落位)──
const layerMemo = ref<Record<string, number>>({})
function autoLayer(id: string): number {
  if (id in layerMemo.value) return layerMemo.value[id]
  const ups = (edges.value[id] || []).filter((u) => mainIds.value.includes(u))
  const lv = ups.length ? Math.max(...ups.map(autoLayer)) + 1 : 0
  layerMemo.value[id] = lv
  return lv
}
function computeAutoPos(id: string): { x: number; y: number } {
  const layer = autoLayer(id)
  const idx = Math.max(mainIds.value.indexOf(id), 0)
  return { x: 40 + layer * 240, y: 40 + idx * 96 }
}

const flowNodes = computed<Node[]>(() => {
  const out: Node[] = [{
    id: 'start', type: 'start', position: { x: -120, y: 40 + (mainIds.value.length - 1) * 48 },
    draggable: false, selectable: false, data: { label: '开始' },
  }]
  for (const sid of mainIds.value) {
    const u = units.value[sid] || {}
    out.push({
      id: sid, type: 'unit',
      position: positions.value[sid] ?? computeAutoPos(sid),
      data: { ref: u.ref || sid, name: nameOf(sid) },
    })
  }
  for (const s of slots.value) {
    out.push({ id: s.id, type: 'slot', position: { x: s.x, y: s.y }, data: { label: s.label } })
  }
  return out
})

const flowEdges = computed<Edge[]>(() => {
  const out: Edge[] = []
  for (const [consumer, producers] of Object.entries(edges.value)) {
    for (const p of producers) {
      if (!mainIds.value.includes(consumer) || !mainIds.value.includes(p)) continue
      out.push({
        id: `${p}->${consumer}`, source: p, target: consumer,
        style: { stroke: 'var(--color-text-tertiary)', strokeWidth: 1.6 },
      })
    }
  }
  for (const key of slotEdges.value) {
    const [a, b] = key.split('->')
    if (!nodeIdExists(a) || !nodeIdExists(b)) continue
    out.push({
      id: `slot:${key}`, source: a, target: b,
      style: { stroke: '#4338ca', strokeWidth: 1.4, strokeDasharray: '5 4' },
    })
  }
  // 「开始」→ 入口单元(纯视觉;不参与推断)
  const inDeg: Record<string, number> = {}
  for (const id of mainIds.value) inDeg[id] = (edges.value[id] || []).length
  for (const r of mainIds.value.filter((id) => inDeg[id] === 0)) {
    out.push({
      id: `start->${r}`, source: 'start', target: r,
      style: { stroke: 'var(--color-border-secondary)', strokeWidth: 1.2 },
    })
  }
  return out
})

function nodeIdExists(id: string): boolean {
  return mainIds.value.includes(id) || slots.value.some((s) => s.id === id)
}

// ── 加载(/suites/:id/compose;非 canEdit 重定向管理页只读态)─────
onMounted(async () => {
  if (!route.params.id) {
    loaded.value = true
    if (!localStorage.getItem(GUIDE_OFF_KEY)) guideOpen.value = true
    return
  }
  try {
    const d = await getSuite(Number(route.params.id))
    if (!d.canEdit) {
      void router.replace(`/suites/${d.suiteId}`)
      return
    }
    applyDetail(d)
    loaded.value = true
    void loadFirstEditBanner()
  } catch {
    toast.error('Suite 加载失败')
    void router.replace('/suites')
  }
})

function applyDetail(d: {
  suiteId: number; name: string; description: string; visibility: string
  isDraft?: boolean; rev: number; mode: string
  members: { scenarioId: string; name: string; role: MemberRole }[]
  modeConfig: SuiteModeConfig | null
}): void {
  suppressSave = true
  suiteId.value = d.suiteId
  rev.value = d.rev
  isDraft.value = d.isDraft !== false
  name.value = d.name
  description.value = d.description || ''
  visibility.value = d.visibility
  members.value = d.members.map((m) => ({ scenarioId: m.scenarioId, role: m.role }))
  memberNames.value = Object.fromEntries(d.members.map((m) => [m.scenarioId, m.name]))
  const cfg = d.modeConfig || {}
  units.value = { ...(cfg.units as Record<string, SuiteUnitConfig>) ?? {} }
  positions.value = { ...(cfg.canvas as Record<string, { x: number; y: number }>) ?? {} }
  const main = members.value.filter((m) => m.role === 'main').map((m) => m.scenarioId)
  edges.value = canvasEdgesFromSuite(d.mode, main, units.value)
  layerMemo.value = {}
  for (const sid of main) {
    positions.value[sid] ??= computeAutoPos(sid)
  }
  suppressSave = false
  saveState.value = 'clean'
}

async function loadFirstEditBanner(): Promise<void> {
  if (!suiteId.value) return
  if (visibility.value === 'public') {
    firstEditBanner = '此 Suite 已公开,改动立即对所有人可见'
    return
  }
  try {
    const out = await listShares({
      direction: 'out', resourceType: 'suite', resourceId: String(suiteId.value) })
    if (out.length) {
      firstEditBanner = `此 Suite 正被 ${out.length} 人引用(${out.map((r) => r.granteeName).join('、')}),改动即时生效`
    }
  } catch { /* 横幅是增强,失败静默 */ }
}

// ── 名称(草稿名可直接改;patch 落库)────────────────────────────
function onNameChange(): Promise<void> {
  const trimmed = name.value.trim()
  if (!suiteId.value || !trimmed) return Promise.resolve()
  return patchSuite(suiteId.value, { name: trimmed }).then(() => {
    toast.success('已重命名')
  }).catch((e) => {
    const det = suiteErrDetail(e)
    toast.error(`重命名失败:${(det?.message as string) || (e as Error).message}`)
  })
}

// ── 自动保存(800ms 防抖;首改确认 + rev 冲突重拉)───────────────
watch([members, units, edges, positions], () => markDirty(), { deep: true })

function markDirty(): void {
  if (suppressSave || !suiteId.value) return
  saveState.value = 'dirty'
  if (saveTimer !== null) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save() }, AUTOSAVE_MS)
}

async function save(): Promise<boolean> {
  const id = suiteId.value
  if (!id || saveState.value !== 'dirty') return true
  if (!sessionConfirmed && firstEditBanner) {
    const banner = firstEditBanner
    const ok = await confirmAction(
      `${banner}。本次编辑会话此后不再提示,自动保存照常进行。继续?`,
      '首次改动提示', { type: 'warning', confirmButtonText: '继续编辑', cancelButtonText: '暂停保存' })
    if (!ok) return false
    sessionConfirmed = true
  }
  saveState.value = 'saving'
  const inf = inference.value
  const ordered = orderByStructure(inf, mainIds.value)
  const cleanedUnits: Record<string, SuiteUnitConfig> = {}
  for (const m of members.value) {
    const u = { ...(units.value[m.scenarioId] || {}) }
    // 非 compose 模式不携带 needs(422 needs_not_allowed);结构编码在成员顺序里
    u.needs = inf.mode === 'compose'
      ? (edges.value[m.scenarioId] || []).filter((x) => mainIds.value.includes(x))
      : undefined
    if (!u.ref) delete u.ref
    cleanedUnits[m.scenarioId] = u
  }
  const bodyMembers = [
    ...beforeIds.value.map((scenarioId) => ({ scenarioId, role: 'before' as MemberRole })),
    ...ordered.map((scenarioId) => ({ scenarioId, role: 'main' as MemberRole })),
    ...afterIds.value.map((scenarioId) => ({ scenarioId, role: 'after' as MemberRole })),
  ]
  try {
    const out = await putSuiteComposition(id, {
      rev: rev.value, mode: inf.mode, members: bodyMembers,
      modeConfig: { units: cleanedUnits, canvas: positions.value },
    })
    rev.value = out.rev
    saveState.value = 'clean'
    return true
  } catch (e) {
    const det = suiteErrDetail(e)
    if (det?.code === 'suite_rev_conflict') {
      toast.error('Suite 已被修改,已拉取最新编排(你的未保存改动被放弃)')
      applyDetail((det.latest ?? {}) as Parameters<typeof applyDetail>[0])
      saveState.value = 'clean'
      return true
    }
    saveState.value = 'dirty'
    toast.error(`保存失败:${(det?.message as string) || (e as Error).message}`)
    if (saveTimer === null) {
      saveTimer = window.setTimeout(() => { saveTimer = null; void save() }, 3000)
    }
    return false
  }
}

// ── 拖入(抽屉 + 按钮同路径;空白 = 新单元,节点上 = 接在它后面)──
function nameOf(sid: string): string {
  return memberNames.value[sid] || sid
}
function refOf(sid: string): string {
  return units.value[sid]?.ref || sid
}

async function ensureSuite(): Promise<boolean> {
  if (suiteId.value) return true
  try {
    const s = await createSuite({})
    suiteId.value = s.suiteId
    rev.value = s.rev
    name.value = s.name
    visibility.value = s.visibility
    // 同一路由记录的 alias 导航:组件实例复用,本地画布状态不丢
    await router.replace(`/suites/${s.suiteId}/compose`)
    return true
  } catch (e) {
    const det = suiteErrDetail(e)
    toast.error(`创建草稿失败:${(det?.message as string) || (e as Error).message}`)
    return false
  }
}

async function addUnit(
  scenarioId: string, role: MemberRole,
  pos?: { x: number; y: number }, afterId?: string,
): Promise<void> {
  if (memberIdSet.value.has(scenarioId)) {
    toast.info('该场景已在画布上')
    return
  }
  if (!await ensureSuite()) return
  members.value = [...members.value, { scenarioId, role }]
  memberNames.value[scenarioId] = scenarioId
  layerMemo.value = {}
  if (role === 'main') {
    if (afterId && mainIds.value.includes(afterId) && afterId !== scenarioId) {
      edges.value = {
        ...edges.value,
        [scenarioId]: [...(edges.value[scenarioId] || []), afterId],
      }
    }
    layerMemo.value = {}
    positions.value[scenarioId] = pos ?? computeAutoPos(scenarioId)
    selection.value = { kind: 'unit', id: scenarioId }
    void loadSchemes(scenarioId)
  }
  markDirty()
}

function onDrawerAdd(scenarioId: string, role: MemberRole): void {
  void addUnit(scenarioId, role)
}

function scenarioFromDrop(ev: DragEvent): string | null {
  return ev.dataTransfer?.getData('application/x-gimbal-scenario') || null
}

async function onCanvasDrop(ev: DragEvent): Promise<void> {
  const sid = scenarioFromDrop(ev)
  if (!sid) return
  await addUnit(sid, 'main')
}

async function onNodeDrop(ev: DragEvent, nodeId: string): Promise<void> {
  const sid = scenarioFromDrop(ev)
  if (!sid) return
  if (mainIds.value.includes(nodeId)) {
    await addUnit(sid, 'main', undefined, nodeId)
  } else {
    await addUnit(sid, 'main')
  }
}

/** 拖到骨架空位上 = 填入:单元落在空位坐标,空位的连线转给单元。 */
async function onSlotDrop(ev: DragEvent, slotId: string): Promise<void> {
  const sid = scenarioFromDrop(ev)
  if (!sid) return
  const slot = slots.value.find((s) => s.id === slotId)
  if (!slot) return
  await addUnit(sid, 'main', { x: slot.x, y: slot.y })
  if (memberIdSet.value.has(sid) && mainIds.value.includes(sid)) {
    for (const key of slotEdges.value) {
      const [a, b] = key.split('->')
      const na = a === slotId ? sid : a
      const nb = b === slotId ? sid : b
      if (na !== nb) addEdge(na, nb)
    }
    removeSlot(slotId)
  }
}

async function onStripDrop(ev: DragEvent, role: MemberRole): Promise<void> {
  const sid = scenarioFromDrop(ev)
  if (!sid) return
  await addUnit(sid, role)
}

// ── 连线(右侧圆点拉线;成环就地拒绝)───────────────────────────
let cycleTimer: number | null = null
function flashCycle(msg: string): void {
  cycleMsg.value = msg
  if (cycleTimer !== null) window.clearTimeout(cycleTimer)
  cycleTimer = window.setTimeout(() => { cycleMsg.value = '' }, 4000)
}

function addEdge(producer: string, consumer: string): void {
  if (producer === consumer) return
  const bothUnit = mainIds.value.includes(producer) && mainIds.value.includes(consumer)
  if (bothUnit) {
    const cur = edges.value[consumer] || []
    if (cur.includes(producer)) return
    if (edgeMakesCycle(mainIds.value, edges.value, producer, consumer)) {
      flashCycle(`${refOf(producer)} → ${refOf(consumer)} 会形成环,连线已取消。依赖只能从早的指向晚的。`)
      return
    }
    edges.value = { ...edges.value, [consumer]: [...cur, producer] }
    layerMemo.value = {}
    markDirty()
    return
  }
  if (nodeIdExists(producer) && nodeIdExists(consumer)) {
    const key = `${producer}->${consumer}`
    if (!slotEdges.value.includes(key)) slotEdges.value = [...slotEdges.value, key]
  }
}

function onConnect(c: Connection): void {
  if (c.source && c.target) addEdge(c.source, c.target)
}

function onDragStop(ev: NodeDragEvent): void {
  const id = String(ev.node.id)
  if (mainIds.value.includes(id)) {
    positions.value = { ...positions.value, [id]: { ...ev.node.position } }
    markDirty()
  }
}

function onNodeClick({ node }: { node: Node }): void {
  const id = String(node.id)
  if (mainIds.value.includes(id)) selection.value = { kind: 'unit', id }
}

function onEdgeClick({ edge }: { edge: Edge }): void {
  if (edge.source === 'start') return
  selection.value = { kind: 'edge', id: String(edge.id) }
}

function clearSelection(): void {
  selection.value = null
}

const selEdgeText = computed(() => {
  if (selection.value?.kind !== 'edge') return ''
  const raw = selection.value.id.replace(/^slot:/, '')
  const [a, b] = raw.split('->')
  return `${refOf(a)} → ${refOf(b)}`
})

function removeSelectedEdge(): void {
  if (selection.value?.kind !== 'edge') return
  const raw = selection.value.id.replace(/^slot:/, '')
  if (selection.value.id.startsWith('slot:')) {
    slotEdges.value = slotEdges.value.filter((k) => k !== raw)
  } else {
    const [a, b] = raw.split('->')
    const cur = edges.value[b] || []
    edges.value = { ...edges.value, [b]: cur.filter((x) => x !== a) }
    layerMemo.value = {}
    markDirty()
  }
  selection.value = null
}

function removeMember(sid: string): void {
  members.value = members.value.filter((m) => m.scenarioId !== sid)
  const next: Record<string, string[]> = {}
  for (const [c, ps] of Object.entries(edges.value)) {
    if (c === sid) continue
    const kept = ps.filter((p) => p !== sid)
    if (kept.length) next[c] = kept
  }
  edges.value = next
  delete positions.value[sid]
  const nextUnits = { ...units.value }
  delete nextUnits[sid]
  units.value = nextUnits
  layerMemo.value = {}
  if (selection.value?.kind === 'unit' && selection.value.id === sid) {
    selection.value = null
  }
  markDirty()
}

// ── 检查器:单元设置(方案/数据行懒加载,同管理页)───────────────
const schemeList = ref<SchemeV2[]>([])
const datasetRows = ref<{ datasetId: string; name: string; rowCount: number }[]>([])
const schemesLoading = ref(false)
const { schemesOf, datasetOf } = useSuiteSchemes()

async function loadSchemes(scenarioId: string): Promise<void> {
  schemesLoading.value = true
  schemeList.value = []
  datasetRows.value = []
  try {
    const list = await schemesOf(scenarioId)
    schemeList.value = list
    const rows: { datasetId: string; name: string; rowCount: number }[] = []
    for (const s of list) {
      for (const ds of s.dataSetIds || []) {
        const d = await datasetOf(ds)
        if (d) rows.push({ datasetId: ds, name: d.name || ds, rowCount: d.rows.length })
      }
    }
    datasetRows.value = rows
  } finally {
    schemesLoading.value = false
  }
}

watch(selection, (sel) => {
  if (sel?.kind === 'unit') void loadSchemes(sel.id)
})

const selUnitId = computed(() =>
  selection.value?.kind === 'unit' ? selection.value.id : '')

const selMember = computed(() => {
  const sid = selUnitId.value
  return {
    scenarioId: sid, name: nameOf(sid), module: '', visibility: 'private',
    role: members.value.find((m) => m.scenarioId === sid)?.role ?? 'main',
    sort: 0, addedAt: null,
  }
})

const refDraft = ref('')
watch(selection, (sel) => {
  if (sel?.kind === 'unit') refDraft.value = units.value[sel.id]?.ref || sel.id
})
function onRefChange(): void {
  if (selection.value?.kind !== 'unit') return
  const v = refDraft.value.trim()
  const sid = selection.value.id
  const cur = units.value[sid] || {}
  units.value = { ...units.value, [sid]: { ...cur, ref: v || sid } }
  markDirty()
}

const needsText = computed(() => {
  if (selection.value?.kind !== 'unit') return ''
  const ups = edges.value[selection.value.id] || []
  return ups.length ? ups.map(refOf).join(', ') : '无 · 入口'
})

function onUnitPatch(sid: string, patch: Partial<SuiteUnitConfig>): void {
  units.value = {
    ...units.value,
    [sid]: { ...(units.value[sid] || {}), ...patch },
  }
  markDirty()
}

// ── 骨架空位(原型 11「用这个结构开始」)────────────────────────
let slotSeq = 0
function placeSkeleton(mode: string): void {
  guideOpen.value = false
  slots.value = []
  slotEdges.value = []
  const mk = (label: string, x: number, y: number) =>
    ({ id: `slot-${++slotSeq}`, label, x, y })
  const link = (a: { id: string }, b: { id: string }) => `${a.id}->${b.id}`
  if (mode === 'chain') {
    const s = [mk('步骤 1', 40, 60), mk('步骤 2', 280, 60), mk('步骤 3', 520, 60)]
    slots.value = s
    slotEdges.value = [link(s[0], s[1]), link(s[1], s[2])]
  } else if (mode === 'fanout') {
    const src = mk('源', 40, 90)
    const vs = [mk('变体 1', 320, 30), mk('变体 2', 320, 150)]
    slots.value = [src, ...vs]
    slotEdges.value = [link(src, vs[0]), link(src, vs[1])]
  } else if (mode === 'compose') {
    const a = mk('准备', 40, 90)
    const b = mk('校验 1', 300, 30)
    const c = mk('校验 2', 300, 150)
    const d = mk('汇总', 560, 90)
    slots.value = [a, b, c, d]
    slotEdges.value = [link(a, b), link(a, c), link(b, d), link(c, d)]
  } else {
    slots.value = [mk('场景 1', 60, 30), mk('场景 2', 300, 30), mk('场景 3', 60, 150)]
  }
  toast.info('骨架已放好 —— 把场景拖进空位,拖满自动成结构')
}

function removeSlot(id: string): void {
  slots.value = slots.value.filter((s) => s.id !== id)
  slotEdges.value = slotEdges.value.filter((k) => !k.startsWith(`${id}->`) && !k.endsWith(`->${id}`))
}

function rememberGuideOff(): void {
  localStorage.setItem(GUIDE_OFF_KEY, '1')
}

// ── 试跑选中段(control.only;串联另可 toNode,管理页已覆盖)─────
async function tryRunSelected(): Promise<void> {
  const sel = selection.value
  const id = suiteId.value
  if (!id || sel?.kind !== 'unit') return
  const ref = refOf(sel.id)
  try {
    const r = await runSuite(id, { only: [ref] })
    if ('batchId' in r && !('executionId' in r)) {
      void router.push(executionsBatchUrl(r.batchId))
    } else if ('executionId' in r) {
      toast.success(`试跑已发起(#${r.executionId},选中段含上游)`)
      void router.push(`/executions/${r.executionId}`)
    }
  } catch (e) {
    const det = suiteErrDetail(e)
    toast.error(`试跑失败:${(det?.message as string) || (e as Error).message}`)
  }
}

// ── 完成编排(命名转正 → 管理页 / 预检)─────────────────────────
const finishOpen = ref(false)
const finishName = ref('')
const finishDesc = ref('')
const finishNameErr = ref('')
const finishAfter = ref<'manage' | 'run'>('manage')
const finishSummary = ref('')
const finishCheck = ref('')
const finishCheckErr = ref(0)
const finishing = ref(false)

async function openFinish(): Promise<void> {
  if (!suiteId.value) return
  if (saveState.value === 'dirty') await save()
  finishName.value = name.value
  finishDesc.value = description.value
  finishNameErr.value = ''
  const inf = inference.value
  finishSummary.value = `${MODE_LABEL[inf.mode]} · ${mainIds.value.length} 单元`
    + (beforeIds.value.length ? ` + ${beforeIds.value.length} 前置` : '')
    + (afterIds.value.length ? ` + ${afterIds.value.length} 后置` : '')
    + ` · 预计 ${estimateOrchRuns(
      mainIds.value.map((scenarioId) => ({ scenarioId })), { units: units.value })} runs`
  finishCheck.value = '预检中…'
  finishCheckErr.value = 0
  finishOpen.value = true
  try {
    const out = await validateSuite(suiteId.value)
    const errs = out.items.filter((i) => i.level === 'error')
    const warns = out.items.filter((i) => i.level === 'warn')
    finishCheckErr.value = errs.length
    finishCheck.value = errs.length
      ? `${errs.length} 项错误 · ${warns.length} 项提示 —— 仍可保存;运行前须解决错误`
      : warns.length ? `✓ 可运行;${warns.length} 项提示(运行前会再检)` : '✓ 预检通过'
  } catch {
    finishCheck.value = '预检服务不可用(不拦保存)'
    finishCheckErr.value = 0
  }
}

async function saveFinish(): Promise<void> {
  const id = suiteId.value
  if (!id) return
  const trimmed = finishName.value.trim()
  if (!trimmed) {
    finishNameErr.value = '名称必填(1–128 字符)'
    return
  }
  finishNameErr.value = ''
  finishing.value = true
  try {
    if (saveState.value === 'dirty') {
      const ok = await save()
      if (!ok) return
    }
    await patchSuite(id, { name: trimmed, description: finishDesc.value.trim(), clearDraft: true })
    finishOpen.value = false
    if (finishAfter.value === 'run') {
      preflightOpen.value = true
    } else {
      toast.success(`已保存「${trimmed}」`)
      void router.push(`/suites/${id}`)
    }
  } catch (e) {
    const det = suiteErrDetail(e)
    finishNameErr.value = (det?.message as string) || (e as Error).message
  } finally {
    finishing.value = false
  }
}

// ── 预检 → 运行(复用 30;结果同管理页导航)─────────────────────
async function onPreflightRun(): Promise<void> {
  const id = suiteId.value
  if (!id) return
  try {
    const r = await runSuite(id)
    preflightOpen.value = false
    if ('executionId' in r) {
      toast.success(`编排执行已发起(#${r.executionId},${r.units} 个单元)`)
      void router.push(`/executions/${r.executionId}`)
    } else if ('batchId' in r) {
      void router.push(executionsBatchUrl(r.batchId))
    }
  } catch (e) {
    const det = suiteErrDetail(e)
    toast.error(`运行失败:${(det?.message as string) || (e as Error).message}`)
  }
}

function onLocate(scenarioId: string): void {
  if (mainIds.value.includes(scenarioId)) {
    selection.value = { kind: 'unit', id: scenarioId }
  }
}

// 测试边界:jsdom 无法模拟连线手势,单测经此 seam 驱动同一逻辑
defineExpose({ addEdge, addUnit })
</script>

<style scoped>
/* 容器与管理页/列表页同款节奏(.slib 规范:1480 居中 + 56/32/48) */
.scp {
  box-sizing: border-box; max-width: 1480px; min-width: 0;
  margin: 0 auto; padding: 56px 32px 48px;
  display: flex; flex-direction: column; gap: 12px;
}
.scp-loading { padding: 40px; color: var(--color-text-secondary); }

.scp-head { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.scp-head-main { flex: 1 1 360px; display: flex; flex-direction: column; gap: 2px; }
.scp-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.scp-name {
  font-size: 22px; font-weight: 600; color: inherit; width: 300px;
  border: 1px solid transparent; border-radius: 6px; padding: 0 6px;
  margin-left: -6px; background: transparent;
}
.scp-name:hover, .scp-name:focus { border-color: rgb(199 210 254); background: #fff; }
.scp-save { font-size: 12px; color: var(--color-text-secondary); }
.scp-actions { display: flex; gap: 10px; }
.scp-ghost {
  height: 36px; padding: 0 14px; border: 1px solid rgb(199 210 254);
  border-radius: 6px; background: var(--accent-soft); color: #4338ca;
  font: inherit; font-weight: 600; cursor: pointer;
}
.scp-ghost:disabled { border-color: var(--color-border-tertiary); background: #fff; color: var(--color-text-tertiary); cursor: not-allowed; }
.scp-primary {
  height: 36px; padding: 0 16px; border: 0; border-radius: 6px;
  background: #4338ca; color: #fff; font: inherit; font-weight: 600; cursor: pointer;
}
.scp-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.scp-cols {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch;
}
.scp-center { flex: 999 1 640px; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.scp-rail {
  flex: 1 1 260px; max-width: 320px; border: 1px solid var(--color-border-tertiary); border-radius: 10px;
  padding: 14px; display: flex; flex-direction: column; gap: 10px;
  background: #fff; color: var(--color-text-primary);
}

.scp-strip {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 8px 12px; border: 1px dashed var(--color-border-secondary); border-radius: 8px; background: #fff;
  min-height: 36px;
}
.scp-strip-title { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.scp-strip-hint { font-size: 12px; color: var(--color-text-tertiary); }
.scp-strip-chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px;
  border-radius: 4px; background: #f8fafc; border: 1px solid var(--color-border-tertiary); font-size: 12px;
}
.scp-strip-chip .mono { color: var(--color-text-secondary); font-size: 11px; }
.scp-strip-chip button { border: 0; background: none; cursor: pointer; color: var(--color-text-secondary); }

.scp-canvas {
  position: relative; height: 500px; overflow: hidden;
  border: 1px solid var(--color-border-tertiary); border-radius: 10px; background: #fff;
}
.scp-canvas :deep(.vue-flow__pane) {
  background-image: radial-gradient(var(--color-border-tertiary) 1px, transparent 1px);
  background-size: 16px 16px;
}
.scp-empty {
  position: absolute; left: 140px; top: 40%; z-index: 4; pointer-events: none;
  width: 260px; padding: 18px; box-sizing: border-box;
  border: 2px dashed var(--accent-soft-border); border-radius: 10px; background: var(--accent-soft);
  display: flex; flex-direction: column; align-items: center; gap: 2px; color: #4338ca;
}
.scp-empty strong { font-weight: 600; }
.scp-empty span { font-size: 12px; color: var(--color-text-secondary); }
.scp-cycle {
  position: absolute; right: 14px; bottom: 14px; z-index: 5; max-width: 320px;
  padding: 8px 10px; border-radius: 6px; background: #fee2e2; color: #991b1b;
  font-size: 12px; box-shadow: 0 1px 6px rgb(67 56 202 / 12%);
}

.scu {
  width: 176px; height: 56px; box-sizing: border-box; padding: 6px 12px;
  border: 1px solid var(--color-border-secondary); border-radius: 8px; background: #fff; color: var(--color-text-primary);
  display: flex; flex-direction: column; justify-content: center; cursor: grab;
}
.scu.sel { border: 2px solid #4338ca; box-shadow: 0 1px 6px rgb(67 56 202 / 12%); }
.scu-ref { font-size: 11px; color: #4338ca; }
.scu-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.scu-handle {
  width: 10px !important; height: 10px !important; right: -6px !important;
  border: 2px solid #4338ca !important; background: #fff !important;
}
.scu-handle-in {
  width: 8px !important; height: 8px !important; left: -5px !important;
  border: 2px solid var(--accent-soft-border) !important; background: #fff !important;
}
.scs {
  width: 150px; height: 48px; box-sizing: border-box; padding: 6px 12px;
  border: 1.5px dashed #4338ca; border-radius: 8px; background: var(--accent-soft);
  opacity: 0.85; display: flex; align-items: center; justify-content: center; gap: 6px;
}
.scs-label { color: #4338ca; font-size: 12.5px; font-weight: 600; }
.scs-x { border: 0; background: none; color: var(--color-text-tertiary); cursor: pointer; font-size: 14px; }
.scstart {
  width: 88px; height: 40px; border-radius: 9999px; background: var(--color-text-primary); color: #f5f3ff;
  display: flex; align-items: center; justify-content: center; font-weight: 600;
}

.scp-status {
  display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
  padding: 10px 14px; border: 1px solid var(--accent-soft-border); border-radius: 8px; background: #fff;
}
.scp-status-label { font-size: 12px; color: var(--color-text-secondary); }
.scp-mode-chip {
  padding: 2px 10px; border-radius: 4px; background: var(--accent-soft); color: #4338ca;
  font-weight: 600;
}
.scp-stats { font-size: 12px; }
.scp-why { flex: 1 1 240px; font-size: 12px; color: var(--color-text-secondary); }
.scp-q {
  width: 24px; height: 24px; border: 1px solid var(--accent-soft-border); border-radius: 9999px;
  background: #fff; color: #4338ca; font-weight: 600; cursor: pointer;
}

.scp-rail-title { margin: 0; font-size: 14px; font-weight: 600; }
.scp-steps { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; color: var(--color-text-secondary); }
.scp-steps b { color: var(--color-text-primary); }
.scp-rail-note { margin: 0; font-size: 12px; color: var(--color-text-secondary); }
.scp-linklike { border: 0; background: none; color: #4338ca; cursor: pointer; padding: 0; font-size: 12px; }
.scp-rail-cap { font-size: 11px; color: var(--color-text-secondary); }
.scp-sel-title { font-size: 14px; font-weight: 600; }
.scp-sel-sid { font-size: 11px; color: var(--color-text-tertiary); }
.scp-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 500; color: var(--color-text-secondary); }
.scp-field-label { font-weight: 500; }
.scp-ref-in, .scp-finish input {
  height: 30px; padding: 0 8px; border: 1px solid var(--color-border-tertiary); border-radius: 6px;
  font: inherit; font-size: 12.5px; color: var(--color-text-primary);
}
.scp-danger {
  height: 30px; border: 1px solid var(--color-border-tertiary); border-radius: 6px;
  background: #fff; color: #ef4444; font: inherit; font-size: 12px; cursor: pointer;
}

.scp-fmask {
  position: fixed; inset: 0; z-index: 70; display: flex; align-items: center;
  justify-content: center; background: rgb(15 23 42 / 45%); padding: 16px;
}
.scp-finish {
  width: min(420px, 100%); background: #fff; border: 1px solid var(--accent-soft-border); border-radius: 10px;
  padding: 16px; display: flex; flex-direction: column; gap: 10px; color: var(--color-text-primary);
  box-shadow: 0 20px 50px rgb(0 0 0 / 12%);
}
.scp-finish h2 { margin: 0; font-size: 14px; }
.scp-ferr { color: #dc2626; font-size: 12px; }
.scp-fsummary {
  padding: 8px 10px; border-radius: 6px; background: #f8fafc; font-size: 12px;
}
.scp-fcheck { font-size: 12px; color: #166534; }
.scp-fcheck.bad { color: #b45309; }
.scp-fafter { margin: 0; padding: 0; border: 0; display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.scp-fafter legend { font-weight: 500; color: var(--color-text-secondary); margin-bottom: 4px; }
.scp-facts { display: flex; justify-content: flex-end; gap: 8px; }

.mono { font-family: ui-monospace, Menlo, monospace; }
</style>
