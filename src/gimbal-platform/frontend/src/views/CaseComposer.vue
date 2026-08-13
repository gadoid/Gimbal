<!--
  CaseComposer.vue — V3 用例编排专用页面 (现代化设计版)
  严格按 PRD-case-composer.md §4 实现:
  - 一个页面承载 4 步流程 (Meta / Resource / Config / Canvas)
  - TopNav + HeadStepper + NavBar 三段式布局 (4 步共享同一 head)
  - ④ Canvas 内嵌选接口的 Catalog Panel (匹配原型图 content.png)
  - V3 composer 1:1 模型: Scenario 自动创建配套 Case + DataSet
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
            <span class="scenario-id">{{ meta.scenarioId }}</span>
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
              <template v-else-if="lastSavedAt">{{ formatTime(lastSavedAt) }} 已保存</template>
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
          v-model="meta"
        />

        <!-- ② Resource -->
        <CaseComposerResource
          v-else-if="stepIdx === 1"
          key="resource"
          v-model="resource"
        />

        <!-- ③ Config -->
        <CaseComposerConfig
          v-else-if="stepIdx === 2"
          key="config"
          v-model="config"
        />

        <!-- ④ Canvas -->
        <CaseComposerCanvas
          v-else
          key="canvas"
          v-model="steps"
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
      :case-data="caseData"
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import TopNav from '@/components/TopNav.vue'
import ScenarioExportMenu from '@/components/ScenarioExportMenu.vue'
import CaseComposerMeta from '@/components/composer/CaseComposerMeta.vue'
import CaseComposerResource from '@/components/composer/CaseComposerResource.vue'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { showError } from '@/utils/errorFallback'
import * as api from '@/api/scenario-composer'
import type {
  Scenario, ScenarioMeta, ScenarioStep, ScenarioConfig, ScenarioResource,
  Case, DataSetSummary, RunEnv,
} from '@/types/scenario-composer'

const STEPS = [
  { key: 'meta',     label: '基本信息',    hint: 'scenarioId / name / system / owner' },
  { key: 'resource', label: '资源',        hint: 'mock / file / http / custom' },
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
const caseData = ref<Case | null>(null)
const dataSets = ref<DataSetSummary[]>([])
const envs = ref<RunEnv[]>([])

// Local draft state
const meta = ref<ScenarioMeta>({
  scenarioId: 'sc-new',
  name: '',
  description: '',
  module: '',
  priority: 1,
  author: '',
  owner: '',
  tags: [],
  system: ['fin'],
  version: 'v0.1.0',
  expire: false,
})
const resource = ref<ScenarioResource>({ items: [] })
const config = ref<ScenarioConfig>({
  timePolicyKind: 'record',
  retryMaxAttempts: 0,
  retryIntervalMs: 500,
  vars: [],
  services: {},
  users: {},
  setup: [],
  teardown: [],
})
const steps = ref<ScenarioStep[]>([])

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
watch([meta, resource, config, steps], () => {
  if (saveState.value !== 'saving') {
    dirty.value = true
    saveState.value = 'dirty'
  }
}, { deep: true })

// ── 把进行中对象同步到共享 draft store (任意 step / 任意时刻都可达) ──
const draftStore = useScenarioDraftStore()
watch(
  [meta, resource, config, steps, scenario],
  () => {
    draftStore.setDraft({
      meta: meta.value,
      steps: steps.value,
      config: config.value,
      resource: resource.value,
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

/** Compare meta.system (declared) with the union of step services
 *  (actual). Mismatch is a yellow warning, not a hard error — the
 *  user can have a scenario that declares only `fin` but happens to
 *  call a `common.monitor` mock, for example. */
const systemMismatch = ref<string>('')
function checkSystemMismatch() {
  if (!scenario.value) return
  const declared = new Set(scenario.value.meta.system || [])
  const actual = new Set<string>()
  for (const s of scenario.value.steps) {
    const svc = s.service || ''
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
    meta.value = { ...s.meta }
    steps.value = [...s.steps]
    // Load config + resource from the persisted payload if present
    const payload = s as any
    if (payload.config) config.value = { ...config.value, ...payload.config }
    if (payload.resource) resource.value = { ...payload.resource }
    // Load case + data-sets (1:1)
    await loadCase()
    saveState.value = 'clean'
  } catch (e) {
    showError('加载场景失败', undefined, (e as Error).message)
  }
}

async function loadCase() {
  if (!scenario.value) return
  try {
    const cases = await api.listCases({ scenarioId: scenario.value.meta.scenarioId })
    if (cases.length > 0) {
      caseData.value = cases[0]
      dataSets.value = await api.listDataSets({ caseId: cases[0].caseId })
    } else {
      // Auto-create 1:1 case on first load
      caseData.value = await autoCreateCase(scenario.value.meta)
      dataSets.value = []
    }
  } catch (e) {
    showError('加载用例失败', undefined, (e as Error).message)
  }
}

async function autoCreateCase(scenarioMeta: ScenarioMeta): Promise<Case> {
  const caseId = `${scenarioMeta.scenarioId}-case-001`
  const draft: Case = {
    caseId,
    scenarioId: scenarioMeta.scenarioId,
    name: `${scenarioMeta.name} 默认用例`,
    description: '由 composer 自动创建 (1:1 绑定)',
    env: 'dev-local',
    auth: { name: 'default', type: 'bearer' },
    dataSetIds: [],
    createdBy: scenarioMeta.owner || '',
    updatedAt: new Date().toISOString(),
  } as Case
  return await api.createCase(draft)
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
async function saveDraft(advance = false) {
  if (!meta.value.scenarioId || !meta.value.name) {
    ElMessage.warning('请先在 ① 基本信息 中填写 scenarioId 和 name')
    onStepClick(0)
    return
  }
  if (!/^sc-[a-z0-9-]+$/.test(meta.value.scenarioId)) {
    ElMessage.error('scenarioId 必须匹配 ^sc-[a-z0-9-]+$')
    onStepClick(0)
    return
  }
  saving.value = true
  saveState.value = 'saving'
  try {
    const draft = { meta: meta.value, steps: steps.value, config: config.value, resource: resource.value }
    let saved: Scenario
    if (scenario.value) {
      saved = await store.saveScenario(scenario.value.meta.scenarioId, draft)
    } else {
      saved = await store.saveScenario(null, draft)
    }
    scenario.value = saved
    // 1:1 case: ensure a case exists
    if (!caseData.value) await loadCase()
    // Persist case if changed
    if (caseData.value && (caseData.value.env || caseData.value.auth)) {
      try {
        caseData.value = await api.updateCase(caseData.value.caseId, {
          env: caseData.value.env,
          auth: caseData.value.auth,
          dataSetIds: caseData.value.dataSetIds,
        })
      } catch { /* best-effort */ }
    }
    lastSavedAt.value = new Date()
    dirty.value = false
    saveState.value = 'clean'
    if (advance) {
      onStepClick(Math.min(STEPS.length - 1, stepIdx.value + 1))
    }
  } catch (e) {
    showError('保存失败', undefined, (e as Error).message)
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
    showError('操作失败', undefined, (e as Error).message)
  }
}

async function onDuplicate() {
  if (!scenario.value) return
  try {
    await ElMessageBox.confirm(
      `复制 "${scenario.value.meta.name}" 为新场景?`,
      '复制场景',
      { type: 'info' }
    )
    const newId = `${scenario.value.meta.scenarioId}-copy`
    const newMeta = { ...scenario.value.meta, scenarioId: newId, name: `${scenario.value.meta.name} (副本)` }
    const draft = { meta: newMeta, steps: scenario.value.steps, config: config.value, resource: resource.value }
    const saved = await store.saveScenario(null, draft as any)
    ElMessage.success('已复制')
    router.push(`/composer/${saved.meta.scenarioId}?step=1`)
  } catch (e) {
    if ((e as any) === 'cancel') return
    showError('复制失败', undefined, (e as Error).message)
  }
}

async function onDelete() {
  if (!scenario.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除场景 "${scenario.value.meta.name}"? 此操作不可恢复。`,
      '删除场景',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
    )
    await store.removeScenario(scenario.value.meta.scenarioId)
    ElMessage.success('已删除')
    router.push('/scenarios')
  } catch (e) {
    if ((e as any) === 'cancel') return
    showError('删除失败', undefined, (e as Error).message)
  }
}

async function onPreview() {
  if (!meta.value.scenarioId || !meta.value.name) {
    ElMessage.warning('请先填写 scenarioId 和 name')
    return
  }
  saving.value = true
  try {
    const draft = { meta: meta.value, steps: steps.value, config: config.value, resource: resource.value }
    const res = await api.previewPlateDraft(draft as any)
    if (res.ok) {
      ElMessage.success('Plate 预校验通过 ✓')
    } else {
      ElMessage.warning(`Plate 校验失败: ${res.errors?.length || 0} 个错误`)
    }
  } catch (e) {
    showError('预校验失败', undefined, (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onRunConfirm(envId: string, dataSetIds: string[]) {
  if (!caseData.value) {
    ElMessage.warning('请先保存草稿以创建配套用例')
    return
  }
  runDispatching.value = true
  lastRunError.value = null
  try {
    const env = envs.value.find(e => e.envId === envId) || { envId, name: envId, baseUrl: '' }
    const resp = await api.runCase({
      caseId: caseData.value.caseId,
      dataSetIds,
      env,
    } as any)
    lastRunId.value = resp.runId
    ElMessage.success(`运行已发起: ${resp.runId}`)
    runDialogOpen.value = false
    setTimeout(() => router.push('/executions'), 800)
  } catch (e) {
    lastRunError.value = (e as Error).message
    showError('运行失败', undefined, (e as Error).message)
  } finally {
    runDispatching.value = false
  }
}

function formatTime(d: Date) {
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return `${diff} 秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
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
