<!--
  RunDialog.vue — 运行对话框 v2(方案工作台阶段③,spec 2026-09-15 §7)
  两路径:① 自建方案 = 只读概要(数据/注入/绑定/参数)+ 原样展平执行,
  失效(引用数据集已删/注入条目悬空)禁跑 + 去工作台修复;② 默认方案 =
  基线执行(数据/注入锁基线),用户与服务绑定 + 基础设置自由配置,可另存
  为自建方案。旧三态下拉(临时手填/上次运行/已存方案)与 RunPreset 退役;
  数据集勾选区/注入勾选区随路径语义移入方案工作台。
  绑定行 = 声明 ∪ 引用并集固定行(D3):service 名只读标签,auth 下拉 +
  URL 覆盖(唯一自由文本);未声明引用行标红「未声明」,现场填 URL 即救燃;
  预填未改动的声明 URL 不算显式绑定不上送(D3)。
-->
<template>
  <Teleport v-if="visible" to="body">
    <div class="run-overlay" @click.self="$emit('close')">
      <div class="run-dialog" role="dialog" aria-modal="true">
        <header class="run-header">
          <div>
            <h2>运行编排</h2>
            <p class="muted">从 <code>{{ scenario?.meta?.name || scenario?.meta?.scenarioId || '—' }}</code> 触发执行</p>
          </div>
          <button class="icon-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div class="run-body">
          <!-- 方案栏 v2(spec §7):两类 chip,无临时/上次 -->
          <div class="rd-scheme-chips" role="tablist">
            <button
              v-for="s in schemes" :key="s.schemeId"
              type="button"
              class="rd-chip"
              :class="{ active: s.schemeId === selected?.schemeId }"
              :data-testid="`scheme-chip-${s.schemeId}`"
              @click="selectScheme(s.schemeId)"
            >
              <span v-if="s.isDefault" class="rd-chip-tag">默认</span>
              {{ s.name }}
              <span v-if="!s.isDefault && isSchemeInvalid(s)" class="rd-chip-warn">· 失效</span>
            </button>
          </div>

          <!-- ═══ 路径②:默认方案 — 可配区(仅绑定 + 参数),数据/注入锁基线 ═══ -->
          <template v-if="selected?.isDefault">
            <div class="rd-baseline-note" data-testid="baseline-note">
              基线执行 — 不选数据集与注入条目;如需带数据/注入的方案,请在<a class="rd-link"
                @click="goWorkbench()">方案工作台</a>配置。
            </div>

            <!-- 用户与服务绑定(平铺不折叠,spec §6 ③) -->
            <section class="run-section">
              <label class="run-label">用户与服务 <span class="muted small">(声明 ∪ 引用并集)</span></label>
              <div v-for="row in serviceRows" :key="row.service"
                class="rd-bind-row"
                :class="{ 'is-degraded': degraded(row.service), 'is-undeclared': row.declaredUrl === null }">
                <span class="rd-bind-svc">{{ row.service }}</span>
                <select class="rd-bind-user" v-model="bindings[row.service].authAlias">
                  <option :value="undefined">— 未绑定 —</option>
                  <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
                </select>
                <input class="rd-bind-url" v-model="bindings[row.service].url"
                  :placeholder="row.declaredUrl === null ? '未声明 — 现场填 URL 即可运行' : '覆盖 URL(可选,已预填声明值)'" />
                <span v-if="row.declaredUrl === null" class="rd-bind-warn undeclared">未声明</span>
                <span v-else-if="degraded(row.service)" class="rd-bind-warn">凭证已删,运行时该用户不注入</span>
              </div>
              <p v-if="!serviceRows.length" class="rd-empty">场景未声明且未引用任何 service</p>
            </section>

            <!-- 基础设置(stepTo / nRuns × parallel;旧 凭证策略·前缀·预设 已退役) -->
            <section class="run-section">
              <label class="run-label">基础设置 <span class="muted small">(步进调试 / 批量执行)</span></label>
              <div class="adv-grid">
                <div class="adv-field">
                  <span class="adv-name">停止于步骤</span>
                  <select v-model.number="stepTo" class="adv-select" data-testid="step-to" :disabled="stepCount === 0">
                    <option :value="null" :disabled="stepCount === 0">运行全部步骤</option>
                    <option v-for="i in stepCount" :key="i" :value="i - 1">
                      第 {{ i }} 步后停止{{ stepName(i - 1) }}
                    </option>
                  </select>
                </div>
                <div class="adv-field">
                  <span class="adv-name">执行次数 / 并发度</span>
                  <div class="num-row">
                    <input type="number" v-model.number="nRuns" class="adv-input" data-testid="n-runs" min="1" max="1000" />
                    <span class="num-sep">次 ×</span>
                    <input type="number" v-model.number="parallel" class="adv-input" data-testid="parallel" min="1" max="200" />
                    <span class="num-sep">并发</span>
                  </div>
                </div>
              </div>
              <div v-if="stepCount === 0" class="muted small">场景暂无步骤,停止于步骤不可用</div>
            </section>

            <!-- 另存为方案(D3:默认方案自由配置可另存) -->
            <section class="run-section rd-save-as">
              <label class="run-label">另存为方案 <span class="muted small">(当前绑定与参数存为自建方案)</span></label>
              <div class="rd-save-row">
                <input class="rd-scheme-name" data-testid="scheme-name-input"
                  v-model="saveAsName" placeholder="方案名" maxlength="64" />
                <button class="ghost-btn" data-testid="save-as-scheme" type="button" @click="onSaveAsScheme">另存为方案</button>
              </div>
            </section>
          </template>

          <!-- ═══ 路径①:自建方案 — 只读概要,失效禁跑 ═══ -->
          <template v-else-if="selected">
            <section class="run-section rd-summary" data-testid="scheme-summary">
              <div class="rd-sum-row">
                <span class="rd-sum-label">数据</span>
                <span class="rd-sum-value">
                  <template v-if="selected.dataSetSelection.length">
                    {{ sumRows(selected) }} 行 / {{ selected.dataSetSelection.length }} 数据集
                    <span class="muted small">({{ selected.dataSetSelection.map(dsLabel).join('、') }})</span>
                  </template>
                  <template v-else>基线(无数据集)</template>
                </span>
              </div>
              <div class="rd-sum-row">
                <span class="rd-sum-label">断言注入</span>
                <span class="rd-sum-value">
                  {{ selected.injectionEntryIds.length ? `${selected.injectionEntryIds.length} 条目` : '无' }}
                </span>
              </div>
              <div class="rd-sum-row">
                <span class="rd-sum-label">绑定</span>
                <span class="rd-sum-value">
                  <template v-if="Object.keys(selected.serviceBindings).length">
                    <span v-for="(b, svc) in selected.serviceBindings" :key="svc" class="rd-sum-bind">
                      {{ svc }}{{ b.authAlias ? ` → ${b.authAlias}` : '' }}{{ b.url ? `(URL 覆盖)` : '' }}
                    </span>
                  </template>
                  <template v-else>无显式绑定</template>
                </span>
              </div>
              <div class="rd-sum-row">
                <span class="rd-sum-label">参数</span>
                <span class="rd-sum-value">
                  {{ selected.stepTo === null ? '全量步骤' : `停于第 ${selected.stepTo + 1} 步` }} ·
                  {{ selected.nRuns }} 次 × {{ selected.parallel }} 并发
                </span>
              </div>
            </section>

            <!-- 失效横幅(spec §9):引用数据集已删 / 注入条目悬空 → 禁跑 + 去工作台修复 -->
            <div v-if="isSchemeInvalid(selected)" class="run-error" data-testid="scheme-invalid">
              <div>
                <div class="err-title">配置已失效 — 不可运行</div>
                <div class="err-msg">{{ invalidReason(selected) }}</div>
                <button class="ghost-btn rd-fix-btn" data-testid="fix-in-workbench" type="button"
                  @click="goWorkbench(selected.schemeId)">去工作台修复</button>
              </div>
            </div>
          </template>

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
            <span v-if="selected?.isDefault" class="summary-chip">基线 ×{{ nRuns || 1 }}</span>
            <template v-else-if="selected">
              <span v-if="selected.dataSetSelection.length" class="summary-chip">
                {{ selected.dataSetSelection.length }} 数据集
              </span>
              <span v-if="selected.injectionEntryIds.length" class="summary-chip">
                {{ selected.injectionEntryIds.length }} 注入条目
              </span>
            </template>
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
              :disabled="running || (selected !== null && !selected.isDefault && isSchemeInvalid(selected))"
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
import type { DataSetSelection, ServiceBinding, SchemeV2 } from '@/api/scenario-composer'
import { scenarioSchemesUrl } from '@/utils/links'
import type { Scenario, DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'

/** 绑定行(spec D3):声明 ∪ 引用并集的固定行;declaredUrl null = 未声明引用行 */
export interface ServiceRow { service: string; declaredUrl: string | null }

const props = withDefaults(defineProps<{
  /** 弹层显隐(父级亦可直接 v-if;默认 true 兼容外部 v-if 用法) */
  visible?: boolean
  scenario?: Scenario | null
  /** 数据集清单:自建方案失效判定/概要行数与数据集名展示用(选择交互已移入工作台) */
  dataSets?: DataSetSummary[]
  running?: boolean
  lastRunId?: string | null
  lastRunError?: string | null
  /** 运行方案(阶段② CRUD wire;default 置顶由宿主保证) */
  schemes: SchemeV2[]
  /** 深链预选(工作台「▶ 运行此方案」);null/不在列表 = 默认方案 */
  initialSchemeId?: string | null
  /** 绑定行 = 声明 ∪ 引用并集(D3);declaredUrl null = 未声明引用行(红,可救燃) */
  serviceRows: ServiceRow[]
  /** 绑定下拉选项:owner 凭证池 ∪ 场景内置 users 别名(父级供给) */
  authOptions: string[]
  /** 平台编排展示名(orchestration.steps[i].name,与 steps 同序);plate Step 无 name */
  stepOrchestrationNames?: string[]
  /** 断言注册表条目(spec v3 §2/§4):自建方案注入条目失效判定面;空 = 全部悬空 */
  assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>
  /** 死条目(悬空)id — 宿主预计算(useInjectableSurface 分组),失效判定沿用 */
  deadEntryIds?: string[]
}>(), {
  visible: true,
  scenario: null,
  dataSets: () => [] as DataSetSummary[],
  running: false,
  lastRunId: null,
  lastRunError: null,
  initialSchemeId: null,
  stepOrchestrationNames: () => [] as string[],
  assertionEntries: () => [] as AssertionEntry[],
  deadEntryIds: () => [] as string[],
})

const emit = defineEmits<{
  close: []
  /** 契约取数降级重试入口(消费面随注入勾选区退役,契约保留供宿主过渡) */
  retryContract: []
  confirm: [
    dataSetSelection: DataSetSelection[],
    opts: {
      /** 溯源:本次执行按哪个方案发起(两态都带) */
      schemeId: string
      schemeName: string
      /** 0-based 含端点(引擎 halt_at);缺省 = 全量运行 */
      stepTo?: number
      /** 每行数据的重复执行次数(total = Σrows × nRuns) */
      nRuns?: number
      /** fan-out 并发度(1–200) */
      parallel?: number
      /** service → {authAlias?, url?};空绑定条目不随 confirm 下发,
       *  预填未改动的声明 URL 也不算显式绑定不上送(D3) */
      serviceBindings?: Record<string, ServiceBinding>
      /** 断言注入条目 id(spec v3 §4):与数据集行**交叉**成 case;
       *  空选不随 confirm 下送 */
      injectionEntryIds?: string[]
    },
  ]
  /** 另存为方案(仅默认方案态):当前绑定与参数存为自建方案(基线空选择) */
  saveAsScheme: [body: Omit<SchemeV2, 'schemeId' | 'isDefault'>]
}>()

// ── 方案选择(spec §7 两路径)──────────────────────────────────
const selectedId = ref<string | null>(null)
const selected = computed<SchemeV2 | null>(() =>
  props.schemes.find((s) => s.schemeId === selectedId.value)
  ?? props.schemes.find((s) => s.isDefault)
  ?? props.schemes[0] ?? null)

function selectScheme(id: string) { selectedId.value = id }

// 深链预选(Task 5 工作台「▶ 运行此方案」):initialSchemeId 在列表中 → 预选;
// 选中项被删(宿主整表回填收缩)→ 回默认方案。
watch(() => props.schemes, (list) => {
  if (selectedId.value && list.some((s) => s.schemeId === selectedId.value)) return
  const initial = list.find((s) => s.schemeId === props.initialSchemeId)
  selectedId.value = initial?.schemeId ?? list.find((s) => s.isDefault)?.schemeId ?? null
}, { immediate: true })

// ── 用户与服务绑定(spec D3:声明 ∪ 引用并集固定行)────────────────
// 绑定态:service → {authAlias?, url?}。默认方案态的初始预填来自默认方案
// 存量(工作台可配),声明 URL 兜底;自建方案态绑定只读(概要行展示)。
const bindings = ref<Record<string, ServiceBinding>>({})

function declaredUrlOf(svc: string): string | null {
  return props.serviceRows.find((r) => r.service === svc)?.declaredUrl ?? null
}

/** 行级显式绑定(D3,confirm 下发与另存快照同口径):预填未改动的
 *  声明 URL 不算显式绑定(否则 confirm 重送成覆盖、快照钉死旧声明
 *  URL);未声明行任何非空 URL 都是救燃绑定。非显式行返回 undefined。 */
function explicitBindingOf(
  b: ServiceBinding | undefined,
  declared: string | null,
): ServiceBinding | undefined {
  const url = b?.url?.trim()
  const effectiveUrl = url && url !== declared ? url : undefined
  const authAlias = b?.authAlias || undefined
  if (!authAlias && !effectiveUrl) return undefined
  return {
    ...(authAlias ? { authAlias } : {}),
    ...(effectiveUrl ? { url: effectiveUrl } : {}),
  }
}

/** 装配显式绑定记录:空绑定条目不落(confirm 下发与另存快照共用;
 *  后端注入清单 = 模板扫描(steps 里 ${auth.*} 引用)∪ 绑定 authAlias,spec §6) */
function explicitServiceBindings(): Record<string, ServiceBinding> {
  const out: Record<string, ServiceBinding> = {}
  for (const svc of Object.keys(bindings.value)) {
    const eb = explicitBindingOf(bindings.value[svc], declaredUrlOf(svc))
    if (eb) out[svc] = eb
  }
  return out
}

// serviceRows 变化(异步补齐/场景变更)→ 补行、清孤儿;行内 v-model 直写
// bindings[svc].authAlias,必须保证每个 svc 有落点对象。声明行预填声明 URL。
watch([() => props.schemes, () => props.serviceRows], () => {
  if (!selected.value?.isDefault) return
  const d = props.schemes.find((s) => s.isDefault)
  const next: Record<string, ServiceBinding> = {}
  for (const r of props.serviceRows) {
    const b = d?.serviceBindings?.[r.service]
    next[r.service] = {
      ...(b?.authAlias ? { authAlias: b.authAlias } : {}),
      url: b?.url ?? r.declaredUrl ?? undefined,
    }
  }
  bindings.value = next
}, { immediate: true })

/** 降级:绑定引用的 alias 已不在凭证选项(凭证被删)→ 行标红,不阻塞运行 */
function degraded(svc: string): boolean {
  const a = bindings.value[svc]?.authAlias
  return !!a && !props.authOptions.includes(a)
}

// ── 自建方案失效判定(spec §9)─────────────────────────────────
// 与旧 schemeDegraded 同口径:引用数据集已删 or 注入条目不在 liveEntryIds
// (悬空/已删/旧版 — deadEntryIds 由宿主掩空决策,契约在途不误判)。
const liveEntryIds = computed(() =>
  new Set(props.assertionEntries
    .filter((e) => !isLegacyEntry(e) && !new Set(props.deadEntryIds).has(e.id))
    .map((e) => e.id)))

function isSchemeInvalid(s: SchemeV2): boolean {
  return s.dataSetSelection.some((x) => !props.dataSets.some((d) => d.datasetId === x.datasetId))
    || s.injectionEntryIds.some((id) => !liveEntryIds.value.has(id))
}

function invalidReason(s: SchemeV2): string {
  const deadDs = s.dataSetSelection.filter((x) => !props.dataSets.some((d) => d.datasetId === x.datasetId))
  if (deadDs.length) return `数据集 ${deadDs.map((x) => x.datasetId).join('、')} 已删除`
  return '注入条目已悬空或删除'
}

/** 概要行数:段带 rowIndexes 按段计,缺省段 = 整库(空库按 1 隐式行) */
const sumRows = (s: SchemeV2) => s.dataSetSelection.reduce((n, x) =>
  n + (x.rowIndexes?.length
    ?? Math.max(props.dataSets.find((d) => d.datasetId === x.datasetId)?.rowCount ?? 0, 1)), 0)
const dsLabel = (x: { datasetId: string }) =>
  props.dataSets.find((d) => d.datasetId === x.datasetId)?.name ?? x.datasetId

// ── 基础设置(stepTo 0-based 含端点,nRuns × parallel)────────────
// V1 能力移植:stepTo 透传引擎 halt_at;null = 全量运行。默认方案态可配
// (ref 即输入源);自建方案态只读展示用同一 ref(选中时重置为方案值)。
const stepTo = ref<number | null>(null)
const nRuns = ref(1)
const parallel = ref(1)
const saveAsName = ref('')

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

// 选中切换 → 参数/另存名重置:默认方案态 ← default 方案存量值;
// 自建方案态 ← 方案值(只读展示,confirm 取方案值不取 ref 篡改值)。
watch(selected, (s) => {
  stepTo.value = s?.stepTo ?? null
  nRuns.value = s?.nRuns ?? 1
  parallel.value = s?.parallel ?? 1
  saveAsName.value = ''
}, { immediate: true })

// ── 另存为方案(仅默认方案态)──────────────────────────────────
function onSaveAsScheme() {
  const name = saveAsName.value.trim()
  if (!name) { ElMessage.warning('请填写方案名'); return }
  if (name === '默认方案') { ElMessage.warning('「默认方案」为保留名'); return }
  emit('saveAsScheme', {
    name, dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: explicitServiceBindings(),
    stepTo: stepTo.value, nRuns: nRuns.value, parallel: parallel.value,
    plugins: null, logSub: null,
  })
}

// ── 工作台跳转(基线提示/失效横幅)──────────────────────────────
const router = useRouter()
function goWorkbench(schemeId?: string) {
  if (!props.scenario) { emit('close'); return }
  router.push(scenarioSchemesUrl(props.scenario.meta.scenarioId, schemeId))
}

// ── confirm(两路径,spec §7):溯源恒带 ────────────────────────
const totalRuns = computed(() => {
  if (!selected.value) return 0
  if (selected.value.isDefault) return 1 * Math.max(nRuns.value || 1, 1)   // 基线 × nRuns
  return sumRows(selected.value) * Math.max(selected.value.injectionEntryIds.length, 1)
    * (nRuns.value || 1)
})

function onConfirm() {
  const s = selected.value
  if (!s) return
  // 输入钳位(与后端 schema 上限一致,防 422)
  nRuns.value = Math.min(1000, Math.max(1, Math.floor(nRuns.value || 1)))
  parallel.value = Math.min(200, Math.max(1, Math.floor(parallel.value || 1)))
  // 总量闸前置:dispatch 侧 rows × nRuns > 200 整单 409 too_many_runs,
  // 同闸提前拦(后端权威定义:app/core/config.py MAX_RUNS_PER_EXECUTION)。
  if (totalRuns.value > MAX_TOTAL_RUNS) {
    ElMessage.warning(`总运行次数 ${totalRuns.value} 超过平台上限 ${MAX_TOTAL_RUNS} — 请调整方案参数`)
    return
  }
  if (!s.isDefault && isSchemeInvalid(s)) return   // 失效禁跑(按钮也禁,双保险)
  const common = { schemeId: s.schemeId, schemeName: s.name }
  if (s.isDefault) {
    const serviceBindings = explicitServiceBindings()
    emit('confirm', [], {
      ...common,
      ...(stepTo.value !== null ? { stepTo: stepTo.value } : {}),
      ...(nRuns.value !== 1 ? { nRuns: nRuns.value } : {}),
      ...(parallel.value !== 1 ? { parallel: parallel.value } : {}),
      ...(Object.keys(serviceBindings).length ? { serviceBindings } : {}),
    })
    return
  }
  // 自建方案:原样展平(不允许运行时篡改,D3)
  emit('confirm', s.dataSetSelection.map((x) => ({ ...x })), {
    ...common,
    ...(s.stepTo !== null ? { stepTo: s.stepTo } : {}),
    ...(s.nRuns !== 1 ? { nRuns: s.nRuns } : {}),
    ...(s.parallel !== 1 ? { parallel: s.parallel } : {}),
    ...(Object.keys(s.serviceBindings).length ? { serviceBindings: { ...s.serviceBindings } } : {}),
    ...(s.injectionEntryIds.length ? { injectionEntryIds: [...s.injectionEntryIds] } : {}),
  })
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

/* ── 方案栏 v2(spec §7:两类 chip,无临时/上次)────────────── */
.rd-scheme-chips {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-bottom: 20px;
}
.rd-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px;
  border: 1.5px solid #e6e8ec; border-radius: 999px;
  background: #fff; font-size: 12px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.rd-chip:hover { border-color: #c7d2fe; color: #1a1d24; }
.rd-chip.active {
  border-color: #4f46e5; color: #4f46e5; font-weight: 600;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
}
.rd-chip-tag {
  font-size: 10px; font-weight: 600; padding: 1px 6px;
  border-radius: 999px; background: #eef2ff; color: #4f46e5;
}
.rd-chip.active .rd-chip-tag { background: #fff; }
.rd-chip-warn { font-size: 11px; color: #b91c1c; }

/* ── 默认方案态:基线提示 ──────────────────────────────────── */
.rd-baseline-note {
  padding: 10px 12px; margin-bottom: 24px;
  border: 1.5px dashed #c7d2fe; border-radius: 10px;
  background: #fafbff;
  font-size: 12px; color: #5a6273; line-height: 1.6;
}
.rd-link { color: #4f46e5; cursor: pointer; }
.rd-link:hover { text-decoration: underline; }

/* ── 绑定行(spec D3)─────────────────────────────────────── */
.rd-bind-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; margin-bottom: 8px;
  border: 1px solid #e6e8ec; border-radius: 8px;
}
.rd-bind-row:last-child { margin-bottom: 0; }
/* 降级:绑定引用的凭证已删 — 标红不报废,运行时该用户不注入 */
.rd-bind-row.is-degraded { border-color: #fca5a5; background: #fef2f2; }
/* 未声明引用行(D3):service 名标红 + 「未声明」警示,现场填 URL 即救燃 */
.rd-bind-row.is-undeclared .rd-bind-svc { color: #dc2626; font-weight: 600; }
.rd-bind-warn.undeclared { color: #dc2626; }
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

/* ── 另存为方案(默认方案态)───────────────────────────────── */
.rd-save-row { display: flex; align-items: center; gap: 8px; }
.rd-scheme-name {
  flex: 1; min-width: 0; max-width: 320px; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-save-row .ghost-btn { padding: 6px 12px; font-size: 12px; white-space: nowrap; }

/* ── 自建方案只读概要(spec §7 路径①)──────────────────────── */
.rd-summary {
  border: 1.5px solid #e6e8ec; border-radius: 10px;
  padding: 6px 14px; background: #fff;
}
.rd-sum-row {
  display: flex; gap: 12px; align-items: baseline;
  padding: 10px 0;
  border-bottom: 1px dashed #eef0f4;
  font-size: 12px;
}
.rd-sum-row:last-child { border-bottom: none; }
.rd-sum-label {
  min-width: 64px; font-size: 12px; font-weight: 600; color: #1a1d24;
}
.rd-sum-value { flex: 1; min-width: 0; color: #3f4756; line-height: 1.8; }
.rd-sum-bind {
  display: inline-block; margin: 0 6px 2px 0;
  font-family: var(--font-mono); font-size: 11px;
  background: #f1f5f9; padding: 1px 6px; border-radius: 4px;
}

/* 失效横幅内的修复按钮 */
.rd-fix-btn { margin-top: 8px; padding: 5px 10px; font-size: 12px; }

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
.run-summary { display: flex; gap: 6px; flex-wrap: wrap; }
.summary-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
  background: #eef2ff; color: #4f46e5;
}
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
