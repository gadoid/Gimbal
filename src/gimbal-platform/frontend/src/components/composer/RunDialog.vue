<!--
  RunDialog.vue — 运行对话框(spec §4 重构:方案栏 + 主面板 + 折叠区)
  方案栏:临时手填 / 上次运行 / 已存方案(orchestration sidecar,plate 零感知);
  主面板:环境 tiles / 数据集多选(空 = 基线)/ 基础设置(stepTo · nRuns×parallel);
  折叠区:用户与服务绑定(service → authAlias/url;凭证按 alias 解密注入,
  本弹框只选 alias 不拉明文)+ 插件/日志订阅预埋(待 gimbal 侧支持)。
  旧 prefix / mergePolicy / preset / auths 多选 chips 语义已退役(spec §10)。
-->
<template>
  <Teleport v-if="visible" to="body">
    <div class="run-overlay" @click.self="$emit('close')">
      <div class="run-dialog" role="dialog" aria-modal="true">
        <header class="run-header">
          <div>
            <h2>运行编排</h2>
            <p class="muted">从 <code>{{ scenario?.meta?.scenarioId || '—' }}</code> 触发执行</p>
          </div>
          <button class="icon-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div class="run-body">
          <!-- 方案栏:临时手填 / 上次运行 / 已存方案;右侧命名另存 -->
          <div class="rd-scheme-bar">
            <select class="rd-scheme-select" v-model="selectedScheme">
              <option v-for="o in schemeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
            <input class="rd-scheme-name" v-model="schemeNameDraft" placeholder="方案名" maxlength="64" />
            <button class="ghost-btn" data-testid="save-scheme" type="button" @click="onSaveScheme">存为方案</button>
          </div>

          <!-- 环境选择 -->
          <section class="run-section">
            <label class="run-label">执行环境</label>
            <div class="env-grid">
              <button
                v-for="env in envs"
                :key="env.envId"
                class="env-tile"
                :class="{ active: selectedEnv === env.envId }"
                @click="selectedEnv = env.envId"
                type="button"
              >
                <div class="env-tile-head">
                  <span class="env-radio"></span>
                  <span class="env-name">{{ env.name }}</span>
                </div>
                <div class="env-url">{{ env.baseUrl }}</div>
              </button>
              <div v-if="envs.length === 0" class="muted small">暂无可用环境 — 请在服务端 data/envs.yaml 中配置后重试</div>
            </div>
          </section>

          <!-- 数据集选择 -->
          <section class="run-section">
            <div class="label-row">
              <label class="run-label">数据集 <span class="muted small">(可多选, 不选则该数据集的行不参与运行)</span></label>
              <button class="link-btn" @click="goCreateDataSet" type="button">+ 新建数据集</button>
            </div>
            <div class="ds-grid ds-grid-baseline">
              <label class="ds-tile baseline" :class="{ active: useBaseline || selectedDatasets.length === 0 }">
                <input
                  type="checkbox"
                  data-test="baseline"
                  :checked="useBaseline"
                  @change="toggleBaseline"
                />
                <div class="ds-info">
                  <div class="ds-name">默认配置(基线)</div>
                  <div class="ds-meta"><span class="ds-rows">1 次运行</span></div>
                  <div class="ds-preview"><code>不选数据集 — 步骤直填值 + 共享变量默认值</code></div>
                </div>
              </label>
            </div>
            <div v-if="dataSets.length === 0" class="empty-data">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/>
              </svg>
              <p>暂无数据集 — 创建一个数据集来参数化运行</p>
              <button class="primary-btn" @click="goCreateDataSet">+ 新建第一个数据集</button>
            </div>
            <div v-else class="ds-grid">
              <label
                v-for="ds in dataSets"
                :key="ds.datasetId"
                class="ds-tile"
                :class="{ active: selectedDatasets.includes(ds.datasetId) }"
              >
                <input
                  type="checkbox"
                  :value="ds.datasetId"
                  v-model="selectedDatasets"
                />
                <div class="ds-info">
                  <div class="ds-name">{{ ds.name }}</div>
                  <div class="ds-meta">
                    <span class="ds-rows">{{ ds.rowCount }} 行</span>
                  </div>
                  <div v-if="ds.preview.length" class="ds-preview">
                    <code>{{ JSON.stringify(ds.preview[0]) }}</code>
                  </div>
                </div>
              </label>
            </div>
          </section>

          <!-- 基础设置(stepTo / nRuns × parallel;旧 凭证策略·前缀·预设 已退役) -->
          <section class="run-section">
            <label class="run-label">基础设置 <span class="muted small">(步进调试 / 批量执行)</span></label>
            <div class="adv-grid">
              <div class="adv-field">
                <span class="adv-name">停止于步骤</span>
                <select v-model.number="stepTo" class="adv-select" :disabled="stepCount === 0">
                  <option :value="null" :disabled="stepCount === 0">运行全部步骤</option>
                  <option v-for="i in stepCount" :key="i" :value="i - 1">
                    第 {{ i }} 步后停止{{ stepName(i - 1) }}
                  </option>
                </select>
              </div>
              <div class="adv-field">
                <span class="adv-name">执行次数 / 并发度</span>
                <div class="num-row">
                  <input type="number" v-model.number="nRuns" class="adv-input" min="1" max="1000" />
                  <span class="num-sep">次 ×</span>
                  <input type="number" v-model.number="parallel" class="adv-input" min="1" max="200" />
                  <span class="num-sep">并发</span>
                </div>
              </div>
            </div>
            <div v-if="stepCount === 0" class="muted small">场景暂无步骤,停止于步骤不可用</div>
          </section>

          <!-- 折叠区:用户与服务绑定(默认折叠) -->
          <section class="rd-fold" :class="{ 'is-open': foldBindings }">
            <button class="rd-fold-head" type="button" @click="foldBindings = !foldBindings">
              用户与服务
              <span class="rd-fold-summary">{{ bindingsSummary }}</span>
            </button>
            <div v-show="foldBindings" class="rd-fold-body">
              <div
                v-for="svc in referencedServices"
                :key="svc"
                class="rd-bind-row"
                :class="{ 'is-degraded': degraded(svc) }"
              >
                <span class="rd-bind-svc">{{ svc }}</span>
                <select class="rd-bind-user" v-model="bindings[svc].authAlias">
                  <option :value="undefined">— 未绑定 —</option>
                  <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
                </select>
                <input class="rd-bind-url" v-model="bindings[svc].url" placeholder="覆盖 URL(可选)" />
                <span v-if="degraded(svc)" class="rd-bind-warn">凭证已删,运行时该用户不注入</span>
              </div>
              <p v-if="!referencedServices.length" class="rd-empty">场景未引用任何 service</p>
            </div>
          </section>

          <!-- 预埋:插件列表 / 日志订阅(只读占位,待 gimbal 侧支持) -->
          <section class="rd-fold">
            <button class="rd-fold-head" type="button">
              插件列表
              <span class="rd-fold-summary">待 gimbal 侧支持</span>
            </button>
          </section>
          <section class="rd-fold">
            <button class="rd-fold-head" type="button">
              日志订阅
              <span class="rd-fold-summary">待 gimbal 侧支持</span>
            </button>
          </section>

          <!-- 错误显示 -->
          <div v-if="lastRunError" class="run-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div>
              <div class="err-title">运行失败</div>
              <div class="err-msg">{{ lastRunError }}</div>
            </div>
          </div>

          <!-- 成功显示 -->
          <div v-if="lastRunId && !lastRunError" class="run-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            <div>
              <div class="success-title">运行已发起</div>
              <div class="success-msg">runId: <code>{{ lastRunId }}</code> — 跳转到执行历史…</div>
            </div>
          </div>
        </div>

        <footer class="run-footer">
          <div class="run-summary">
            <span v-if="useBaseline || selectedDatasets.length === 0" class="summary-chip">基线 ×1</span>
            <span v-if="selectedDatasets.length" class="summary-chip">
              {{ selectedDatasets.length }} 数据集
            </span>
            <span v-if="selectedEnv" class="summary-chip env">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
              {{ selectedEnv }}
            </span>
            <span
              class="summary-chip total"
              :class="{ over: totalRuns > MAX_TOTAL_RUNS }"
              :title="totalRuns > MAX_TOTAL_RUNS ? `超过平台上限 ${MAX_TOTAL_RUNS},无法发起` : undefined"
            >
              {{ totalRuns }} 次运行
            </span>
            <span v-if="parallel > 1" class="summary-chip">
              并发 {{ parallel }}
            </span>
          </div>
          <div class="run-actions">
            <button class="ghost-btn" @click="$emit('close')">取消</button>
            <button
              class="primary-btn"
              data-testid="run-confirm"
              :disabled="!selectedEnv || running"
              @click="onConfirm"
            >
              <svg v-if="!running" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              <svg v-else class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
              {{ running ? '运行中…' : '发起运行' }}
            </button>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { ServiceBinding, RunScheme, RunOverlay } from '@/api/scenario-composer'
import type { Scenario, DataSetSummary, RunEnv } from '@/types/scenario-composer'

const props = withDefaults(defineProps<{
  /** 弹层显隐(父级亦可直接 v-if;默认 true 兼容外部 v-if 用法) */
  visible?: boolean
  scenario?: Scenario | null
  envs: RunEnv[]
  dataSets: DataSetSummary[]
  running?: boolean
  lastRunId?: string | null
  lastRunError?: string | null
  /** 运行方案(orchestration sidecar,Task 10 类型) */
  schemes: RunScheme[]
  /** 上次运行覆盖层(方案栏「上次运行」回填源) */
  lastRunOverlay: RunOverlay | null
  /** 场景引用的 service 名(用户与服务区每服务一行) */
  referencedServices: string[]
  /** 绑定下拉选项:owner 凭证池 ∪ 场景内置 users 别名(父级供给) */
  authOptions: string[]
  /** 平台编排展示名(orchestration.steps[i].name,与 steps 同序);plate Step 无 name */
  stepOrchestrationNames?: string[]
}>(), {
  visible: true,
  scenario: null,
  running: false,
  lastRunId: null,
  lastRunError: null,
  stepOrchestrationNames: () => [] as string[],
})

const emit = defineEmits<{
  close: []
  confirm: [
    envId: string,
    dataSetIds: string[],
    opts: {
      /** 0-based 含端点(引擎 halt_at);缺省 = 全量运行 */
      stepTo?: number
      /** 每行数据的重复执行次数(total = Σrows × nRuns) */
      nRuns?: number
      /** fan-out 并发度(1–200) */
      parallel?: number
      /** service → {authAlias?, url?};空绑定条目不随 confirm 下发 */
      serviceBindings?: Record<string, ServiceBinding>
    },
  ]
  /** 存为方案:当前 env/ds/绑定快照(plugins/logSub 预埋 no-op) */
  saveScheme: [scheme: RunScheme]
}>()

// ── 环境与数据集(既有语义保留)──────────────────────────────────
const selectedEnv = ref<string>(props.envs[0]?.envId || '')
const selectedDatasets = ref<string[]>([])
// D12 基线执行:不选数据集 = 直填值 + 共享变量默认值跑一次(一个隐式空覆盖行)
const useBaseline = ref(false)

watch(() => props.envs, (envs) => {
  if (!selectedEnv.value && envs.length > 0) {
    selectedEnv.value = envs[0].envId
  }
}, { immediate: true })

watch(() => props.dataSets, (ds) => {
  if (ds.length) {
    selectedDatasets.value = ds.map(d => d.datasetId)  // 默认全选(基线关)
  } else {
    useBaseline.value = true   // 无数据集:唯一可跑的就是基线
    selectedDatasets.value = []
  }
}, { immediate: true })

// 勾回任一数据集 → 退出基线(基线与数据集互斥:基线 = 空覆盖行)
watch(selectedDatasets, (v) => { if (v.length) useBaseline.value = false })

function toggleBaseline() {
  useBaseline.value = !useBaseline.value
  if (useBaseline.value) selectedDatasets.value = []
}

// ── 方案栏(spec §4):临时手填 / 上次运行 / 已存方案 ──────────────
const selectedScheme = ref<string>('__adhoc__')   // '__adhoc__' | '__last__' | scheme.name
const schemeNameDraft = ref('')

/** 方案配置降级:方案里的 env / 数据集已被删 → 选项标注(不报废,选了可改) */
const schemeDegraded = computed(() =>
  props.schemes
    .filter((s) =>
      (s.envId && !props.envs.some((e) => e.envId === s.envId)) ||
      s.dataSetIds.some((id) => !props.dataSets.some((d) => d.datasetId === id)))
    .map((s) => s.name))

const schemeOptions = computed(() => [
  { value: '__adhoc__', label: '临时手填' },
  ...(props.lastRunOverlay ? [{ value: '__last__', label: '上次运行' }] : []),
  ...props.schemes.map((s) => ({
    value: s.name,
    label: schemeDegraded.value.includes(s.name) ? `${s.name} · 配置已失效` : s.name,
  })),
])

// ── 用户与服务绑定(spec §3.1/§4)───────────────────────────────
// 绑定态:service → {authAlias?, url?};方案/上次运行选择时整体替换。
const bindings = ref<Record<string, ServiceBinding>>({})

// referencedServices 变化(异步补齐/场景变更)→ 补空行、清孤儿,行内
// v-model 直写 bindings[svc].authAlias,必须保证每个 svc 有落点对象。
watch(() => props.referencedServices, (svcs) => {
  const next = { ...bindings.value }
  for (const svc of svcs) if (!next[svc]) next[svc] = {}
  for (const k of Object.keys(next)) if (!svcs.includes(k)) delete next[k]
  bindings.value = next
}, { immediate: true })

// 选方案/上次运行 → 绑定整体替换预填 + env/ds 回填(已删项静默跳过 = 降级不报废)
watch(selectedScheme, (v) => {
  if (v === '__adhoc__') {
    bindings.value = Object.fromEntries(props.referencedServices.map((svc) => [svc, {} as ServiceBinding]))
    return
  }
  const src = v === '__last__'
    ? props.lastRunOverlay
    : props.schemes.find((s) => s.name === v)
  const next: Record<string, ServiceBinding> = {}
  for (const svc of props.referencedServices)
    next[svc] = src?.serviceBindings?.[svc] ? { ...src.serviceBindings[svc]! } : {}
  bindings.value = next
  if (src?.envId && props.envs.some((e) => e.envId === src.envId)) selectedEnv.value = src.envId
  // 无条件回填:基线方案(dataSetIds: [])也要把勾选重置回基线,
  // 不能沿用打开时的当前勾选。
  selectedDatasets.value = (src?.dataSetIds ?? []).filter((id) =>
    props.dataSets.some((d) => d.datasetId === id))
})

/** 降级:绑定引用的 alias 已不在凭证选项(凭证被删)→ 行标红,不阻塞运行 */
function degraded(svc: string): boolean {
  const a = bindings.value[svc]?.authAlias
  return !!a && !props.authOptions.includes(a)
}

const foldBindings = ref(false)   // 折叠区默认折叠

const bindingsSummary = computed(() => {
  const total = props.referencedServices.length
  if (!total) return '未引用服务'
  const bound = props.referencedServices.filter((svc) => {
    const b = bindings.value[svc]
    return !!(b?.authAlias || b?.url)
  }).length
  return `${bound}/${total} 已绑定`
})

// ── 基础设置(stepTo 0-based 含端点,nRuns × parallel)────────────
// V1 能力移植:stepTo 透传引擎 halt_at;null = 全量运行
const stepTo = ref<number | null>(null)
const nRuns = ref(1)
const parallel = ref(1)

const stepCount = computed(() => props.scenario?.stepCount ?? 0)

/** 下拉里附上步骤名,便于定位。展示名在 orchestration(plate Step 无
 *  name/id 字段);长度不齐或缺名时降级 Step N,不再恒空。 */
function stepName(i: number): string {
  const n = props.stepOrchestrationNames?.[i]
  return n ? ` · ${n}` : ` · Step ${i + 1}`
}

/** 总量闸(行数 × 每行重复):对齐后端 dispatch 侧
 * MAX_RUNS_PER_EXECUTION(app/core/config.py)的 409 too_many_runs。 */
const MAX_TOTAL_RUNS = 200

const totalRuns = computed(() => {
  // 基线或空选择都按一个隐式空行计(D12:confirm 原样透传空 dataSetIds 即基线,
  // 显示必须与派发语义一致,不能谎报 0 次)
  if (useBaseline.value || selectedDatasets.value.length === 0) return 1 * (nRuns.value || 1)
  return props.dataSets
    .filter(d => selectedDatasets.value.includes(d.datasetId))
    .reduce((sum, d) => sum + (d.rowCount || 0), 0) * (nRuns.value || 1)
})

function onConfirm() {
  if (!selectedEnv.value) {
    ElMessage.warning('请选择执行环境')
    return
  }
  // 输入钳位(与后端 schema 上限一致,防 422)
  nRuns.value = Math.min(1000, Math.max(1, Math.floor(nRuns.value || 1)))
  parallel.value = Math.min(200, Math.max(1, Math.floor(parallel.value || 1)))
  // 总量闸前置:dispatch 侧 rows × nRuns > 200 整单 409 too_many_runs,
  // 同闸提前拦(后端权威定义:app/core/config.py MAX_RUNS_PER_EXECUTION)。
  if (totalRuns.value > MAX_TOTAL_RUNS) {
    ElMessage.warning(
      `总运行次数 ${totalRuns.value} 超过平台上限 ${MAX_TOTAL_RUNS}(行数 × 每行重复)— 请减少数据集/重复次数`,
    )
    return
  }
  // 用户与服务绑定:空绑定条目不随 confirm 下发(后端注入清单 =
  // 模板扫描(steps 里 ${auth.*} 引用)∪ 绑定 authAlias,spec §6)
  const serviceBindings = Object.fromEntries(Object.entries(bindings.value)
    .filter(([, b]) => b.authAlias || b.url))
  emit('confirm', selectedEnv.value, selectedDatasets.value, {
    ...(stepTo.value !== null ? { stepTo: stepTo.value } : {}),
    ...(nRuns.value !== 1 ? { nRuns: nRuns.value } : {}),
    ...(parallel.value !== 1 ? { parallel: parallel.value } : {}),
    ...(Object.keys(serviceBindings).length ? { serviceBindings } : {}),
  })
}

/** 存为方案:当前 env/ds/绑定快照落 orchestration sidecar(plate 零感知)。
 *  插件/日志订阅为预埋 no-op(gimbal 侧就绪前恒 null)。 */
function onSaveScheme() {
  const name = schemeNameDraft.value.trim()
  if (!name) {
    ElMessage.warning('请填写方案名')
    return
  }
  emit('saveScheme', {
    name,
    envId: selectedEnv.value || null,
    dataSetIds: [...selectedDatasets.value],
    serviceBindings: { ...bindings.value },
    plugins: null,
    logSub: null,
  })
  // 不立即清空方案名草稿:PUT 失败(如 409 重名)时用户改名即可重试,
  // 清空会丢掉已输入的名字 — 由用户手动编辑/清空。
}

/** 新建数据集:跳转数据集编辑器(结构由调色板/稀疏行模型约束,
 *  裸 JSON 快速创建路径已退役 — 会引导未声明变量并 422)。 */
const router = useRouter()
function goCreateDataSet() {
  if (!props.scenario) {
    ElMessage.warning('请先保存草稿')
    return
  }
  router.push(`/scenarios/${props.scenario.meta.scenarioId}/data-sets/new`)
}
</script>

<style scoped>
.run-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 18, 25, 0.5);
  backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.run-dialog {
  width: 720px; max-width: 92vw; max-height: 88vh;
  background: #fff; border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.25);
  display: flex; flex-direction: column;
  animation: slideUp 0.25s ease-out;
}
@keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.run-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 24px 28px 20px;
  border-bottom: 1px solid #e6e8ec;
}
.run-header h2 { margin: 0 0 4px; font-size: 20px; }
.run-header .muted { font-size: 13px; color: #5a6273; }
.run-header .muted code { font-family: var(--font-mono); background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }

.icon-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; border-radius: 6px;
  color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.icon-btn:hover { background: #f5f6fa; color: #1a1d24; }

.run-body { padding: 20px 28px; flex: 1; overflow-y: auto; }
.run-section { margin-bottom: 24px; }
.run-label {
  display: block; font-size: 13px; font-weight: 600; color: #1a1d24;
  margin-bottom: 12px;
}
.run-label .muted { font-weight: 400; color: #94a3b8; }
.label-row { display: flex; justify-content: space-between; align-items: center; }
.link-btn {
  background: transparent; border: none; color: #4f46e5;
  font-size: 12px; cursor: pointer; padding: 0;
}
.link-btn:hover { text-decoration: underline; }

/* ── 方案栏(spec §4)────────────────────────────────────────── */
.rd-scheme-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; margin-bottom: 16px;
  border: 1.5px solid #e6e8ec; border-radius: 10px;
  background: #fafbfc;
}
.rd-scheme-select {
  min-width: 128px; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-scheme-name {
  flex: 1; min-width: 0; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-scheme-bar .ghost-btn { padding: 6px 12px; font-size: 12px; }

/* env grid */
.env-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;
}
.env-tile {
  text-align: left;
  background: #fff; border: 1.5px solid #e6e8ec; border-radius: 10px;
  padding: 12px 14px; cursor: pointer; transition: all 0.15s;
}
.env-tile:hover { border-color: #c7d2fe; }
.env-tile.active { border-color: #4f46e5; background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); }
.env-tile-head { display: flex; align-items: center; gap: 8px; }
.env-radio {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid #cbd5e1; transition: all 0.15s;
}
.env-tile.active .env-radio { border-color: #4f46e5; background: radial-gradient(circle, #4f46e5 0%, #4f46e5 35%, transparent 40%); }
.env-name { font-weight: 600; font-size: 13px; }
.env-url { font-family: var(--font-mono); font-size: 11px; color: #5a6273; margin-top: 4px; padding-left: 22px; }

/* data-set grid */
.ds-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.ds-tile {
  display: flex; gap: 10px;
  background: #fff; border: 1.5px solid #e6e8ec; border-radius: 10px;
  padding: 10px 12px; cursor: pointer; transition: all 0.15s;
}
.ds-tile input { margin-top: 2px; }
.ds-tile:hover { border-color: #c7d2fe; }
.ds-tile.active { border-color: #4f46e5; background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); }
.ds-info { flex: 1; min-width: 0; }
.ds-name { font-weight: 600; font-size: 13px; }
.ds-meta { display: flex; gap: 8px; margin-top: 2px; font-size: 11px; color: #5a6273; }
.ds-preview { margin-top: 4px; font-size: 10px; }
.ds-preview code { background: #f1f5f9; padding: 1px 4px; border-radius: 2px; }

.ds-grid-baseline { margin-bottom: 8px; }
.ds-tile.baseline { border-style: dashed; }

.empty-data {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 32px 20px; border: 1.5px dashed #cbd5e1; border-radius: 12px;
  color: #5a6273; text-align: center;
}
.empty-data p { margin: 0; font-size: 13px; }

/* 基础设置(stepTo / nRuns × parallel) */
.adv-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.adv-field {
  padding: 10px 12px;
  border: 1.5px solid #e6e8ec; border-radius: 10px;
}
.adv-name {
  display: block; font-size: 12px; font-weight: 600; margin-bottom: 6px;
}
.adv-select {
  width: 100%; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.num-row {
  display: flex; align-items: center; gap: 6px;
}
.adv-input {
  width: 100%; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.num-row .adv-input { width: 72px; }
.num-sep { font-size: 11px; color: #94a3b8; }

/* ── 折叠区 + 用户与服务绑定(spec §4)──────────────────────── */
.rd-fold {
  border: 1.5px solid #e6e8ec; border-radius: 10px;
  margin-bottom: 16px; background: #fff; overflow: hidden;
}
.rd-fold-head {
  width: 100%; display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border: none; background: transparent;
  font-size: 13px; font-weight: 600; color: #1a1d24;
  text-align: left; cursor: pointer; transition: background 0.15s;
}
.rd-fold-head:hover { background: #f5f6fa; }
.rd-fold.is-open .rd-fold-head { border-bottom: 1px solid #e6e8ec; }
.rd-fold-summary { margin-left: auto; font-size: 11px; font-weight: 400; color: #94a3b8; }
.rd-fold-body { padding: 12px; }

.rd-bind-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; margin-bottom: 8px;
  border: 1px solid #e6e8ec; border-radius: 8px;
}
.rd-bind-row:last-child { margin-bottom: 0; }
/* 降级:绑定引用的凭证已删 — 标红不报废,运行时该用户不注入 */
.rd-bind-row.is-degraded { border-color: #fca5a5; background: #fef2f2; }
.rd-bind-svc {
  min-width: 120px; font-family: var(--font-mono);
  font-size: 12px; font-weight: 600;
}
.rd-bind-user {
  min-width: 128px; padding: 5px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-bind-row.is-degraded .rd-bind-user { border-color: #fca5a5; }
.rd-bind-url {
  flex: 1; min-width: 0; padding: 5px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-bind-warn { font-size: 11px; color: #b91c1c; white-space: nowrap; }
.rd-empty { margin: 4px 0 0; font-size: 12px; color: #94a3b8; }

.run-error, .run-success {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 12px 14px; border-radius: 8px; margin-bottom: 16px;
}
.run-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.run-error svg { flex-shrink: 0; color: #ef4444; margin-top: 2px; }
.err-title { font-weight: 600; font-size: 13px; }
.err-msg { font-size: 12px; margin-top: 2px; font-family: var(--font-mono); }
.run-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.run-success svg { flex-shrink: 0; color: #10b981; margin-top: 2px; }
.success-title { font-weight: 600; font-size: 13px; }
.success-msg { font-size: 12px; margin-top: 2px; }
.success-msg code { font-family: var(--font-mono); background: #dcfce7; padding: 1px 4px; border-radius: 3px; }

/* footer */
.run-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 28px; border-top: 1px solid #e6e8ec;
  background: #fafbfc; border-radius: 0 0 16px 16px;
}
.run-summary { display: flex; gap: 6px; }
.summary-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
  background: #eef2ff; color: #4f46e5;
}
.summary-chip.env { background: #fef3c7; color: #92400e; }
.summary-chip.total { background: #d1fae5; color: #065f46; }
/* 总量超闸(dispatch 409 too_many_runs)→ 红色警示,confirm 亦被拦 */
.summary-chip.total.over { background: #fee2e2; color: #991b1b; }
.run-actions { display: flex; gap: 8px; }

.ghost-btn {
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.ghost-btn:hover { background: #f5f6fa; }

.primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border: none; border-radius: 8px;
  padding: 8px 18px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.2);
}
.primary-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.small { font-size: 11px; }

</style>
