<!--
  CaseComposer.vue — V3 用例编排专用页面 (现代化设计版)
  严格按 PRD-case-composer.md §4 实现:
  - 一个页面承载 4 步流程 (Meta / Resource / Config / Canvas)
  - TopNav + 页内 stepper-bar + footer 导航三段式布局 (4 步共享同一 head)
  - ④ Canvas 内嵌选接口的 Catalog Panel (匹配原型图 content.png)
  - Case 层已解散: Scenario 即执行主体,数据集直接挂场景
  - 顶部 action 区: 收藏 / 复制 / 删除 / 运行

  视觉规范:
  - Heroicons-style 24px SVG icons
  - 8px grid spacing, rounded-xl (12px) cards
  - Subtle elevation (1px border + 0/2/8 shadow)
  - 渐变 accent (indigo 500→600)
  - Inter 字体
-->
<template>
  <div class="composer-shell" :class="{ 'has-run-open': runDialogOpen }">
    <!-- ═══════ Top action bar (sticky) ═══════ -->
    <header class="topbar">
      <div class="topbar-inner">
        <button class="back-btn" @click="$router.push('/scenarios')" title="返回场景库">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
        </button>
        <div class="title-block">
          <div class="crumb">
            <span @click="$router.push('/scenarios')">场景库</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6"/></svg>
            <span class="scenario-id">{{ definition.scenarioId }}</span>
          </div>
          <h1 class="title">
            {{ meta.name || '未命名编排' }}
            <span v-if="scenario?.starred" class="star-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              已收藏
            </span>
          </h1>
        </div>

        <div class="topbar-actions">
          <!-- Status indicator -->
          <div class="save-state" :class="saveState">
            <span class="dot"></span>
            <span class="label">
              <template v-if="saveState === 'saving'">保存中…</template>
              <template v-else-if="saveState === 'dirty'">未保存</template>
              <template v-else-if="lastSavedAt">{{ relTime(lastSavedAt) }} 已保存</template>
              <template v-else>草稿</template>
            </span>
          </div>

          <button class="icon-btn" :class="{ active: scenario?.starred }" @click="onToggleStar" title="收藏">
            <svg width="18" height="18" viewBox="0 0 24 24" :fill="scenario?.starred ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
          </button>
          <button class="icon-btn" @click="onDuplicate" title="复制">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
            </svg>
          </button>
          <button class="icon-btn danger" @click="onDelete" title="删除">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
            </svg>
          </button>

          <div class="divider"></div>

          <!-- 导出菜单 — 在每个 step 都可见,平台侧始终持有当前 draft -->
          <ScenarioExportMenu variant="topbar" />

          <button class="primary-btn" :disabled="!canRun" @click="runDialogOpen = true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            运行
          </button>
        </div>
      </div>
    </header>

    <!-- System-mismatch warning (PRD §5.1 §9) -->
    <div v-if="systemMismatch" class="system-warn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <span><strong>系统不匹配:</strong> {{ systemMismatch }}</span>
    </div>

    <!-- ═══════ Stepper (glassmorphic sticky) ═══════ -->
    <div class="stepper-bar">
      <div
        class="stepper-inner"
        :style="{ '--progress': progressPct }"
      >
        <div
          v-for="(s, i) in STEPS"
          :key="s.key"
          class="step"
          :class="{ active: i === stepIdx, done: i < stepIdx, pending: i > stepIdx }"
          @click="onStepClick(i)"
        >
          <div class="step-dot">
            <svg v-if="i < stepIdx" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <div class="step-info">
            <div class="step-label">{{ s.label }}</div>
            <div class="step-hint">{{ s.hint }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ Body (4 步 sub-views) ═══════ -->
    <main class="body">
      <transition name="slide" mode="out-in">
        <!-- ① Meta -->
        <CaseComposerMeta
          v-if="stepIdx === 0"
          key="meta"
          v-model="definition.meta"
        />

        <!-- ② Resource -->
        <CaseComposerResource
          v-else-if="stepIdx === 1"
          key="resource"
          v-model:resource="definition.resource"
          v-model:resource-meta="orchestration.resourceMeta"
        />

        <!-- ③ Config -->
        <CaseComposerConfig
          v-else-if="stepIdx === 2"
          key="config"
          v-model="definition.config"
        />

        <!-- ④ Canvas -->
        <CaseComposerCanvas
          v-else
          key="canvas"
          v-model:steps="definition.steps"
          v-model:orchestration="orchestration"
          :scenario="scenario"
        />
      </transition>
    </main>

    <!-- ═══════ Footer nav-bar (下/上步, 保存, 验证) ═══════ -->
    <footer class="footer">
      <div class="footer-inner">
        <button class="ghost-btn" :disabled="stepIdx === 0 || saving" @click="onStepClick(stepIdx - 1)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          上一步：{{ STEPS[stepIdx - 1]?.label }}
        </button>

        <div class="footer-center">
          <button class="ghost-btn" :disabled="saving" @click="onPreview">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            预校验 Plate
          </button>
          <button class="primary-btn outline" :disabled="saving" @click="saveDraft(false)">
            <svg v-if="!saving" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/></svg>
            <svg v-else class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
            保存草稿
          </button>
        </div>

        <button
          v-if="stepIdx < STEPS.length - 1"
          class="primary-btn"
          @click="onStepClick(stepIdx + 1)"
        >
          下一步：{{ STEPS[stepIdx + 1].label }}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
        <button
          v-else
          class="primary-btn"
          :disabled="!canRun"
          @click="runDialogOpen = true"
        >
          下一步：运行
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        </button>
      </div>
    </footer>

    <!-- ═══════ Run dialog (env + data-set picker) ═══════ -->
    <RunDialog
      v-if="runDialogOpen"
      :scenario="scenario"
      :data-sets="dataSets"
      :envs="envs"
      :running="runDispatching"
      :last-run-id="lastRunId"
      :last-run-error="lastRunError"
      @close="runDialogOpen = false"
      @confirm="onRunConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ScenarioExportMenu from '@/components/ScenarioExportMenu.vue'
import CaseComposerMeta from '@/components/composer/CaseComposerMeta.vue'
import CaseComposerResource from '@/components/composer/CaseComposerResource.vue'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { showError } from '@/utils/errorFallback'
import { relTime } from '@/utils/datetime'
import { executionUrl, composerUrl } from '@/utils/links'
import { confirmAction } from '@/utils/confirmAction'
import * as api from '@/api/scenario-composer'
import type { MergePolicy } from '@/api/executions'
import type {
  Scenario, DataSetSummary, RunEnv, Orchestration, ScenarioDraft,
} from '@/types/scenario-composer'
import type { ScenarioView, StepView } from '@/types/plate'

const STEPS = [
  { key: 'meta',     label: '基本信息',    hint: 'scenarioId / name / system / owner' },
  { key: 'resource', label: '资源',        hint: 'mock / file' },
  { key: 'config',   label: '配置',        hint: 'timePolicy / retry / services / vars' },
  { key: 'canvas',   label: '步骤编辑',    hint: '从接口目录选接口, 编排业务流程' },
] as const

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()

const stepIdx = ref(0)
const scenarioId = computed(() => route.params.scenarioId as string | undefined)
const saving = ref(false)
const dirty = ref(false)
const lastSavedAt = ref<Date | null>(null)
const saveState = ref<'clean' | 'dirty' | 'saving'>('clean')

const scenario = ref<Scenario | null>(null)
const dataSets = ref<DataSetSummary[]>([])
const envs = ref<RunEnv[]>([])

// Local draft state — 容器: definition(plate) + orchestration(平台)
const definition = ref<ScenarioView>({
  kind: 'scenario',
  scenarioId: 'sc-new',
  meta: {
    name: '',
    description: '',
    module: '',
    priority: 1,
    author: '',
    owner: '',
    tags: [],
    version: 'v0.1.0',
    createTime: new Date().toISOString(),
    expire: false,
    requirementRef: [],
    system: ['fin'],
  },
  config: {
    setup: [],
    teardown: [],
    services: {},
    users: {},
    timePolicy: { kind: 'record' },
    retry: null,
    vars: {},
  },
  resource: {},
  steps: [],
})
const orchestration = ref<Orchestration>({
  steps: [],
  resourceMeta: {},
})

// 便利 getter (模板顶部 crumb / 标题 / canRun 用)
const meta = computed(() => definition.value.meta)
const steps = computed(() => definition.value.steps)

// Run dialog
const runDialogOpen = ref(false)
const runDispatching = ref(false)
const lastRunId = ref<string | null>(null)
const lastRunError = ref<string | null>(null)

const canRun = computed(() => !!scenario.value && steps.value.length > 0)

// 步骤条进度 (0% → 100%) — 当前 step 之前的部分用绿色,之后用灰色
const progressPct = computed(() => {
  const total = STEPS.length - 1
  if (total <= 0) return '0%'
  return `${Math.min(100, Math.max(0, (stepIdx.value / total) * 100))}%`
})

// Mark dirty on any draft change
watch([definition, orchestration], () => {
  if (saveState.value !== 'saving') {
    dirty.value = true
    saveState.value = 'dirty'
  }
}, { deep: true })

// ── 把进行中对象同步到共享 draft store (任意 step / 任意时刻都可达) ──
const draftStore = useScenarioDraftStore()
watch(
  [definition, orchestration, scenario],
  () => {
    draftStore.setDraft({
      definition: definition.value,
      orchestration: orchestration.value,
      scenarioId: scenario.value?.meta?.scenarioId ?? null,
    })
  },
  { deep: true, immediate: true },
)

// ── lifecycle ──
onMounted(async () => {
  const stepParam = parseInt(route.query.step as string) || 1
  stepIdx.value = Math.max(0, Math.min(3, stepParam - 1))

  if (scenarioId.value && scenarioId.value !== 'new') {
    await loadScenario()
  }
  await loadEnvs()
  // Auto-compute system warning (PRD §5.1 §9): declared systems vs
  // services actually called by steps.
  if (scenario.value) checkSystemMismatch()
})

// 运行成功后跳详情页的延迟定时器 — 组件卸载时必须清除，否则用户在
// 800ms 内手动离开后仍会被强行拉去 /executions/{id}。
let runNavTimer: ReturnType<typeof setTimeout> | null = null
onUnmounted(() => {
  if (runNavTimer !== null) {
    clearTimeout(runNavTimer)
    runNavTimer = null
  }
})

/** Compare meta.system (declared) with the union of step services
 *  (actual). Mismatch is a yellow warning, not a hard error — the
 *  user can have a scenario that declares only `fin` but happens to
 *  call a `common.monitor` mock, for example. */
const systemMismatch = ref<string>('')
function checkSystemMismatch() {
  if (!scenario.value) return
  const declared = new Set(scenario.value.meta.system || [])
  const actual = new Set<string>()
  for (const s of scenario.value.steps as any[]) {
    const svc = (s.api && s.api.service) || ''
    if (svc.includes('.')) actual.add(svc.split('.')[0])
    else if (svc) actual.add(svc)
  }
  const missing = [...actual].filter(s => !declared.has(s) && s !== 'common')
  const extra = [...declared].filter(s => !actual.has(s) && s !== 'common')
  const parts: string[] = []
  if (missing.length) parts.push(`steps 调用了未声明的系统: ${missing.join(', ')}`)
  if (extra.length) parts.push(`声明但未使用的系统: ${extra.join(', ')}`)
  systemMismatch.value = parts.join(' · ')
}

watch(() => route.query.step, (q) => {
  if (q) {
    const n = parseInt(q as string)
    if (!isNaN(n)) stepIdx.value = Math.max(0, Math.min(3, n - 1))
  }
})

async function loadScenario() {
  try {
    const s = await api.getScenario(scenarioId.value!)
    scenario.value = s
    // 读侧返回 {meta, steps(plate dict), ...};重建 definition(plate 结构)
    const prevConfig = definition.value.config
    const prevResource = definition.value.resource
    definition.value = {
      kind: 'scenario',
      scenarioId: s.meta.scenarioId,
      meta: {
        name: s.meta.name,
        description: s.meta.description,
        module: s.meta.module,
        priority: s.meta.priority,
        author: s.meta.author,
        owner: s.meta.owner,
        tags: s.meta.tags || [],
        version: s.meta.version || 'v0.1.0',
        createTime: s.meta.createTime || new Date().toISOString(),
        expire: s.meta.expire ?? false,
        requirementRef: [],
        system: s.meta.system || ['fin'],
      },
      config: (s as any).config ?? prevConfig,
      resource: (s as any).resource ?? prevResource,
      steps: (s.steps || []) as unknown as StepView[],
    }
    // orchestration 与 definition.steps 同序同长。
    // 优先用持久化值 (s.orchestration);缺失或长度不齐 (编辑过步骤后过期)
    // 时回退到默认重建 (全启用、展示名空、resourceMeta 空),保证 index 对齐。
    const persistedOrch = s.orchestration
    const inSync = persistedOrch
      && persistedOrch.steps.length === definition.value.steps.length
    orchestration.value = inSync
      ? { steps: persistedOrch!.steps, resourceMeta: persistedOrch!.resourceMeta ?? {} }
      : {
          steps: definition.value.steps.map(() => ({ enabled: true, name: '' })),
          resourceMeta: {},
        }
    await loadDataSets()
    saveState.value = 'clean'
  } catch (e) {
    showError('加载场景', undefined, (e as Error).message)
  }
}

/** 数据集直接挂场景(Case 层已解散)— 只需拉列表,无需自动建 1:1 配套行 */
async function loadDataSets() {
  if (!scenario.value) return
  try {
    dataSets.value = await api.listDataSets({
      scenarioId: scenario.value.meta.scenarioId,
    })
  } catch (e) {
    showError('加载数据集', undefined, (e as Error).message)
  }
}

async function loadEnvs() {
  try {
    envs.value = await api.listEnvs()
  } catch { /* leave empty */ }
}

// ── navigation ──
function onStepClick(idx: number) {
  if (idx === stepIdx.value) return
  if (idx > stepIdx.value && dirty.value) {
    // Auto-save before advancing
    saveDraft(false)
  }
  stepIdx.value = idx
  router.replace({
    path: route.path,
    query: { ...route.query, step: String(idx + 1) },
  }).catch(() => { /* dup nav */ })
}

// ── save / load / delete ──

/** 新建场景时生成唯一 scenarioId(满足后端正则 ^sc-[a-z0-9-]+$,3–128)。
 *  格式: sc-<name-slug>-<6位base36时间戳><3位随机>。
 *  slug 取 name 转小写、非 [a-z0-9] 替换为 -,合并去首尾;为空用 'scenario'。
 *  后端把此 id 作 DB 主键原样采用;撞了返 409,调用方捕获后重生成。 */
function genScenarioId(name: string): string {
  const slug = (name || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'scenario'
  const ts = Date.now().toString(36).slice(-6)
  const rnd = Math.floor(Math.random() * 36 * 36 * 36).toString(36).padStart(3, '0')
  const id = `sc-${slug}-${ts}${rnd}`
  return id.length > 128 ? id.slice(0, 128) : id
}

async function saveDraft(advance = false) {
  if (!meta.value.name) {
    // scenarioId 不再前端必填校验:新建时自动生成,编辑时由路由回填并锁定。
    ElMessage.warning('请先在 ① 基本信息 中填写 name')
    onStepClick(0)
    return
  }
  // 新建场景:生成唯一 id 替换占位 'sc-new'。后端以此 id 作 DB 主键原样采用。
  // 编辑场景:definition.scenarioId 已由 loadScenario 从路由回填,update 时锁定不变。
  if (!scenario.value && definition.value.scenarioId === 'sc-new') {
    definition.value.scenarioId = genScenarioId(meta.value.name)
  }
  saving.value = true
  saveState.value = 'saving'
  try {
    // 容器草稿:definition(plate) + orchestration(平台渲染)
    const draft: ScenarioDraft = {
      definition: definition.value,
      orchestration: orchestration.value,
    }
    let saved: Scenario | undefined
    if (scenario.value) {
      saved = await store.saveScenario(scenario.value.meta.scenarioId, draft)
    } else {
      // create:撞 id 时后端返 409 (scenario_id_exists),重生成 id 重试(最多 2 次)。
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          saved = await store.saveScenario(null, draft)
          break
        } catch (e: any) {
          if (attempt < 2 && /scenario_id_exists|409/.test(String(e?.message || e))) {
            definition.value.scenarioId = genScenarioId(meta.value.name)
            draft.definition = definition.value
            continue
          }
          throw e
        }
      }
      if (!saved) throw new Error('create failed: id 撞号重试耗尽')
    }
    scenario.value = saved
    // 新建场景后拉一次数据集列表(空列表,但保持状态一致)
    if (!dataSets.value.length) await loadDataSets()
    lastSavedAt.value = new Date()
    dirty.value = false
    saveState.value = 'clean'
    if (advance) {
      onStepClick(Math.min(STEPS.length - 1, stepIdx.value + 1))
    }
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onToggleStar() {
  if (!scenario.value) return
  try {
    await store.toggleStar(scenario.value.meta.scenarioId)
    scenario.value = { ...scenario.value, starred: !scenario.value.starred }
  } catch (e) {
    showError('操作', undefined, (e as Error).message)
  }
}

async function onDuplicate() {
  if (!scenario.value) return
  const ok = await confirmAction(
    `复制 "${scenario.value.meta.name}" 为新场景?`,
    '复制场景',
    { type: 'info' },
  )
  if (!ok) return // 用户取消或 ESC 关闭
  try {
    // 复制统一走服务端 copyScenario(生成唯一新 id),
    // 不再本地拼 `${id}-copy`(重复复制会撞号)。
    const saved = await store.copyScenario(scenario.value.meta.scenarioId)
    ElMessage.success('已复制')
    router.push(composerUrl(saved.meta.scenarioId))
  } catch (e) {
    showError('复制', undefined, (e as Error).message)
  }
}

async function onDelete() {
  if (!scenario.value) return
  const ok = await confirmAction(
    `确定删除场景 "${scenario.value.meta.name}"? 此操作不可恢复。`,
    '删除场景',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' },
  )
  if (!ok) return // 用户取消或 ESC 关闭
  try {
    await store.removeScenario(scenario.value.meta.scenarioId)
    ElMessage.success('已删除')
    router.push('/scenarios')
  } catch (e) {
    showError('删除', undefined, (e as Error).message)
  }
}

async function onPreview() {
  if (!meta.value.name) {
    ElMessage.warning('请先填写 name')
    return
  }
  // 新建场景:预校验也要发真实 id 给 plate /convert(替换占位 'sc-new')。
  if (!scenario.value && definition.value.scenarioId === 'sc-new') {
    definition.value.scenarioId = genScenarioId(meta.value.name)
  }
  saving.value = true
  try {
    const draft: ScenarioDraft = {
      definition: definition.value,
      orchestration: orchestration.value,
    }
    const res = await api.previewPlateDraft(draft)
    if (res.ok) {
      ElMessage.success('Plate 预校验通过 ✓')
    } else {
      ElMessage.warning(`Plate 校验失败: ${res.errors?.length || 0} 个错误`)
    }
  } catch (e) {
    showError('预校验', undefined, (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onRunConfirm(
  envId: string,
  dataSetIds: string[],
  opts?: {
    stepTo?: number | null
    injectCredentials: boolean
    nRuns?: number
    parallel?: number
    prefix?: string
    mergePolicy?: MergePolicy
  },
) {
  if (!scenario.value) {
    ElMessage.warning('请先保存草稿')
    return
  }
  runDispatching.value = true
  lastRunError.value = null
  try {
    const env = envs.value.find(e => e.envId === envId) || { envId, name: envId, baseUrl: '' }
    const resp = await api.runScenario({
      scenarioId: scenario.value.meta.scenarioId,
      dataSetIds,
      env,
      // V1 能力移植:stepTo(引擎 halt_at)与凭证注入开关;仅在
      // 非默认时上送,保持旧后端兼容。
      ...(opts?.stepTo != null ? { stepTo: opts.stepTo } : {}),
      ...(opts && opts.injectCredentials === false
        ? { injectCredentials: false } : {}),
      // M1 执行能力:nRuns/parallel/prefix/mergePolicy,同样仅在
      // 非默认时上送。
      ...(opts?.mergePolicy ? { mergePolicy: opts.mergePolicy } : {}),
      ...(opts?.nRuns && opts.nRuns > 1 ? { nRuns: opts.nRuns } : {}),
      ...(opts?.parallel && opts.parallel > 1 ? { parallel: opts.parallel } : {}),
      ...(opts?.prefix ? { prefix: opts.prefix } : {}),
    })
    lastRunId.value = resp.runId
    ElMessage.success(`运行已发起: ${resp.runId}`)
    runDialogOpen.value = false
    // Jump straight to the execution detail page. Older backends don't
    // return executionId — fall back to the list. runDispatching stays
    // true until navigation so the confirm button can't double-fire in
    // the 800ms toast window.
    runNavTimer = setTimeout(() => {
      runNavTimer = null
      runDispatching.value = false
      if (resp.executionId != null) router.push(executionUrl(resp.executionId))
      else router.push('/executions')
    }, 800)
  } catch (e) {
    lastRunError.value = (e as Error).message
    showError('运行', undefined, (e as Error).message)
    runDispatching.value = false
  }
}
</script>

<style scoped>
/* ═══════ Shell ═══════ */
.composer-shell {
  min-height: 100vh;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f6fa 100%);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
  color: #1a1d24;
  display: flex;
  flex-direction: column;
}

/* ═══════ Top action bar ═══════ */
.topbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid #e6e8ec;
  position: sticky;
  top: 0;
  z-index: 50;
}
.topbar-inner {
  display: flex; align-items: center; gap: 12px;
  padding: 10px clamp(16px, 3vw, 48px);
  max-width: min(100%, 1800px);
  margin: 0 auto;
}
.back-btn {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.back-btn:hover { background: #f5f6fa; color: #1a1d24; }

.title-block { flex: 1; min-width: 0; }
.crumb {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #5a6273;
  margin-bottom: 2px;
}
.crumb span { cursor: pointer; transition: color 0.15s; }
.crumb span:hover { color: #4f46e5; }
.scenario-id { color: #1a1d24; font-weight: 600; }
.title {
  margin: 0; font-size: 18px; font-weight: 700; color: #1a1d24;
  display: flex; align-items: center; gap: 8px;
}
.star-pill {
  display: inline-flex; align-items: center; gap: 4px;
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: #fff; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px;
}

.topbar-actions { display: flex; align-items: center; gap: 8px; }

.save-state {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: #f5f6fa; border-radius: 999px;
  font-size: 12px; color: #5a6273;
  margin-right: 8px;
}
.save-state .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #10b981; transition: all 0.2s;
}
.save-state.saving .dot { background: #f59e0b; animation: pulse 1s infinite; }
.save-state.dirty .dot { background: #ef4444; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.icon-btn {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.icon-btn:hover { background: #f5f6fa; color: #1a1d24; }
.icon-btn.active { color: #f59e0b; border-color: #fbbf24; background: #fffbeb; }
.icon-btn.danger:hover { color: #ef4444; border-color: #fecaca; background: #fef2f2; }

.divider { width: 1px; height: 24px; background: #e6e8ec; margin: 0 4px; }

.primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border: none; border-radius: 8px;
  padding: 8px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.2);
}
.primary-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.primary-btn.outline { background: #fff; color: #4f46e5; border: 1px solid #c7d2fe; box-shadow: none; }
.primary-btn.outline:hover { background: #eef2ff; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.ghost-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.ghost-btn:hover { background: #f5f6fa; color: #1a1d24; }
.ghost-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ═══════ Stepper (4 步) ═══════ */
.stepper-bar {
  background: #fff;
  border-bottom: 1px solid #e6e8ec;
  position: sticky; top: 60px; z-index: 40;
}
.stepper-inner {
  --pad: clamp(16px, 3vw, 48px);
  --dot-offset: 32px; /* step padding-left (16) + dot 半径 (16) */
  position: relative;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  padding: 16px var(--pad);
  max-width: min(100%, 1800px); margin: 0 auto;
}
/* 贯穿整行的连续横线 — 用 --progress CSS 变量驱动已完成 vs 未完成的渐变 */
.stepper-inner::before {
  content: '';
  position: absolute;
  left: calc(var(--pad) + var(--dot-offset));
  right: calc(var(--pad) + var(--dot-offset));
  top: 50%;
  height: 2px;
  transform: translateY(-50%);
  background: linear-gradient(
    to right,
    #10b981 0%,
    #10b981 var(--progress, 0%),
    #e6e8ec var(--progress, 0%),
    #e6e8ec 100%
  );
  z-index: 0;
  pointer-events: none;
}
.step {
  position: relative;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.15s;
  z-index: 1;
}
.step:hover { background: #f5f6fa; }
.step-dot {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: #f1f5f9; color: #94a3b8;
  font-weight: 700; font-size: 14px;
  transition: all 0.2s;
  flex-shrink: 0;
}
.step-label { font-size: 14px; font-weight: 600; color: #1a1d24; }
.step-hint { font-size: 11px; color: #94a3b8; margin-top: 1px; }
.step.active { background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border-radius: 12px; }
.step.active .step-dot { background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); color: #fff; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3); }
.step.active .step-label { color: #4f46e5; }
.step.done .step-dot { background: #10b981; color: #fff; }
.step.done .step-label { color: #10b981; }

/* ═══════ Body ═══════ */
.body {
  flex: 1;
  padding: 28px clamp(16px, 3vw, 48px) 120px;
  max-width: min(100%, 1800px);
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

/* ═══════ Footer nav-bar ═══════ */
.footer {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: saturate(180%) blur(20px);
  border-top: 1px solid #e6e8ec;
  position: sticky; bottom: 0; z-index: 30;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.04);
}
.footer-inner {
  display: flex; align-items: center; gap: 12px;
  padding: 12px clamp(16px, 3vw, 48px);
  max-width: min(100%, 1800px); margin: 0 auto;
}
.footer-center {
  flex: 1; display: flex; gap: 8px; justify-content: center;
}

/* ═══════ Slide transition ═══════ */
.slide-enter-active, .slide-leave-active {
  transition: all 0.25s ease-out;
}
.slide-enter-from { opacity: 0; transform: translateY(8px); }
.slide-leave-to { opacity: 0; transform: translateY(-8px); }

/* System-mismatch warning */
.system-warn {
  display: flex; align-items: center; gap: 8px;
  background: #fef3c7; border: 1px solid #fbbf24; border-left: 4px solid #f59e0b;
  color: #92400e; padding: 10px 16px; margin: 8px 24px;
  border-radius: 8px; font-size: 13px;
}
.system-warn svg { color: #f59e0b; flex-shrink: 0; }
.system-warn strong { color: #92400e; }
</style>
