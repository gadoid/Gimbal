<!--
  RunConfigPanel.vue — 运行配置面板(执行设计 §1.5:RunDialog 剥壳产物)。

  纯内容组件:方案 chip 两路径(自建只读概要 / 默认可配)+ 声明∪引用并集
  绑定行 + 基础设置 + 另存为方案 + 失效横幅 + footer(摘要 chips + 确认)。
  弹层壳(RunDialog)与执行器页右栏(Runner.vue)共用本面板;右栏内嵌时
  `footer=false`(队列级「发起执行」取代单条确认),宽度自适应容器,不读
  固定弹窗宽。

  显式绑定 / 降级 / 总量闸 / 失效判定等纯函数来自 utils/run-bindings.ts
  (单源,§1.5);死集输入 = 宿主传入的 deadEntryIds(useInjectableSurface
  的唯一派生,本组件不复算)。
-->
<template>
  <div class="rc-panel">
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
        <span v-if="!s.isDefault && schemeInvalid(s)" class="rd-chip-warn">· 失效</span>
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
      <section v-if="footer" class="run-section rd-save-as">
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
              <span v-for="(b, svc) in selected.serviceBindings" :key="svc" class="rd-sum-bind"
                :class="{ 'is-degraded': degradedAliasOf(b.authAlias) }">
                {{ svc }}{{ b.authAlias ? ` → ${b.authAlias}` : '' }}{{ b.url ? `(URL 覆盖)` : '' }}
                <span v-if="degradedAliasOf(b.authAlias)" class="rd-sum-warn">凭证已删,去工作台重选</span>
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
      <div v-if="schemeInvalid(selected)" class="run-error" data-testid="scheme-invalid">
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
        <div class="success-msg">runId: <code>{{ lastRunId }}</code></div>
      </div>
    </div>

    <!-- footer(摘要 + 确认/取消):仅弹层壳渲染;右栏内嵌由宿主给队列级动作 -->
    <footer v-if="footer" class="run-footer">
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
        <button class="ghost-btn" @click="$emit('cancel')">取消</button>
        <button
          class="primary-btn"
          data-testid="run-confirm"
          :disabled="running || (selected !== null && !selected.isDefault && schemeInvalid(selected))"
          @click="onConfirm"
        >
          <svg v-if="!running" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <svg v-else class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
          {{ running ? '运行中…' : '发起运行' }}
        </button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import type { DataSetSelection, ServiceBinding, SchemeV2 } from '@/api/scenario-composer'
import { scenarioSchemesUrl } from '@/utils/links'
import type { Scenario, DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import {
  MAX_TOTAL_RUNS, assembleExplicitBindings, datasetLabel, degradedAlias,
  isSchemeInvalid, liveEntryIdSet, schemeInvalidReason, schemeRowsTotal,
  type ServiceRow,
} from '@/utils/run-bindings'

const props = withDefaults(defineProps<{
  /** 弹层壳 = true(footer 摘要 + 确认/取消);执行器右栏内嵌 = false */
  footer?: boolean
  scenario?: Scenario | null
  /** 数据集清单:自建方案失效判定/概要行数与数据集名展示用 */
  dataSets?: DataSetSummary[]
  running?: boolean
  lastRunId?: string | null
  lastRunError?: string | null
  /** 运行方案(default 置顶由宿主保证) */
  schemes: SchemeV2[]
  /** 深链预选(工作台「▶ 运行此方案」);null/不在列表 = 默认方案 */
  initialSchemeId?: string | null
  /** 绑定行 = 声明 ∪ 引用并集(D3);declaredUrl null = 未声明引用行 */
  serviceRows: ServiceRow[]
  /** 绑定下拉选项:owner 凭证池 ∪ 场景内置 users 别名(宿主供给) */
  authOptions: string[]
  /** 平台编排展示名(orchestration.steps[i].name,与 steps 同序) */
  stepOrchestrationNames?: string[]
  /** 断言注册表条目:自建方案注入条目失效判定面 */
  assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>
  /** 死条目(门控后)id — useInjectableSurface.deadIds,宿主传入 */
  deadEntryIds?: string[]
}>(), {
  footer: true,
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
  /** footer 的取消键(仅弹层壳消费;内嵌态无 footer 不发) */
  cancel: []
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
      /** service → {authAlias?, url?};空绑定条目不随 confirm 下发 */
      serviceBindings?: Record<string, ServiceBinding>
      /** 断言注入条目 id:与数据集行**交叉**成 case;空选不随 confirm 下送 */
      injectionEntryIds?: string[]
    },
  ]
  /** 另存为方案(仅默认方案态):当前绑定与参数存为自建方案 */
  saveAsScheme: [body: Omit<SchemeV2, 'schemeId' | 'isDefault'>]
}>()

// ── 方案选择(spec §7 两路径)──────────────────────────────────
const selectedId = ref<string | null>(null)
const selected = computed<SchemeV2 | null>(() =>
  props.schemes.find((s) => s.schemeId === selectedId.value)
  ?? props.schemes.find((s) => s.isDefault)
  ?? props.schemes[0] ?? null)

function selectScheme(id: string) { selectedId.value = id }

// 深链预选(工作台「▶ 运行此方案」):initialSchemeId 在列表中 → 预选;
// 选中项被删(宿主整表回填收缩)→ 回默认方案。
watch(() => props.schemes, (list) => {
  if (selectedId.value && list.some((s) => s.schemeId === selectedId.value)) return
  const initial = list.find((s) => s.schemeId === props.initialSchemeId)
  selectedId.value = initial?.schemeId ?? list.find((s) => s.isDefault)?.schemeId ?? null
}, { immediate: true })

// ── 用户与服务绑定(spec D3:声明 ∪ 引用并集固定行)────────────────
// 绑定态:service → {authAlias?, url?}。默认方案态的初始预填来自默认方案
// 存量,声明 URL 兜底;自建方案态绑定只读(概要行展示)。
const bindings = ref<Record<string, ServiceBinding>>({})

function declaredUrlOf(svc: string): string | null {
  return props.serviceRows.find((r) => r.service === svc)?.declaredUrl ?? null
}

// serviceRows 变化(异步补齐/场景变更)→ 补行、清孤儿;行内 v-model 直写
// bindings[svc].authAlias,必须保证每个 svc 有落点对象。声明行预填声明 URL。
// 依赖含 selected:深链自建方案挂载时本 watch guard return 过一次,切回
// 默认方案必须重算填充 — 否则 bindings 恒空,绑定行 v-model 对 undefined
// 求值直接渲染崩溃。切换即重置(与参数 watch(selected) 同语义)。
watch([() => props.schemes, () => props.serviceRows, selected], () => {
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

/** 默认方案态绑定行降级(读编辑中的 bindings) */
function degraded(svc: string): boolean {
  return degradedAlias(bindings.value[svc]?.authAlias, props.authOptions)
}
/** 概要态降级(读方案存量绑定) */
function degradedAliasOf(alias: string | undefined): boolean {
  return degradedAlias(alias, props.authOptions)
}

// ── 自建方案失效判定(活集 = registry 全集 − 宿主门控死集)─────────
const liveEntries = computed(() =>
  liveEntryIdSet(props.assertionEntries, props.deadEntryIds))

/** 模板/confirm 共用的本组件判定入口(死集由宿主 surface 派生,这里只组装) */
function schemeInvalid(s: SchemeV2): boolean {
  return isSchemeInvalid(s, props.dataSets, liveEntries.value)
}

function invalidReason(s: SchemeV2): string {
  return schemeInvalidReason(s, props.dataSets)
}

const sumRows = (s: SchemeV2) => schemeRowsTotal(s, props.dataSets)
const dsLabel = (x: { datasetId: string }) => datasetLabel(x, props.dataSets)

// ── 基础设置(stepTo 0-based 含端点,nRuns × parallel)────────────
const stepTo = ref<number | null>(null)
const nRuns = ref(1)
const parallel = ref(1)
const saveAsName = ref('')

const stepCount = computed(() => props.scenario?.stepCount ?? 0)

/** 下拉里附上步骤名,便于定位。展示名在 orchestration(plate Step 无
 * name/id 字段);长度不齐或缺名时降级 Step N,不再恒空。 */
function stepName(i: number): string {
  const n = props.stepOrchestrationNames?.[i]
  return n ? ` · ${n}` : ` · Step ${i + 1}`
}

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
  if (!name) { toast.warning('请填写方案名'); return }
  if (name === '默认方案') { toast.warning('「默认方案」为保留名'); return }
  emit('saveAsScheme', {
    name, dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: assembleExplicitBindings(bindings.value, props.serviceRows),
    stepTo: stepTo.value, nRuns: nRuns.value, parallel: parallel.value,
    plugins: null, logSub: null,
  })
}

// ── 工作台跳转(基线提示/失效横幅)──────────────────────────────
const router = useRouter()
function goWorkbench(schemeId?: string) {
  if (!props.scenario) return
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
  // 文案分态:自建方案参数只读 → 指去工作台;默认方案态参数就地可调。
  if (totalRuns.value > MAX_TOTAL_RUNS) {
    const hint = s.isDefault ? '请调整方案参数' : '请到方案工作台调整方案参数'
    toast.warning(`总运行次数 ${totalRuns.value} 超过平台上限 ${MAX_TOTAL_RUNS} — ${hint}`)
    return
  }
  if (!s.isDefault && schemeInvalid(s)) return   // 失效禁跑(按钮也禁,双保险)
  const common = { schemeId: s.schemeId, schemeName: s.name }
  if (s.isDefault) {
    const serviceBindings = assembleExplicitBindings(bindings.value, props.serviceRows)
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
.rc-panel { display: flex; flex-direction: column; min-width: 0; }

.run-section { margin-bottom: 24px; }
.run-section:last-child { margin-bottom: 0; }
.run-label {
  display: block; font-size: 13px; font-weight: 600; color: #10151C;
  margin-bottom: 12px;
}
.run-label .muted { font-weight: 400; color: #8B93A1; }

/* ── 方案栏 v2(spec §7 + 执行设计 1 号原型:选中 = 深色实心 chip)── */
.rd-scheme-chips {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-bottom: 20px;
}
.rd-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px;
  border: 1.5px solid #E1E5EB; border-radius: 999px;
  background: #fff; font-size: 12px; color: #5B6472;
  cursor: pointer; transition: all 0.15s;
}
.rd-chip:hover { border-color: #2F6FED; color: #10151C; }
.rd-chip.active {
  border-color: #10151C; color: #fff; font-weight: 600;
  background: #10151C;
}
.rd-chip-tag {
  font-size: 10px; font-weight: 600; padding: 1px 6px;
  border-radius: 999px; background: #E7EFFF; color: #2F6FED;
}
.rd-chip.active .rd-chip-tag { background: rgba(255, 255, 255, .16); color: #fff; }
.rd-chip-warn { font-size: 11px; color: #DC2626; }
.rd-chip.active .rd-chip-warn { color: #FCA5A5; }

/* ── 默认方案态:基线提示 ──────────────────────────────────── */
.rd-baseline-note {
  padding: 10px 12px; margin-bottom: 24px;
  border: 1.5px dashed rgba(47, 111, 237, .35); border-radius: 10px;
  background: #F6F8FC;
  font-size: 12px; color: #5B6472; line-height: 1.6;
}
.rd-link { color: #2F6FED; cursor: pointer; }
.rd-link:hover { text-decoration: underline; }

/* ── 绑定行(spec D3;蓝紫灰 = 配置面)────────────────────── */
.rd-bind-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; margin-bottom: 8px;
  border: 1px solid #E1E5EB; border-radius: 8px;
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
  border: 1px solid #E1E5EB; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-bind-row.is-degraded .rd-bind-user { border-color: #fca5a5; }
.rd-bind-url {
  flex: 1; min-width: 0; padding: 5px 8px;
  border: 1px solid #E1E5EB; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-bind-warn { font-size: 11px; color: #b91c1c; white-space: nowrap; }
.rd-empty { margin: 4px 0 0; font-size: 12px; color: #8B93A1; }

/* 基础设置(stepTo / nRuns × parallel) */
.adv-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
@media (max-width: 720px) { .adv-grid { grid-template-columns: 1fr; } }
.adv-field {
  padding: 10px 12px;
  border: 1.5px solid #E1E5EB; border-radius: 10px;
}
.adv-name {
  display: block; font-size: 12px; font-weight: 600; margin-bottom: 6px;
}
.adv-select {
  width: 100%; padding: 6px 8px;
  border: 1px solid #E1E5EB; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.num-row {
  display: flex; align-items: center; gap: 6px;
}
.adv-input {
  width: 100%; padding: 6px 8px;
  border: 1px solid #E1E5EB; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.num-row .adv-input { width: 72px; }
.num-sep { font-size: 11px; color: #8B93A1; }

/* ── 另存为方案(默认方案态)───────────────────────────────── */
.rd-save-row { display: flex; align-items: center; gap: 8px; }
.rd-scheme-name {
  flex: 1; min-width: 0; max-width: 320px; padding: 6px 8px;
  border: 1px solid #E1E5EB; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.rd-save-row .ghost-btn { padding: 6px 12px; font-size: 12px; white-space: nowrap; }

/* ── 自建方案只读概要(spec §7 路径①)──────────────────────── */
.rd-summary {
  border: 1.5px solid #E1E5EB; border-radius: 10px;
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
/* 降级(概要态,spec §9):绑定 alias 已删 — 底色微红 + 警示(与默认态 .is-degraded 同口径) */
.rd-sum-bind.is-degraded { background: #fef2f2; color: #b91c1c; }
.rd-sum-warn { margin-left: 4px; font-family: inherit; }

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
  gap: 12px; flex-wrap: wrap;
  padding: 16px 0 0; margin-top: 8px;
  border-top: 1px solid #E1E5EB;
}
.run-summary { display: flex; gap: 6px; flex-wrap: wrap; }
.summary-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
  background: #E7EFFF; color: #2F6FED;
}
.summary-chip.total { background: #E4F5EA; color: #15803D; }
/* 总量超闸(dispatch 409 too_many_runs)→ 红色警示,confirm 亦被拦 */
.summary-chip.total.over { background: #FEE2E2; color: #DC2626; }
.run-actions { display: flex; gap: 8px; }

.ghost-btn {
  background: transparent; border: 1px solid #E1E5EB; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; color: #5B6472;
  cursor: pointer; transition: all 0.15s;
}
.ghost-btn:hover { background: #F3F5F8; }

.primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: #2F6FED;
  color: #fff; border: none; border-radius: 8px;
  padding: 8px 18px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(47, 111, 237, 0.25);
}
.primary-btn:hover:not(:disabled) { background: #275FD7; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.small { font-size: 11px; }
</style>
