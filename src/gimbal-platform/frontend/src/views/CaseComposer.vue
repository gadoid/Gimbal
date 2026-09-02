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
  <div ref="rootEl" class="composer-shell" :class="{ 'has-run-open': runDialogOpen }">
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
            <span class="scenario-id">{{ meta.name || definition.scenarioId }}</span>
          </div>
          <h1 class="title" :class="{ expired: meta.expire }">
            {{ meta.name || '未命名编排' }}
            <span v-if="scenario?.starred" class="star-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              已收藏
            </span>
            <!-- ① 基本信息的 expire 实时同步:过期场景顶栏置灰标记 -->
            <span v-if="meta.expire" class="expire-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              已过期
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

          <button class="primary-btn" :disabled="!canRun" @click="openRunDialog">
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
      <div class="body-split" :class="{ 'with-rail': showPoolRail }">
        <div class="body-main">
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
              :services="definition.config?.services ?? {}"
              @update:services="onServicesUpdate"
              @var-promote="onVarPromote"
              @seed-var="seedPoolVar"
            />
          </transition>
        </div>

        <!-- 常量池 rail(步骤 0-2;步骤 3 挂在 Canvas col-info,同一组件) -->
        <aside v-if="showPoolRail" class="pool-rail">
          <ConstantPoolPanel :entries="constantsStore.entries" @seed-var="seedPoolVar" />
        </aside>
      </div>
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
          @click="openRunDialog"
        >
          下一步：运行
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        </button>
      </div>
    </footer>

    <!-- ═══════ Run dialog (方案栏 + ds + 声明∪引用并集绑定行) ═══════ -->
    <RunDialog
      v-if="runDialogOpen"
      :scenario="scenario"
      :data-sets="dataSets"
      :running="runDispatching"
      :last-run-id="lastRunId"
      :last-run-error="lastRunError"
      :step-orchestration-names="stepNames"
      :schemes="runSchemes"
      :last-run-overlay="lastRunOverlay"
      :service-rows="serviceRows"
      :auth-options="authOptions"
      @close="runDialogOpen = false"
      @confirm="onRunConfirm"
      @save-scheme="onSaveScheme"
      @delete-scheme="onDeleteScheme"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ScenarioExportMenu from '@/components/ScenarioExportMenu.vue'
import CaseComposerMeta from '@/components/composer/CaseComposerMeta.vue'
import CaseComposerResource from '@/components/composer/CaseComposerResource.vue'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import ConstantPoolPanel from '@/components/composer/ConstantPoolPanel.vue'
import { provideInsertTarget, useInsertTarget } from '@/composables/useInsertTarget'
import { useSystemPrefill } from '@/composables/useSystemPrefill'
import { seedPoolVarIntoDefinition } from '@/utils/pool-var'
import { deriveSystem } from '@/utils/service-alias'
import { loadCatalogServiceNames, loadCatalogSystemByService } from '@/utils/catalog-services'
import { useConstantsStore } from '@/stores/constants'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { showError } from '@/utils/errorFallback'
import { relTime } from '@/utils/datetime'
import { executionUrl, composerUrl } from '@/utils/links'
import { confirmAction } from '@/utils/confirmAction'
import { lintDraft } from '@/utils/draft-lint'
import * as api from '@/api/scenario-composer'
import { list as listAuthSessions } from '@/api/auth_sessions'
import { listExecutions } from '@/api/executions'
import type {
  RunRequest, RunScheme, RunOverlay, ServiceBinding,
} from '@/api/scenario-composer'
import type {
  Scenario, DataSetSummary, Orchestration, ScenarioDraft,
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

// ── 防抖自动保存(仅已保存过的场景)──────────────────────────
// 编辑停顿 2.5s 自动落库;新建场景(无服务端身份)不自动 — 首存仍手动,
// 防半成品草稿污染场景库。失败静默:指示灯保持「未保存」,下次编辑再试。
const AUTOSAVE_DEBOUNCE_MS = 2500
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

function scheduleAutoSave(): void {
  if (autoSaveTimer !== null) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(() => {
    autoSaveTimer = null
    void maybeAutoSave()
  }, AUTOSAVE_DEBOUNCE_MS)
}

async function maybeAutoSave(): Promise<void> {
  if (!scenario.value || !meta.value.name || !dirty.value) return
  if (saving.value) {
    scheduleAutoSave()   // 手动/步进保存进行中 → 顺延一个窗口再试
    return
  }
  await saveDraft(false, false, true)
}

const scenario = ref<Scenario | null>(null)
const dataSets = ref<DataSetSummary[]>([])

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
/** Orchestration + 运行方案 sidecar 键(后端 Task 10 已收录 runSchemes,
 *  前端 types 侧 Orchestration 尚未补 — 本地交叉类型桥接,不改共享类型)。 */
type OrchestrationWithSchemes = Orchestration & { runSchemes?: RunScheme[] }
const orchestration = ref<OrchestrationWithSchemes>({
  steps: [],
  resourceMeta: {},
})

// ── 选系统预填(仅新建场景)──────────────────────────────
// meta 取 common 通用定义公共项;config 取 common 基座 + 各选中系统
// services/users/vars 合并;resource 取各系统并集。仅首次、且
// config/resource 未被编辑过时生效 — 详见 useSystemPrefill 契约。
const isNewScenario = computed(() => !scenarioId.value || scenarioId.value === 'new')
useSystemPrefill(definition, isNewScenario)

// 便利 getter (模板顶部 crumb / 标题 / canRun 用)
const meta = computed(() => definition.value.meta)
const steps = computed(() => definition.value.steps)

// Run dialog
const runDialogOpen = ref(false)
const runDispatching = ref(false)
const lastRunId = ref<string | null>(null)
const lastRunError = ref<string | null>(null)
/** 上次运行覆盖层(方案栏「上次运行」回填源;openRunDialog 拉取,仅两字段) */
const lastRunOverlay = ref<RunOverlay | null>(null)
// owner 凭证池别名(懒加载:首次打开运行弹框时拉取;失败静默 — 不阻塞运行)
const ownerAuthAliases = ref<string[]>([])

const canRun = computed(() => !!scenario.value && steps.value.length > 0)

/** stepTo 下拉的展示名:平台编排态 orchestration.steps[].name(plate Step 无 name) */
const stepNames = computed(() => orchestration.value.steps.map((s) => s.name))

/** 打开运行弹框:dirty 时先 flush 落库(运行按 scenarioId 取服务端版本,
 *  不 flush 则跑的是最后一次保存的旧编排);flush 失败中止 — 宁可不跑,
 *  不跑旧版。之后先开弹层(网络慢不阻塞交互),再并行拉 上次运行覆盖层
 *  与 owner 凭证池别名(两者失败均静默 — 不阻塞运行)。 */
async function openRunDialog() {
  if (!scenarioId.value) return
  if (scenario.value && dirty.value && meta.value.name) {
    const flushed = await saveDraft(false, false, true)
    if (!flushed) return
  }
  runDialogOpen.value = true
  if (ownerAuthAliases.value.length === 0) {
    listAuthSessions()
      .then((sessions) => { ownerAuthAliases.value = sessions.map((s) => s.alias) })
      .catch(() => { /* 凭证池不可达不阻塞运行 */ })
  }
  // 「上次运行」按持久化 id 查(新建保存后路由仍停留 /scenarios/new,
  // 路由参数查 'new' 恒空 → 回填永不出现);未保存场景无执行历史,跳过。
  const sid = scenario.value?.meta.scenarioId
  if (!sid) return
  try {
    const res = await listExecutions({ scenarioId: sid, limit: 1 })
    const cfg = res.items[0]?.config
    // 只回填 overlay 两字段:envId 已随 D2 退役(历史 config_json 里的
    // envId 键静默忽略);stepTo/nRuns/parallel 等其余 base_config 键
    // 不进方案栏(方案快照语义),两字段全缺 → 视为无可回填。
    lastRunOverlay.value = cfg && (cfg.dataSetIds?.length || cfg.serviceBindings)
      ? { dataSetIds: cfg.dataSetIds ?? [], serviceBindings: cfg.serviceBindings ?? {} }
      : null
  } catch { lastRunOverlay.value = null }
}

// 步骤条进度 (0% → 100%) — 当前 step 之前的部分用绿色,之后用灰色
const progressPct = computed(() => {
  const total = STEPS.length - 1
  if (total <= 0) return '0%'
  return `${Math.min(100, Math.max(0, (stepIdx.value / total) * 100))}%`
})

// Mark dirty on any draft change
// suppressDirty:loadScenario 的整包替换不是编辑 — deep watch 在赋值上
// 同样触发(pre-flush 微任务),不抑制则每次加载都伪 dirty → 加载即自动保存。
// editsDuringSave:保存进行中的编辑 — 不当场翻转 saveState(灯仍显 saving),
// 但 dirty 置位;保存成功后据此不清 dirty,防抖再存最新草稿(编辑不被吞)。
let suppressDirty = false
let editsDuringSave = false
watch([definition, orchestration], () => {
  if (suppressDirty) return
  dirty.value = true
  if (saveState.value === 'saving') {
    editsDuringSave = true   // 灯仍显 saving;保存完成后再转 dirty
  } else {
    saveState.value = 'dirty'
  }
  scheduleAutoSave()   // 编辑即重设防抖窗口(尾随去抖)
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

// ── RunDialog props 装配(Task 12)────────────────────────────────
/** 已存运行方案:orchestration sidecar(Task 10 窄端点专管键,编辑器
 *  PUT 对该键透传保留 — 这里只读,写走 onSaveScheme → putRunSchemes)。 */
const runSchemes = computed<RunScheme[]>(() =>
  (draftStore.draft?.orchestration as OrchestrationWithSchemes | undefined)?.runSchemes ?? [])
/** 绑定行 = 声明 ∪ 引用并集(spec D3):声明行带 declaredUrl,
 *  引用未声明的键 declaredUrl=null(RunDialog 标红可救燃)。
 *  声明源 = definition.config.services(service → URL);引用源 = steps[].api.service。 */
const serviceRows = computed(() => {
  const declared = definition.value.config?.services ?? {}
  const rows = new Map<string, string | null>()
  for (const [k, v] of Object.entries(declared))
    rows.set(k, typeof v === 'string' ? v : null)
  for (const st of (definition.value.steps ?? []) as { api?: { service?: string } }[])
    if (st?.api?.service && !rows.has(st.api.service)) rows.set(st.api.service, null)
  return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
})
/** 绑定下拉选项:owner 凭证池别名 ∪ 场景内置 users 键 */
const authOptions = computed(() => [...new Set([
  ...ownerAuthAliases.value,
  ...Object.keys(definition.value.config?.users ?? {}),
])])

/** Canvas"设为变量"上报:登记共享变量默认值(D8;vars 扁平 name→value,零 schema 变化) */
function onVarPromote(name: string, value: unknown) {
  const config = definition.value.config ?? { vars: {} }
  definition.value = {
    ...definition.value,
    config: { ...config, vars: { ...(config.vars ?? {}), [name]: value } },
  }
}

/** Canvas 内联创建别名双写的声明面落库(config.services 整表替换) */
function onServicesUpdate(services: Record<string, string>) {
  definition.value = {
    ...definition.value,
    config: { ...definition.value.config, services },
  }
}

const constantsStore = useConstantsStore()
const rootEl = ref<HTMLElement | null>(null)
const inserter = useInsertTarget()
provideInsertTarget(inserter)

/** 常量池 rail: 步骤 0-2(步骤 3 面板挂在 Canvas col-info) */
const showPoolRail = computed(() => stepIdx.value < 3)

/** 常量池播种(生成器 key 插入链): 快照拷贝进 config.vars,已存在不覆盖。 */
function seedPoolVar(name: string, spec: Record<string, unknown>): void {
  const result = seedPoolVarIntoDefinition(definition.value, name, spec)
  definition.value = result.definition
  if (!result.seeded) {
    ElMessage.info(`config.vars 已有同名变量 ${name},使用现有值`)
  }
}

// ── 目录服务名集合(别名派生输入, spec D5/§1.6)──
// checkSystemMismatch 经 deriveSystem 派生 step 系统;与 Canvas/Config
// 共享 loader 的模块缓存 — 任一消费者先拉过则此处免费。失败静默降级为
// 空集合/空映射 → 派生退回点前缀启发式(现状行为),不阻塞加载。
const catalogNames = ref<Set<string>>(new Set())
/** 目录权威映射 service → system(endpoint 条目自带 system 字段)。 */
const systemByService = ref<Map<string, string>>(new Map())

// ── 离开防线:dirty 时拦截(自动保存把窗口缩到 ≤2.5s,这里是兜底;
//    新建未保存场景无自动保存,全靠这里)──────────────────────────
function onBeforeUnload(e: BeforeUnloadEvent): void {
  if (!dirty.value) return
  e.preventDefault()
  e.returnValue = ''   // 旧版 Chrome 要求显式赋值才弹原生提示
}

// 三选(distinguishCancelAndClose):确认=保存并离开;cancel=放弃修改并
// 离开;ESC/关闭=留下。无名/未保存过的场景没有「保存并离开」可走 — 确认
// 钮退化为直接离开。保存失败 → 留在页面(错误 toast 由 manual 路径弹出)。
onBeforeRouteLeave(async () => {
  if (!dirty.value) return true
  const canSave = Boolean(scenario.value && meta.value.name)
  try {
    await ElMessageBox.confirm(
      `当前有未保存的修改${canSave ? '' : '(场景尚未保存过)'},离开将丢失本次编辑。`,
      '未保存的修改',
      {
        type: 'warning',
        distinguishCancelAndClose: true,
        confirmButtonText: canSave ? '保存并离开' : '离开',
        cancelButtonText: '放弃修改并离开',
      },
    )
  } catch (action) {
    if (action === 'cancel') return true   // 放弃修改并离开
    return false                           // close(ESC/×)→ 留下
  }
  return canSave ? await saveDraft(false, false, false) : true
})

// ── lifecycle ──
onMounted(async () => {
  const stepParam = parseInt(route.query.step as string) || 1
  stepIdx.value = Math.max(0, Math.min(3, stepParam - 1))

  if (scenarioId.value && scenarioId.value !== 'new') {
    await loadScenario()
  }
  // 目录名非阻塞拉取(fire-and-forget, 不 await):到达晚于下方首次
  // checkSystemMismatch → 由 watch 重算;失败静默降级。
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 派生降级为整串(现状行为) */ })
  loadCatalogSystemByService()
    .then((m) => { systemByService.value = m })
    .catch(() => { /* 同上:同一拉取,失败时两者一起降级 */ })
  // Auto-compute system warning (PRD §5.1 §9): declared systems vs
  // services actually called by steps.
  if (scenario.value) checkSystemMismatch()
  if (rootEl.value) inserter.start(rootEl.value)
  void constantsStore.ensureEntries().catch(() => {})
  window.addEventListener('beforeunload', onBeforeUnload)
})

// 运行成功后跳详情页的延迟定时器 — 组件卸载时必须清除，否则用户在
// 800ms 内手动离开后仍会被强行拉去 /executions/{id}。
let runNavTimer: ReturnType<typeof setTimeout> | null = null
onUnmounted(() => {
  if (runNavTimer !== null) {
    clearTimeout(runNavTimer)
    runNavTimer = null
  }
  if (autoSaveTimer !== null) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
  window.removeEventListener('beforeunload', onBeforeUnload)
  inserter.stop()
})

/** Compare meta.system (declared) with the union of step systems
 *  (actual, 经 deriveSystem 权威派生 — endpoint_id 首段 / 目录
 *  service→system 映射,详见 service-alias.ts)。Mismatch is a yellow
 *  warning, not a hard error — the user can have a scenario that
 *  declares only `fin` but happens to call a `common.monitor` mock,
 *  for example. */
const systemMismatch = ref<string>('')
function checkSystemMismatch() {
  if (!scenario.value) return
  const declared = new Set(scenario.value.meta.system || [])
  const actual = new Set<string>()
  for (const s of scenario.value.steps as any[]) {
    const system = deriveSystem(s?.api, catalogNames.value, systemByService.value)
    if (system) actual.add(system)
  }
  const missing = [...actual].filter(s => !declared.has(s) && s !== 'common')
  const extra = [...declared].filter(s => !actual.has(s) && s !== 'common')
  const parts: string[] = []
  if (missing.length) parts.push(`steps 调用了未声明的系统: ${missing.join(', ')}`)
  if (extra.length) parts.push(`声明但未使用的系统: ${extra.join(', ')}`)
  systemMismatch.value = parts.join(' · ')
}

// 目录名/系统映射异步到达(fire-and-forget)晚于 onMounted 首次比对 →
// 到达后重算一次,权威派生才真正生效;loader 失败时本 watch 不触发,
// 维持点前缀启发式降级(现状行为)。
watch([catalogNames, systemByService], () => {
  if (scenario.value) checkSystemMismatch()
})

watch(() => route.query.step, (q) => {
  if (q) {
    const n = parseInt(q as string)
    if (!isNaN(n)) stepIdx.value = Math.max(0, Math.min(3, n - 1))
  }
})

async function loadScenario() {
  suppressDirty = true   // 加载赋值不算编辑;nextTick 后 watch 已冲刷,复位
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
    // runSchemes 与步骤无关,两条分支都原样带回 — 否则重载后方案丢失,
    // 下次存方案会整表覆盖掉已存方案。
    const persistedOrch = s.orchestration
    const persistedSchemes
      = (persistedOrch as OrchestrationWithSchemes | undefined)?.runSchemes
    const inSync = persistedOrch
      && persistedOrch.steps.length === definition.value.steps.length
    orchestration.value = inSync
      ? {
          steps: persistedOrch!.steps,
          resourceMeta: persistedOrch!.resourceMeta ?? {},
          runSchemes: persistedSchemes,
        }
      : {
          steps: definition.value.steps.map(() => ({ enabled: true, name: '' })),
          resourceMeta: {},
          runSchemes: persistedSchemes,
        }
    await loadDataSets()
    dirty.value = false
    editsDuringSave = false
    saveState.value = 'clean'
    await nextTick()    // 等 deep watch 冲完加载赋值,再解除抑制
    suppressDirty = false
  } catch (e) {
    suppressDirty = false
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

// ── navigation ──
function onStepClick(idx: number) {
  if (idx === stepIdx.value) return
  if (idx > stepIdx.value && dirty.value) {
    // Auto-save before advancing(manual=false:自动保存不弹 lint 提醒,防步步弹窗)
    saveDraft(false, false)
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

/** silent=true(防抖自动保存路径):失败不弹 toast,指示灯保持「未保存」,
 *  下次编辑重新调度 — 防后端掉线时每 2.5s 弹一次窗。
 *  返回是否成功 — openRunDialog/离开守卫据此决定「中止跑旧版/留在页面」。 */
async function saveDraft(advance = false, manual = true, silent = false): Promise<boolean> {
  if (!meta.value.name) {
    // scenarioId 不再前端必填校验:新建时自动生成,编辑时由路由回填并锁定。
    ElMessage.warning('请先在 ① 基本信息 中填写 name')
    onStepClick(0)
    return false
  }
  // 保存前 lint(C10/§4.3):不拦截保存,只提醒;自动保存(步进)不弹 toast
  const lintWarns = lintDraft(definition.value as Parameters<typeof lintDraft>[0])
  if (lintWarns.length && manual) {
    ElMessage.warning({ message: `草稿提醒:${lintWarns.join(';')}`, duration: 6000 })
  }
  // 新建场景:生成唯一 id 替换占位 'sc-new'。后端以此 id 作 DB 主键原样采用。
  // 编辑场景:definition.scenarioId 已由 loadScenario 从路由回填,update 时锁定不变。
  if (!scenario.value && definition.value.scenarioId === 'sc-new') {
    definition.value.scenarioId = genScenarioId(meta.value.name)
  }
  saving.value = true
  saveState.value = 'saving'
  editsDuringSave = false   // 本次保存的编辑快照基线
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
    // 新建首次保存:路由仍停留 /composer/new → 替换为真实 id(F5 安全、
    // URL 可分享;router-view 无 key 不重挂载,内存态原样保留)。
    if (route.params.scenarioId === 'new') {
      router.replace(composerUrl(saved.meta.scenarioId, stepIdx.value + 1))
    }
    // 新建场景后拉一次数据集列表(空列表,但保持状态一致)
    if (!dataSets.value.length) await loadDataSets()
    lastSavedAt.value = new Date()
    if (!editsDuringSave) {
      dirty.value = false
      saveState.value = 'clean'
    } else {
      saveState.value = 'dirty'   // 保存中又有编辑:不清 dirty,防抖续存
    }
    if (advance) {
      onStepClick(Math.min(STEPS.length - 1, stepIdx.value + 1))
    }
    return true
  } catch (e) {
    if (!silent) showError('保存', undefined, (e as Error).message)
    return false
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
  dataSetIds: string[],
  opts?: {
    stepTo?: number
    nRuns?: number
    parallel?: number
    serviceBindings?: Record<string, ServiceBinding>
  },
) {
  if (!scenario.value) {
    ElMessage.warning('请先保存草稿')
    return
  }
  runDispatching.value = true
  lastRunError.value = null
  try {
    // RunRequest 新配方(spec §6,D2 后无 env):serviceBindings 取代
    // auths/prefix/mergePolicy/injectCredentials;stepTo 0 合法(首步后停),
    // 只在 null/undefined 时缺省;nRuns/parallel 仅非默认上送。
    const body: RunRequest = {
      scenarioId: scenario.value.meta.scenarioId,
      dataSetIds,
      ...(opts?.stepTo != null ? { stepTo: opts.stepTo } : {}),
      ...(opts?.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
      ...(opts?.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
      ...(opts?.serviceBindings && Object.keys(opts.serviceBindings).length
        ? { serviceBindings: opts.serviceBindings } : {}),
    }
    const resp = await api.runScenario(body)
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

/** 存为方案:同名覆盖,整表 PUT(Task 10 窄端点);落库返回值回填共享
 *  草稿(RunDialog schemes prop 数据源)。失败弹错且不清空方案名草稿
 *  (409 重名等用户改名即可重试)。 */
async function onSaveScheme(scheme: RunScheme) {
  // 新建场景首次保存后路由仍停留 /scenarios/new — 路由参数不可作场景 id
  // (PUT /api/scenarios/new/run-schemes 会 404);用持久化 scenario 的真实 id。
  const id = scenario.value?.meta.scenarioId
  if (!id) {
    ElMessage.warning('场景尚未保存 — 请先保存场景,再存为方案')
    return
  }
  try {
    const next = [...runSchemes.value.filter(s => s.name !== scheme.name), scheme]
    const saved = await api.putRunSchemes(id, next)
    if (draftStore.draft) {
      ;(draftStore.draft.orchestration as OrchestrationWithSchemes).runSchemes = saved
    }
  } catch (e) {
    showError('存方案', undefined, (e as Error).message)
  }
}

/** 删除方案:确认后整表 PUT 去掉该项(窄端点整键替换语义,后端零改动);
 *  落库返回值回填共享草稿 → RunDialog schemes prop 收缩,其内部 watch
 *  检测选中项消失自动回「临时手填」。取消(含 ESC/遮罩)静默不动。 */
async function onDeleteScheme(name: string) {
  const id = scenario.value?.meta.scenarioId
  if (!id) {
    ElMessage.warning('场景尚未保存 — 无已存方案可删')
    return
  }
  const ok = await confirmAction(
    `删除方案 "${name}"?此操作不可撤销。`,
    '删除方案',
    { type: 'warning' },
  )
  if (!ok) return
  try {
    const saved = await api.putRunSchemes(id, runSchemes.value.filter(s => s.name !== name))
    if (draftStore.draft) {
      ;(draftStore.draft.orchestration as OrchestrationWithSchemes).runSchemes = saved
    }
    ElMessage.success(`已删除方案 ${name}`)
  } catch (e) {
    showError('删方案', undefined, (e as Error).message)
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
/* 过期场景:标题置灰 + 灰 pill(与收藏金 pill 同构、语义相反) */
.title.expired { color: #94a3b8; }
.expire-pill {
  display: inline-flex; align-items: center; gap: 4px;
  background: #f1f5f9; border: 1px solid #e2e8f0;
  color: #64748b; font-size: 11px; font-weight: 600;
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

/* ── 常量池 rail(步骤 0-2 右栏,body-split 布局;步骤 3 挂 Canvas col-info)── */
/* gap 16px 对齐 ①-③ 页 .c-page 卡片间隔(常量池 rail 与主内容同节奏) */
.body-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  height: 100%;
  min-height: 0;
}
.body-split.with-rail {
  grid-template-columns: minmax(0, 1fr) minmax(240px, 300px);
  /* 整体限宽 1280(c-page 上限)+16(间隔)+300(rail 上限)并居中:
     主单元恰为 1280 → c-page 撑满,rail 以精确 16px 贴主卡;
     否则 c-page 在更宽单元里居中,卡与 rail 之间夹 ~54px 死白 */
  max-width: 1596px;
  margin: 0 auto;
}
.body-main { min-width: 0; min-height: 0; }
.pool-rail {
  position: sticky;
  top: 8px;
  align-self: start;
  max-height: calc(100vh - 16px);
  overflow: auto;
}
@media (max-width: 1280px) {
  .body-split.with-rail { grid-template-columns: minmax(0, 1fr); }
  .pool-rail { position: static; max-height: none; }
}
</style>
