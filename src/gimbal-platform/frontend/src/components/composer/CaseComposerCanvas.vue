<!--
  CaseComposerCanvas.vue — ④ 步骤编辑 (现代化设计)
  3 栏布局 + 嵌入式接口目录 (子流程)
-->
<template>
  <div class="canvas-shell">
    <!-- 子流程:覆盖右两栏 -->
    <CaseComposerCatalog
      v-if="subView === 'catalog'"
      :next-step-idx="local.length + 1"
      :adding="adding"
      @add="onAddEndpoint"
      @back="subView = null"
    />

    <!-- 主页:3 栏 -->
    <div v-else class="three-col">
      <!-- ① 步骤流 -->
      <aside class="col col-steps">
        <div class="col-head">
          <div>
            <h3>步骤流</h3>
            <p class="muted">{{ local.length }} 个 step · 按顺序执行</p>
          </div>
          <button class="add-step" @click="subView = 'catalog'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            添加接口
          </button>
        </div>
        <div class="step-list">
          <!-- vuedraggable 上下拖拽重排(#5):纵向手柄拖,不做 DAG。
               item-key 用 WeakMap 侧挂的稳定 key(step 数据本体不能加字段 —
               草稿原样进 /convert);local 已被 draggable 重排,onStepReordered
               同步 orch.steps 并让选中项跟随 -->
          <draggable
            :list="local"
            :item-key="stepKey"
            handle=".step-handle"
            :animation="150"
            tag="div"
            class="step-drag-area"
            @end="onStepReordered"
          >
            <template #item="{ element: s, index: i }">
              <div class="step-row"
                   :class="{ active: i === activeStepIdx, disabled: !orch.steps[i]?.enabled }"
                   @click="activeStepIdx = i">
                <span class="step-handle" title="拖拽调整顺序">⠿</span>
                <div class="step-idx">{{ i + 1 }}</div>
                <div class="step-info">
                  <div class="step-name">{{ orch.steps[i]?.name || s.api?.path || 'step' }}</div>
                  <div class="step-meta">
                    <span v-if="s.api?.method" class="method-badge" :class="`m-${s.api.method.toLowerCase()}`">{{ s.api.method }}</span>
                    <span v-if="s.api?.service" class="svc-tag">{{ s.api.service }}</span>
                    <span v-if="s.api?.path" class="ep-path">{{ s.api.path }}</span>
                  </div>
                </div>
                <el-switch v-if="orch.steps[i]" v-model="orch.steps[i].enabled" size="small" @click.stop />
                <button class="step-del" @click.stop="removeStep(i)" title="删除">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
                </button>
              </div>
            </template>
          </draggable>
          <div v-if="!local.length" class="step-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
            <p>还没有 step</p>
            <button class="empty-cta" @click="subView = 'catalog'">+ 从接口目录选</button>
          </div>
        </div>
      </aside>

      <!-- ② 字段编辑器 -->
      <main class="col col-fields">
        <div v-if="currentStep" class="fields-shell">
          <div class="fields-head">
            <div class="fields-head-row">
              <div class="fields-title">
                <span class="title-num">{{ activeStepIdx + 1 }}</span>
                <input
                  class="title-input"
                  :value="currentOrch?.name ?? ''"
                  @input="(e: any) => { if (currentOrch) currentOrch.name = e.target.value }"
                  placeholder="step 名称"
                />
              </div>
              <span class="step-kind">{{ inferProtocol(currentStep) }}</span>
            </div>
            <!-- 接口事实只读缩略: method/service/path 来自接口目录 (plate), 是选定接口的属性,
                 不是用例配置项。要换接口 → 删 step 从目录重选。 -->
            <div class="api-summary">
              <span v-if="currentStep.api?.method" class="method-badge" :class="`m-${currentStep.api.method.toLowerCase()}`">{{ currentStep.api.method }}</span>
              <span v-if="currentStep.api?.service" class="svc-tag">{{ currentStep.api.service }}</span>
              <span v-if="currentStep.api?.path" class="ep-path">{{ currentStep.api.path }}</span>
            </div>
          </div>
          <el-form label-position="top" size="small" class="c-form">
            <!-- description 来自接口目录 (ep.name/desc), 同为选定接口的事实 — 只读展示 -->
            <el-form-item label="description">
              <p class="desc-readonly">{{ currentStep.description || '—' }}</p>
            </el-form-item>
            <!-- headers: KV 行编辑。value 支持 ${auth.<alias>.<field>} 模板 —
                 点 ⓘ 从认证列表选(草稿只存引用,token 明文永不进前端),
                 引用徽章提示悬空(alias 不在 /api/auths) -->
            <el-form-item label="headers (点 ⓘ 注入 ${auth.<alias>.<field>})">
              <div class="hdr-rows">
                <div v-for="(value, key) in currentStep.api.headers" :key="String(key)" class="hdr-row">
                  <el-input
                    :model-value="String(key)"
                    size="small"
                    placeholder="header name"
                    class="hdr-key"
                    @update:model-value="v => updateHeaderKey(currentStep, String(key), v)"
                  />
                  <el-input
                    :model-value="String(value)"
                    size="small"
                    placeholder="value (如 ${auth.qa1.token})"
                    class="hdr-val"
                    @update:model-value="v => updateHeaderValue(currentStep, String(key), v)"
                  />
                  <button type="button" class="c-kv-del hdr-pick" title="选择认证" @click="openAuthPicker(String(key), String(value))">ⓘ</button>
                  <button type="button" class="c-kv-del hdr-pick hdr-var" title="选择变量" @click="openVarPicker(String(key), String(value))">Ⓥ</button>
                  <button type="button" class="c-kv-del" title="删除" @click="removeHeader(currentStep, String(key))">×</button>
                  <div v-for="r in hdrRefs(String(value))" :key="r.raw" class="ref-chip" :class="hdrRefStatus(r)">
                    <span class="ref-chip-dot" />{{ r.raw }}
                    <span v-if="hdrRefStatus(r) === 'dangling'" class="ref-chip-note">
                      {{ r.domain === 'var' ? `变量 ${r.alias} 未注册` : `认证 ${r.alias} 不存在` }}
                    </span>
                  </div>
                </div>
                <button type="button" class="c-add" @click="addHeader(currentStep)">+ 新增 header</button>
              </div>
            </el-form-item>
            <!-- body: 优先由 request.fields_meta (IOFieldBinding) 驱动表单 -->
            <el-form-item v-if="fieldBindings(currentStep).length" label="请求体 (由 IOFieldBinding 驱动)">
              <div class="field-form-wrap">
                <FieldForm
                  :bindings="fieldBindings(currentStep)"
                  :body="currentStep.request.body || {}"
                  :var-entries="varRegistryEntries"
                  @update:body="v => currentStep.request.body = mergeBody(v, {})"
                />
                <p class="field-form-hint">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  来自 plate <code>/api/endpoint/.../full</code> 的 IOFieldBinding
                  · {{ fieldBindings(currentStep).length }} 个字段, plate 是结构权威源
                </p>
              </div>
            </el-form-item>
            <el-form-item v-else label="body (JSON)">
              <el-input
                :model-value="JSON.stringify(currentStep.request.body || {}, null, 2)"
                @update:model-value="v => currentStep.request.body = parseJson(v, {})"
                type="textarea"
                :rows="5"
                class="code-input"
              />
              <span class="hint">提示: 从接口目录添加 step 后, body 将由 IOFieldBinding 自动渲染</span>
            </el-form-item>
            <!-- 策略区: plate 策略语法 dim 驱动(kinds 懒加载);失败降级 extract 专用 UI -->
            <el-form-item v-if="strategyKinds.length" label="策略 (plate 语法 dim 驱动)">
              <div class="strategy-area">
                <StrategyForm
                  v-for="(s, j) in currentStep.strategy"
                  :key="`${activeStepIdx}-${j}`"
                  :strategy="s"
                  :detail="strategyDetail(s)"
                  :start-expanded="j === justAddedStrategyIdx"
                  :candidates="strategyCandidates(s)"
                  @remove="removeStrategy(currentStep, s)"
                />
                <el-dropdown trigger="click" @command="addStrategy(currentStep, $event as string)">
                  <!-- type="button": el-form 渲染原生 form,无 type 的按钮是 submit,
                       点击会触发整页表单提交丢掉 ?step= query -->
                  <button type="button" class="c-add add-strategy">
                    + 添加策略 ▾
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        v-for="k in strategyKinds"
                        :key="k.kind"
                        :command="k.kind"
                      >
                        {{ k.label }}<span class="strat-kind-tag">{{ k.kind }}</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </el-form-item>
            <el-form-item v-else label="extract (从响应提取变量 → strategy)">
              <div v-for="(ex, j) in extractStrategies(currentStep)" :key="j" class="extract-row c-kv-row">
                <el-input
                  :model-value="ex.target"
                  @update:model-value="v => ex.target = v"
                  placeholder="变量名 (target)"
                  size="small"
                />
                <span class="c-kv-sep">←</span>
                <el-input
                  :model-value="ex.expression"
                  @update:model-value="v => ex.expression = v"
                  placeholder="$.data.orderId"
                  size="small"
                  class="ex-path"
                />
                <button type="button" class="c-kv-del" @click="removeExtract(currentStep, ex)">×</button>
              </div>
              <button type="button" class="c-add add-extract" @click="addExtract(currentStep)">
                + 添加 extract
              </button>
            </el-form-item>
          </el-form>
        </div>
        <div v-else class="fields-empty">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <polyline points="14 2 14 8 20 8"/><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          </svg>
          <p>选一个 step 编辑</p>
          <p class="muted">或在左侧添加新 step</p>
        </div>
      </main>

      <!-- ③ 信息面板 -->
      <aside class="col col-info">
        <div class="col-head">
          <h3>step 信息</h3>
        </div>
        <div v-if="currentStep" class="info-body">
          <div class="info-block">
            <div class="info-k">HTTP</div>
            <div class="info-v">
              <span v-if="currentStep.api?.method" class="method-badge" :class="`m-${currentStep.api.method.toLowerCase()}`">{{ currentStep.api.method }}</span>
              <code>{{ currentStep.api?.path || '—' }}</code>
            </div>
          </div>
          <div class="info-block">
            <div class="info-k">service</div>
            <div class="info-v"><code>{{ currentStep.api?.service || '—' }}</code></div>
          </div>
          <div class="info-block">
            <div class="info-k">kind</div>
            <div class="info-v"><span class="badge">{{ inferProtocol(currentStep) }}</span></div>
          </div>
          <div class="info-block">
            <div class="info-k">enabled</div>
            <div class="info-v">
              <span :class="['status-pill', currentOrch?.enabled ? 'on' : 'off']">
                {{ currentOrch?.enabled ? '✓ 启用' : '✗ 禁用' }}
              </span>
            </div>
          </div>
          <div v-if="extractStrategies(currentStep).length" class="info-block">
            <div class="info-k">extracts</div>
            <div class="info-v">
              <div v-for="(ex, i) in extractStrategies(currentStep)" :key="i" class="extract-line">
                <code>{{ ex.target || '?' }}</code> ← <code>{{ ex.expression || '?' }}</code>
              </div>
            </div>
          </div>
          <!-- 响应字段(#2):200 响应契约字段清单,断言/extract 的目标参考 -->
          <div v-if="currentRespFields.length" class="info-block">
            <div class="info-k">响应字段 (200)</div>
            <div class="info-v">
              <div v-for="rf in currentRespFields" :key="rf.name" class="resp-field-line">
                <code>{{ rf.name }}</code>
                <span class="resp-field-kind">{{ rf.ui_kind }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="info-empty muted">无选中 step</div>
      </aside>
    </div>

    <!-- 认证选择器(headers value 注入 ${auth.<alias>.<field>}) -->
    <AuthSelectorModal
      v-if="authPickerOpen"
      v-model="authPickerOpen"
      :auths="auths"
      @select="onAuthPicked"
    />
    <!-- 变量选择器(headers value 注入 ${var.<name>},#3) -->
    <VarSelectorModal
      v-if="varPickerOpen"
      v-model="varPickerOpen"
      :entries="varRegistryEntries"
      @select="onVarPicked"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import draggable from 'vuedraggable'
import CaseComposerCatalog from './CaseComposerCatalog.vue'
import FieldForm from './FieldForm.vue'
import StrategyForm from './StrategyForm.vue'
import AuthSelectorModal from '../AuthSelectorModal.vue'
import VarSelectorModal from './VarSelectorModal.vue'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { deriveVarRegistry } from '@/utils/var-registry'
import { getFullEndpoint, listStrategyKinds, getStrategyKindFull } from '@/api/scenario-composer'
import { list as listAuths } from '@/api/auth_sessions'
import { parseTplRefs, refStatus } from '@/utils/tpl-refs'
import type { TplRef } from '@/utils/tpl-refs'
import type { AuthSession } from '@/api/auth_sessions'
import { deepDefaults } from '@/utils/jsonpath'
import type {
  StepView, ExtractView, IOFieldBinding, EndpointFullView,
  StrategyView, StrategyKindView, StrategyKindDetailView,
} from '@/types/plate'
import type { Orchestration, StepOrchestration } from '@/types/scenario-composer'

const props = defineProps<{
  steps: StepView[]
  orchestration: Orchestration
}>()
const emit = defineEmits<{
  'update:steps': [StepView[]]
  'update:orchestration': [Orchestration]
}>()

const local = reactive<StepView[]>([...(props.steps || [])])
const orch = reactive<Orchestration>(
  props.orchestration || { steps: [], resourceMeta: {} }
)
const activeStepIdx = ref(0)
const subView = ref<null | 'catalog'>(null)
const adding = ref(false)

const currentStep = computed(() => local[activeStepIdx.value])
const currentOrch = computed<StepOrchestration | undefined>(() => orch.steps[activeStepIdx.value])

/** plate Step 无顶层协议 kind;从 api 形状推断展示标签 (http/...) */
function inferProtocol(step: StepView | undefined): string {
  if (step?.api && step.api.method) return 'http'
  return 'step'
}

/** 从 request.fields_meta 派生 FieldForm 需要的 IOFieldBinding[] */
function fieldBindings(step: StepView | undefined): IOFieldBinding[] {
  const fm = step?.request?.fields_meta
  return fm ? Object.values(fm) : []
}

/** strategy 里提取 extract 变体 */
function extractStrategies(step: StepView | undefined): ExtractView[] {
  if (!step?.strategy) return []
  return step.strategy.filter((s): s is ExtractView => s.kind === 'extract')
}
function addExtract(step: StepView) {
  step.strategy.push({
    kind: 'extract', expression: '', target: '',
    scope: 'step', required: true,
  })
}
function removeExtract(step: StepView, ex: ExtractView) {
  const idx = step.strategy.indexOf(ex)
  if (idx >= 0) step.strategy.splice(idx, 1)
}

// ── 策略区(plate 语法 dim 驱动) ─────────────────────────────────
// kinds 加载失败 → strategyKinds 留空 → 模板降级到上方 extract 专用 UI。

const strategyKinds = ref<StrategyKindView[]>([])
/** detail 按 kind 懒加载 + 会话级缓存(语法全局不变)。ref 包对象 → 命中后模板自动重渲染 */
const strategyDetailCache = ref<Record<string, StrategyKindDetailView>>({})
let strategyDetailPrefetch = false
/** 刚通过"添加策略"下拉新建的实例下标(渲染为展开引导填写);-1 = 无 */
const justAddedStrategyIdx = ref(-1)
// 切 step 时清"刚添加"标记(下标在新 step 语境无意义,防误展开)
watch(activeStepIdx, () => { justAddedStrategyIdx.value = -1 })

async function loadStrategyKinds() {
  try {
    strategyKinds.value = await listStrategyKinds()
  } catch {
    // 降级:模板 v-if 落到 extract 专用 UI,不阻塞编排
  }
}
async function ensureStrategyDetail(kind: string): Promise<StrategyKindDetailView | undefined> {
  if (strategyDetailCache.value[kind]) return strategyDetailCache.value[kind]
  try {
    const d = await getStrategyKindFull(kind)
    strategyDetailCache.value = { ...strategyDetailCache.value, [kind]: d }
    return d
  } catch {
    return undefined
  }
}
/** 渲染期同步取 detail(缓存未命中返回 placeholder 并触发懒加载,完成后响应式刷新) */
function strategyDetail(s: StrategyView): StrategyKindDetailView {
  const hit = strategyDetailCache.value[s.kind]
  if (hit) return hit
  void ensureStrategyDetail(s.kind)
  return { kind: s.kind, label: s.kind, phase: 'verifying', fields: [], base_fields: [] }
}

async function addStrategy(step: StepView, kind: string) {
  const d = await ensureStrategyDetail(kind)
  if (!d) {
    ElMessage.error(`拉取策略 ${kind} 结构失败, 请重试`)
    return
  }
  // 骨架 = {kind 判别字段 + 按 detail.fields 的 default 展开}
  const inst: Record<string, unknown> = { kind }
  for (const f of d.fields) {
    if (f.default !== null && f.default !== undefined) inst[f.name] = f.default
  }
  step.strategy.push(inst as unknown as StrategyView)
  // 新实例引导填写 → 展开(仅最新的;预填/加载的保持折叠降噪)
  justAddedStrategyIdx.value = step.strategy.length - 1
}

function removeStrategy(step: StepView, s: StrategyView) {
  const idx = step.strategy.indexOf(s)
  if (idx >= 0) step.strategy.splice(idx, 1)
}

// ── headers KV 行 + 认证引用(模式照搬 EditableStepCard 成熟实现) ────
// headers 本就是 Record<string, string>;KV 行只是编辑形态,草稿/导出形状不变。

const auths = ref<AuthSession[]>([])
const authPickerOpen = ref(false)
const authPickerKey = ref<string | null>(null)
const authPickerVal = ref<string | null>(null)
const authPickerStep = ref<StepView | null>(null)

function addHeader(step: StepView) {
  const h = (step.api.headers ||= {})
  let k = 'X-Header'
  while (k in h) k += '1'
  h[k] = ''
}
function removeHeader(step: StepView, key: string) {
  delete step.api.headers?.[key]
}
function updateHeaderKey(step: StepView, oldKey: string, newKey: string) {
  if (oldKey === newKey || !step.api.headers) return
  const v = step.api.headers[oldKey]
  delete step.api.headers[oldKey]
  step.api.headers[newKey] = v ?? ''
}
function updateHeaderValue(step: StepView, key: string, value: string) {
  if (step.api.headers) step.api.headers[key] = value
}

/**
 * 打开选择器时记 key + 当时 value。key 在弹窗期间可能被改名
 * (rename 是 delete+set,弹窗里拿不到新 key),所以落注入时:
 * key 仍在 → 注入该 key;key 没了 → 找 value 等于当时 value 的唯一行。
 */
function openAuthPicker(key: string, value: string) {
  authPickerStep.value = currentStep.value ?? null
  if (!authPickerStep.value) return
  authPickerKey.value = key
  authPickerVal.value = value
  authPickerOpen.value = true
}
function onAuthPicked(tpl: string) {
  const step = authPickerStep.value
  const key = authPickerKey.value
  const val = authPickerVal.value
  const headers = step?.api?.headers
  if (step && headers) {
    if (key && key in headers) {
      headers[key] = tpl
    } else {
      // key 被改:按当时 value 定位(唯一匹配才注入,防误写)
      const hits = Object.entries(headers).filter(([, v]) => v === val)
      if (hits.length === 1) headers[hits[0][0]] = tpl
    }
  }
  authPickerKey.value = null
  authPickerVal.value = null
  authPickerStep.value = null
}

/** header value 的引用徽章数据(auth + var 两域;var 为 #3 增) */
function hdrRefs(value: string): TplRef[] {
  return parseTplRefs(value).filter((r) => r.domain === 'auth' || r.domain === 'var')
}

/** 徽章悬空判定:auth 对 /api/auths 列表,var 对注册表(数据集列运行期
 *  注入,不在编辑期注册表 — 悬空提示核对拼写,不硬阻断) */
function hdrRefStatus(ref: TplRef): 'ok' | 'dangling' {
  if (ref.domain === 'var') {
    return varRegistryEntries.value.some((e) => e.name === ref.alias) ? 'ok' : 'dangling'
  }
  return refStatus(ref, authAliases.value)
}

// ── 变量选择器(#3):Ⓥ 从注册表选 ${var.<name>},不手打 ─────────────
// 注册表 = 共享 vars(config) + 全部 step 的 extract;config 来自共享
// draft store(CaseComposer watch 同步,含本页未编辑的最新值)。
const draftStore = useScenarioDraftStore()
const varPickerOpen = ref(false)
const varPickerKey = ref<string | null>(null)
const varPickerVal = ref<string | null>(null)

const varRegistryEntries = computed(() =>
  deriveVarRegistry(local, draftStore.draft?.definition?.config?.vars).entries)

/** 同 openAuthPicker:key 在弹窗期间可能被改,落注入时按 key 或唯一 value 定位 */
function openVarPicker(key: string, value: string) {
  if (!currentStep.value) return
  varPickerKey.value = key
  varPickerVal.value = value
  varPickerOpen.value = true
}
function onVarPicked(tpl: string) {
  const key = varPickerKey.value
  const val = varPickerVal.value
  const headers = currentStep.value?.api?.headers
  if (headers) {
    if (key && key in headers) {
      headers[key] = tpl
    } else {
      const hits = Object.entries(headers).filter(([, v]) => v === val)
      if (hits.length === 1) headers[hits[0][0]] = tpl
    }
  }
  varPickerKey.value = null
  varPickerVal.value = null
}

/** 模板里 refStatus 的第二参:已知 alias 列表 */
const authAliases = computed(() => auths.value.map((a) => a.alias))

onMounted(() => {
  void loadStrategyKinds()
  // 首次进入策略区前预热三个 kind 的 detail(共 3 个请求,一次性)
  if (!strategyDetailPrefetch) {
    strategyDetailPrefetch = true
    void loadStrategyKinds().then(() => {
      for (const k of strategyKinds.value) void ensureStrategyDetail(k.kind)
    })
  }
  // 认证列表:ⓘ 选择器 + 悬空徽章判定共用。失败静默(ⓘ 打开时列表为空,可重进)
  listAuths().then((a) => { auths.value = a }).catch(() => {})
})

watch(() => props.steps, (v) => {
  // 父组件回写的是 emit 出去的同一份内容(引用不同)。deep-equal 时跳过,
  // 避免与下方 emit watch 互触形成递归更新环(Maximum recursive updates)。
  if (sameSteps(v, local)) return
  local.splice(0, local.length, ...(v || []))
}, { deep: true })

watch(() => props.orchestration, (v) => {
  if (v && v.steps.length === orch.steps.length && sameSteps(v.steps, orch.steps)
    && JSON.stringify(v.resourceMeta) === JSON.stringify(orch.resourceMeta)) return
  orch.steps.splice(0, orch.steps.length, ...(v?.steps || []))
  orch.resourceMeta = v?.resourceMeta || {}
}, { deep: true })

watch([local, orch], () => {
  emit('update:steps', [...local])
  emit('update:orchestration', { steps: [...orch.steps], resourceMeta: { ...orch.resourceMeta } })
}, { deep: true })

/** 两份 step 数组内容是否一致(浅比较 + 关键字段;step 对象在同步链上会被克隆,不能比引用) */
function sameSteps(a: StepView[] | undefined, b: StepView[]): boolean {
  if (!a) return false
  if (a.length !== b.length) return false
  return a.every((s, i) => {
    const t = b[i]
    return s === t || JSON.stringify(s) === JSON.stringify(t)
  })
}

/**
 * 预填的 code 断言 target 探测顺序 —— 仅当 assertable_fields 命中其一
 * 才追加业务码断言,避免给没有 code 语义的接口塞无效断言。
 */
const CODE_TARGET_CANDIDATES = ['$.code', '$.data.code'] as const

/**
 * endpoint_id → 200 响应 assertable_fields(#2 起被消费:断言 target /
 * extract expression 的下拉候选)。step 经 api.view_hints.endpoint_id
 * 持久化接口身份,缓存 miss 时懒拉 /full 回填 — 刷新后候选不丢。
 */
const assertableByEndpoint = new Map<string, string[]>()
/** 正在懒拉的 endpoint_id(防重复并发) */
const assertableFetching = new Set<string>()

/** 当前 step 的断言候选列表;endpoint 未知/拉取中 → 空(不渲染 ▾) */
const currentAssertable = computed<string[]>(() => {
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return []
  ensureAssertable(eid)
  return assertableByEndpoint.get(eid) ?? []
})

/** 缓存 miss 时懒拉 /full 回填 assertable(fail-soft:拉不到就无候选) */
function ensureAssertable(endpointId: string) {
  if (assertableByEndpoint.has(endpointId) || assertableFetching.has(endpointId)) return
  assertableFetching.add(endpointId)
  getFullEndpoint(endpointId)
    .then((full) => {
      const a = full.responses?.['200']?.assertable_fields
      if (a?.length) assertableByEndpoint.set(endpointId, a)
    })
    .catch(() => {})
    .finally(() => assertableFetching.delete(endpointId))
}

// ── 响应字段渲染(#2):step 信息面板展示 200 响应字段清单 ───────────
// 与 assertable 同源(/full),共用懒拉;名字+类型一行一档,断言/extract
// 的目标从面板直接抄 JSONPath。空 200 契约 → 块不渲染。
interface RespField { name: string; ui_kind: string }
const respFieldsByEndpoint = new Map<string, RespField[]>()
/** 响应式触发器:Map 变更不会触发 computed,用版本号 bump */
const respFieldsVersion = ref(0)
const currentRespFields = computed<RespField[]>(() => {
  void respFieldsVersion.value
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return []
  ensureRespFields(eid)
  return respFieldsByEndpoint.get(eid) ?? []
})
function ensureRespFields(endpointId: string) {
  if (respFieldsByEndpoint.has(endpointId) || assertableFetching.has(endpointId)) return
  assertableFetching.add(endpointId)
  getFullEndpoint(endpointId)
    .then((full) => {
      const r200 = full.responses?.['200']
      const fields = (r200?.fields || []).map((f) => ({ name: f.name, ui_kind: f.ui_kind }))
      respFieldsByEndpoint.set(endpointId, fields)
      respFieldsVersion.value++
    })
    .catch(() => {})
    .finally(() => assertableFetching.delete(endpointId))
}

/** 策略表单候选映射(#2):kind 定字段名 — assertion 用 target,extract 用 expression */
function strategyCandidates(s: StrategyView): Record<string, string[]> {
  const fields = s.kind === 'assertion' ? ['target'] : s.kind === 'extract' ? ['expression'] : []
  if (!fields.length || !currentAssertable.value.length) return {}
  return Object.fromEntries(fields.map((f) => [f, currentAssertable.value]))
}

/** 由 endpoint 契约(/full 原料)构造初始策略,替代硬编码 $.status eq 200 */
function buildInitialStrategies(full: EndpointFullView | undefined): StrategyView[] {
  // 保底第一条: HTTP 层状态断言(与旧行为一致)
  const strategies: StrategyView[] = [
    { kind: 'assertion', target: '$.status', operator: 'eq', expected: 200, message: '', soft: false },
  ]
  if (!full) return strategies
  const r200 = full.responses?.['200']
  const assertable = r200?.assertable_fields || []
  const successCriteria = full.metadata?.success_criteria || ''
  // 契约驱动追加: success_criteria 非空 且 响应确有 code 断言位
  if (successCriteria) {
    const codeTarget = CODE_TARGET_CANDIDATES.find((c) => assertable.includes(c))
    if (codeTarget) {
      strategies.push({
        kind: 'assertion', target: codeTarget, operator: 'eq', expected: 0,
        message: successCriteria, soft: false,
      })
    }
  }
  return strategies
}

async function onAddEndpoint(ep: any) {
  if (!ep) return
  adding.value = true
  try {
    // 拉 plate /api/endpoint/{id}/full 取 IOFieldBinding + 策略原料
    // (assertable_fields / success_criteria);失败仍以原始信息加入
    // (用户投诉过的"裸 JSON"兜底)。
    let fieldsMeta: Record<string, IOFieldBinding> | undefined
    let full: EndpointFullView | undefined
    try {
      full = await getFullEndpoint(ep.id)
      fieldsMeta = Object.fromEntries(
        (full.request?.fields || []).map((f: IOFieldBinding) => [f.name, f])
      )
    } catch (e) {
      ElMessage.warning('拉取完整接口定义失败, 仍以原始信息加入: ' + (e as Error).message)
    }
    // assertable_fields 存 step 级 view_hints(本期只存不消费,供后续
    // target/expression 下拉候选使用)
    const assertable = full?.responses?.['200']?.assertable_fields
    const strategy = buildInitialStrategies(full)
    const initialBody = fieldsMeta ? deepDefaults(Object.values(fieldsMeta)) : {}
    const newStep: StepView = {
      kind: 'step',
      description: ep.name,
      api: {
        kind: 'api',
        service: ep.service,
        method: ep.api?.method || 'GET',
        path: ep.api?.path || '',
        headers: ep.api?.headers || {},
        // 接口身份持久化(#2):断言/extract 候选懒拉 /full 的 key;
        // view_hints 是平台视图扩展,GimbalScenarioExporter 导出时剥离
        view_hints: { endpoint_id: ep.id },
      },
      request: {
        kind: 'request',
        body: initialBody,
        ...(fieldsMeta ? { fields_meta: fieldsMeta } : {}),
      },
      strategy,
    }
    // assertable_fields 存 Canvas 本地 Map(引用数据不进 draft,容器原则;
    // StepView 顶层无 view_hints 声明,塞 step 会泄漏进 /convert 导出)
    if (assertable?.length) assertableByEndpoint.set(ep.id, assertable)
    local.push(newStep)
    // 同步 orchestration (保持 index 对齐)
    orch.steps.push({ enabled: true, name: ep.name })
    activeStepIdx.value = local.length - 1
    subView.value = null  // 直接落盘, 关闭目录回到画布
    ElMessage.success(`已加入 step: ${ep.name} (${fieldsMeta ? Object.keys(fieldsMeta).length : 0} 字段)`)
  } finally {
    adding.value = false
  }
}

function mergeBody(formValues: any, _hiddenFields: any): any {
  // Form values come from IOFieldBinding-driven controls; plate 已是结构权威,
  // 平台不再派生 Type C 隐藏字段, 直接以表单值为准。
  return { ...(_hiddenFields || {}), ...(formValues || {}) }
}

function removeStep(i: number) {
  local.splice(i, 1)
  orch.steps.splice(i, 1)  // 保持与 local 同序同长
  if (activeStepIdx.value >= local.length) activeStepIdx.value = Math.max(0, local.length - 1)
}

// ── 步骤拖拽重排(#5) ─────────────────────────────────────────────
// item-key 不能写进 step 数据本体(草稿原样进 /convert,不能加字段),
// 用 WeakMap 给对象侧挂稳定 key — key 生命周期与对象引用一致,天然免清理。
const stepKeys = new WeakMap<object, number>()
let stepKeySeq = 0
function stepKey(s: object): number {
  let k = stepKeys.get(s)
  if (k === undefined) {
    k = ++stepKeySeq
    stepKeys.set(s, k)
  }
  return k
}

/**
 * draggable @end:同步 orch.steps(same splice)并让 activeStepIdx 跟随
 * 被拖动的 step。选中项身份从 orch.steps 取 — local 此刻是否已被
 * vuedraggable 重排取决于 sortable 内部事件序,而 orch 只有本函数一处写,
 * 时序自定;且 orch 与重排前的 local 下标对齐,activeStepIdx 正是旧下标。
 */
function onStepReordered(evt: { oldIndex?: number; newIndex?: number }) {
  const { oldIndex, newIndex } = evt
  if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
  const selected = orch.steps[activeStepIdx.value]
  const moved = orch.steps.splice(oldIndex, 1)[0]
  orch.steps.splice(newIndex, 0, moved)
  if (selected) {
    const next = orch.steps.indexOf(selected)
    if (next >= 0) activeStepIdx.value = next
  }
}

function parseJson(s: string, fallback: unknown) {
  try { return JSON.parse(s) } catch { return fallback }
}
</script>

<style scoped>
/* 表单控件统一外观走 composer.css (.c-form) */
.canvas-shell { width: 100%; }

/* 三栏自适应: 宽屏 3 栏, 中屏两栏 (信息面板下移), 窄屏单列 */
.three-col {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(240px, 300px);
  gap: 12px;
  min-height: 600px;
  align-items: start;
}
@media (max-width: 1280px) {
  .three-col { grid-template-columns: minmax(240px, 300px) minmax(0, 1fr); }
  .col-info { grid-column: 1 / -1; }
}
@media (max-width: 860px) {
  .three-col { grid-template-columns: minmax(0, 1fr); }
}

.col {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 16px 18px;
  display: flex; flex-direction: column;
}

.col-head {
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid var(--c-divider);
  display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
}
.col-head h3 { margin: 0 0 2px; font-size: 14px; font-weight: 600; }
.col-head .muted { margin: 0; font-size: 11px; color: var(--c-text-tertiary); }

.add-step {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--c-accent);
  color: #fff; border: none; border-radius: 6px;
  padding: 6px 12px; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: background 0.15s;
  white-space: nowrap;
}
.add-step:hover { background: var(--accent-hover, #3730a3); }

/* step list */
.step-list { display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto; }
/* draggable 容器接管行布局与行间距(行现在挂在这一层,不再直接挂 .step-list) */
.step-drag-area { display: flex; flex-direction: column; gap: 6px; }
/* 拖拽手柄:竖排点阵,grab 光标;仅手柄可发起拖拽(handle 限定),
   行其余区域仍是点击选中 */
.step-handle {
  flex-shrink: 0;
  width: 14px;
  color: var(--c-border-strong, #cbd5e1);
  cursor: grab;
  font-size: 13px;
  line-height: 1;
  user-select: none;
  text-align: center;
}
.step-handle:active { cursor: grabbing; }
.step-row:hover .step-handle { color: var(--c-text-tertiary); }
.step-row.sortable-ghost { opacity: 0.4; border-style: dashed; }
.step-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  background: var(--c-bg-secondary);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.step-row:hover { background: var(--c-surface); border-color: var(--c-border); }
.step-row.active {
  background: var(--c-accent-soft);
  border-color: var(--c-accent-soft-border);
}
.step-row.disabled { opacity: 0.55; }
.step-idx {
  width: 26px; height: 26px; border-radius: 50%;
  background: var(--c-surface); color: var(--c-text-secondary);
  font-size: 12px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--c-border);
  flex-shrink: 0;
}
.step-row.active .step-idx {
  background: var(--c-accent);
  color: #fff; border-color: transparent;
}
.step-info { flex: 1; min-width: 0; }
.step-name { font-size: 13px; font-weight: 600; color: var(--c-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.step-row.active .step-name { color: var(--c-accent); }
.step-meta { display: flex; gap: 4px; align-items: center; margin-top: 3px; font-size: 10px; color: var(--c-text-secondary); flex-wrap: wrap; }
.method-badge {
  font-family: var(--font-mono); font-weight: 700;
  padding: 1px 5px; border-radius: 3px;
  background: #f1f5f9; color: #475569; font-size: 9px;
}
.method-badge.m-get { background: #dbeafe; color: #1e40af; }
.method-badge.m-post { background: #d1fae5; color: #065f46; }
.method-badge.m-put { background: #fef3c7; color: #92400e; }
.method-badge.m-delete { background: #fee2e2; color: #991b1b; }
.method-badge.m-patch { background: #f3e8ff; color: #6b21a8; }
.svc-tag { background: #f1f5f9; color: #475569; padding: 1px 5px; border-radius: 3px; font-size: 9px; }
.ep-path { font-family: var(--font-mono); font-size: 10px; color: var(--c-text-tertiary); }
.step-row :deep(.el-switch) { transform: scale(0.8); }
.step-del {
  width: 24px; height: 24px; background: transparent; border: none;
  border-radius: 4px; color: var(--c-text-tertiary); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s; opacity: 0;
}
.step-row:hover .step-del { opacity: 1; }
.step-del:hover { background: #fef2f2; color: #ef4444; }

.step-empty {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px 16px; text-align: center; color: var(--c-text-tertiary);
}
.step-empty svg { color: var(--c-border-strong); }
.step-empty p { margin: 0; font-size: 13px; }
.empty-cta {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--c-accent); color: #fff; border: none; border-radius: 6px;
  padding: 8px 16px; font-size: 12px; font-weight: 600;
  cursor: pointer;
}
.empty-cta:hover { background: var(--accent-hover, #3730a3); }

/* fields editor */
.fields-shell { flex: 1; }
.fields-head {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--c-divider);
  margin-bottom: 16px;
}
.fields-head-row { display: flex; align-items: center; gap: 10px; }
.api-summary {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 8px; padding: 6px 10px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 6px;
}
.api-summary .ep-path { font-size: 11px; }
.desc-readonly {
  margin: 0;
  font-size: 12.5px;
  color: var(--c-text-secondary);
  line-height: 1.7;
}
.fields-title { display: flex; align-items: center; gap: 8px; flex: 1; }
.title-num {
  width: 28px; height: 28px; border-radius: 6px;
  background: var(--c-accent);
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.title-input {
  border: none; background: transparent;
  font-size: 18px; font-weight: 700; color: var(--c-text);
  flex: 1; outline: none;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  min-width: 0;
}
.title-input:focus { border-bottom-color: var(--c-accent); }
.step-kind {
  padding: 4px 10px; border-radius: 999px;
  background: #f3e8ff; color: #6b21a8;
  font-size: 11px; font-weight: 600;
}

.input-tag {
  display: inline-block; background: var(--c-accent);
  color: #fff; font-size: 10px; font-weight: 700;
  padding: 2px 6px; border-radius: 4px; margin-right: 4px;
}

.code-input :deep(.el-textarea__inner) {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1;
  border-radius: 6px; box-shadow: 0 0 0 1px #313244;
  padding: 10px 12px;
}
.code-input :deep(.el-textarea__inner::placeholder) { color: #6c7086; }

/* 附带字段 (Type C) 折叠区 — 平面化: 去渐变,保留琥珀色语义 */
.extra-fields {
  margin-top: 10px;
  border: 1px solid #fde68a; border-radius: 8px;
  background: #fffbeb;
}
.extra-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer;
  font-size: 12px; font-weight: 600; color: #92400e;
}
.extra-head svg { transition: transform 0.15s; }
.extra-head svg.open { transform: rotate(180deg); }
.extra-hint { margin-left: auto; font-size: 11px; font-weight: 400; color: #b45309; }
.extra-body { padding: 0 12px 10px; display: flex; flex-direction: column; gap: 4px; }
.extra-row {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; background: #fff; border-radius: 4px;
  font-size: 11px;
}
.extra-key { color: #4338ca; font-weight: 600; }
.extra-arrow { color: var(--c-text-tertiary); }
.extra-val { color: #15803d; }
.extra-tag {
  margin-left: auto; padding: 1px 6px; border-radius: 3px;
  font-size: 9px; font-weight: 700; text-transform: uppercase;
}
.t-c { background: #fde68a; color: #92400e; }

/* 字段栅格自适应 */
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0 14px; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0 14px; }

/* extract 行 — 走共享 kv 栅格 */
.extract-row { margin-bottom: 4px; }
.ex-path :deep(.el-input__wrapper) { font-family: var(--font-mono); }
.add-extract { width: 100%; }

/* 策略区(语法 dim 驱动) */
.strategy-area { width: 100%; }
.add-strategy { width: 100%; }
.strat-kind-tag {
  margin-left: 8px;
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8;
}

/* headers KV 行 — 独立 flex 布局(元素数可变: key/val/ⓘ/×/chips,
   不能用 .c-kv-row 的固定 4 列 grid,多出的子元素会溢出格子叠层) */
.hdr-rows { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.hdr-row {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 6px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
}
.hdr-key { width: 170px; flex-shrink: 0; }
.hdr-val { flex: 1; min-width: 200px; }
.hdr-pick { color: #4f46e5; flex-shrink: 0; }
.hdr-pick:hover { background: #e0e7ff; color: #3730a3; }
/* Ⓥ 变量选择器:绿系,与 ⓘ(认证,靛蓝)区分 */
.hdr-var { color: #047857; }
.hdr-var:hover { background: #d1fae5; color: #065f46; }
.hdr-row .c-kv-del { flex-shrink: 0; }
.ref-chip { margin-top: 2px; }

/* ${auth.*} 引用徽章:绿=可解析 / 红=悬空 */
.ref-chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: 10px;
  padding: 1px 7px; border-radius: 3px;
  background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0;
}
.ref-chip.dangling { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
.ref-chip-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.ref-chip-note { font-family: inherit; opacity: 0.85; }

/* fields empty */
.fields-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: var(--c-text-tertiary);
}
.fields-empty svg { color: var(--c-border-strong); }
.fields-empty p { margin: 0; font-size: 13px; }
.fields-empty .muted { font-size: 12px; }

/* info panel */
.info-body { display: flex; flex-direction: column; gap: 12px; }
.info-block {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 10px 12px; background: var(--c-bg-secondary); border-radius: 8px;
}
.info-k {
  width: 50px; flex-shrink: 0;
  font-size: 11px; color: var(--c-text-tertiary); text-transform: uppercase; font-weight: 600;
}
.info-v { flex: 1; font-size: 12px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.info-v code { font-family: var(--font-mono); font-size: 11px; color: var(--c-accent); background: var(--c-surface); padding: 1px 4px; border-radius: 3px; word-break: break-all; }
.badge { background: #f3e8ff; color: #6b21a8; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill.on { background: #d1fae5; color: #065f46; }
.status-pill.off { background: #fee2e2; color: #991b1b; }
.extract-line { font-size: 10px; width: 100%; }
/* 响应字段行(#2):字段名 + ui_kind 小标,断言/extract 目标参考 */
.resp-field-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; width: 100%;
}
.resp-field-kind {
  font-family: var(--font-mono); font-size: 9px;
  color: #94a3b8; background: #f1f5f9;
  padding: 0 4px; border-radius: 3px;
}
.info-empty { padding: 40px 0; text-align: center; font-size: 12px; }
</style>
