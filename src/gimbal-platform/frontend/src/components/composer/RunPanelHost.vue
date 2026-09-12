<!--
  RunPanelHost.vue — 运行面板宿主(spec v3 §6)

  两个执行入口共用的装配层:数据集入口(测试数据页「运行」/「运行此行」)
  与场景入口同款 RunDialog,场景加载不绑死 CaseComposer。自取数:
  getScenario(展示名/步数)+ getScenarioDraft(definition/
  orchestration.runSchemes/assertion_registry)+ listDataSets + 凭证池。
  dead 计算与 CaseComposer 同构(可注入面 = body 现存 ∪ 契约声明,spec v3.1 §2.1)。
-->
<template>
  <RunDialog
    :visible="true"
    :scenario="scenario"
    :data-sets="dataSets"
    :running="dispatching"
    :last-run-id="null"
    :last-run-error="lastRunError"
    :schemes="schemes"
    :last-run-overlay="null"
    :service-rows="serviceRows"
    :auth-options="authOptions"
    :step-orchestration-names="stepNames"
    :assertion-entries="registry.entries"
    :dead-entry-ids="deadEntryIds"
    :contract-pending="contractPending"
    :preset="preset"
    @close="emit('close')"
    @confirm="onConfirm"
    @save-scheme="onSaveScheme"
    @delete-scheme="onDeleteScheme"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import RunDialog from './RunDialog.vue'
import {
  getScenario, getScenarioDraft, listDataSets, putRunSchemes, runScenario,
} from '@/api/scenario-composer'
import type {
  DataSetSelection, RunPreset, RunScheme, ServiceBinding,
} from '@/api/scenario-composer'
import type { DataSetSummary, Scenario } from '@/types/scenario-composer'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { injectablePathSetOf, isDeadEntry, normalizeRegistry } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { endpointFullState, requestDeclarationsOf } from '@/composables/useEndpointFull'
import { list as listAuthSessions } from '@/api/auth_sessions'
import { showError } from '@/utils/errorFallback'
import { executionUrl } from '@/utils/links'

const props = defineProps<{
  /** 目标场景(路由级组件 prop,非响应式路由参数 — 宿主页已持有) */
  scenarioId: string
  /** 预填(spec v3 §6):数据集入口(整库/单行)或「加入本次执行」条目 */
  preset?: RunPreset | null
}>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()

const scenario = ref<Scenario | null>(null)
const draft = ref<Awaited<ReturnType<typeof getScenarioDraft>> | null>(null)
const dataSets = ref<DataSetSummary[]>([])
const authAliases = ref<string[]>([])
const schemes = ref<RunScheme[]>([])
const registry = ref<AssertionRegistry>({ entries: [] })
const dispatching = ref(false)
const lastRunError = ref<string | null>(null)

const steps = computed(() => ((draft.value?.definition.steps ?? []) as any[]))
/** 展示名:平台编排态 orchestration.steps[i].name(plate Step 无 name) */
const stepNames = computed(() =>
  ((draft.value?.orchestration as any)?.steps ?? []).map((s: { name?: string }) => s.name ?? ''))
/** 绑定行 = 声明 ∪ 引用并集(spec D3,与 CaseComposer 同构) */
const serviceRows = computed(() => {
  const declared = (draft.value?.definition.config as { services?: Record<string, unknown> } | undefined)?.services ?? {}
  const rows = new Map<string, string | null>()
  for (const [k, v] of Object.entries(declared)) rows.set(k, typeof v === 'string' ? v : null)
  for (const st of steps.value) {
    const svc = (st as { api?: { service?: string } })?.api?.service
    if (svc && !rows.has(svc)) rows.set(svc, null)
  }
  return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
})
/** 凭证选项:owner 凭证池 ∪ 场景内置 users 别名(与 CaseComposer 同构) */
const authOptions = computed(() => {
  const users = Object.keys(
    ((draft.value?.definition.config as any)?.users ?? {}) as Record<string, unknown>)
  return [...new Set([...authAliases.value, ...users])]
})
/** dead 计算(spec v3 §2,与 CaseComposer 同构)。
 *  可注入面(spec v3.1 §2.1):body 现存 ∪ 契约声明(全状态 form/collapse/
 *  carry)。声明面来自共享 /full 缓存 —— 契约未回填时退化为 body 面(从严)。 */
function injectablePathsOfStep(si: number): ReadonlySet<string> {
  const step = steps.value[si]
  return injectablePathSetOf(fieldPathsOf(step as any), requestDeclarationsOf(step))
}
function assertTargetsOf(si: number): ReadonlySet<string> {
  // String(x.target):兑现 ReadonlySet<string> 的类型承诺(裸 x.target 会
  // 把 undefined 塞进 string 集合)。断言 target 在引擎/plate 双侧 schema
  // 均必填,故对合法场景不可达;但四处 dead 投影必须同口径
  // (CaseComposer / CaseDataSetsList / AssertionRegistryEditor 同写法)。
  const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
  return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadEntryIds = computed(() =>
  registry.value.entries
    .filter((e) => isDeadEntry(e, steps.value.length, injectablePathsOfStep, assertTargetsOf))
    .map((e) => e.id))
/** 契约面是否**在途**(spec v3.1 §2.1):任一「被引用且带 endpoint_id」的步骤
 *  尚未回填 /full 声明 ⇒ 此刻的 deadEntryIds 只跑过 body 面,锚在 carry /
 *  未落 body 的 collapse 上的条目会被**误判**成悬空。时序坑:本宿主自取数后
 *  才挂 RunDialog,`/full` 与挂载同 tick 才发起 ⇒ 首判定必然是 body 面
 *  (此前 preset 锚在 carry 的预勾会被静默丢掉,且契约回来后 prop 不变、
 *  RunDialog 的 watch 不重跑 → 永不重放)。交 RunDialog 在 pending 期间
 *  不把「尚未判定」当「判死」。
 *  ensureEndpointFull 幂等:miss 时由 requestDeclarationsOf 发起取数。 */
const contractPending = computed(() => {
  for (const st of steps.value) {
    const eid = (st as { api?: { view_hints?: { endpoint_id?: string } } })?.api?.view_hints?.endpoint_id
    if (!eid) continue
    requestDeclarationsOf(st)
    if (endpointFullState(eid) === 'loading') return true
  }
  return false
})

onMounted(async () => {
  try {
    const [sc, dr, dss] = await Promise.all([
      getScenario(props.scenarioId),
      getScenarioDraft(props.scenarioId),
      listDataSets({ scenarioId: props.scenarioId }),
    ])
    // ⚠ 下面 5 行必须在**同一个同步 tick** 内落完(dataSets / registry /
    // draft 之间不得插 await):RunDialog 的 preset 预填 watch 双源
    // dataSets+registry,预勾靠 defaultSelection 按 dataSets 收窄、按
    // deadEntryIds(由 registry 派生)过滤。中间插一个 await 会让
    // preset 先以空 dataSets/registry 求值一次 → 静默丢掉预勾的条目
    // (「运行此行」/「加入本次执行」看上去没生效)。
    scenario.value = sc
    draft.value = dr
    dataSets.value = dss
    registry.value = normalizeRegistry(dr.assertion_registry)
    schemes.value = ((dr.orchestration as any)?.runSchemes ?? []) as RunScheme[]
  } catch (e) {
    showError('加载运行面板', e)
    return
  }
  try {
    authAliases.value = (await listAuthSessions()).map((s) => s.alias)
  } catch { /* 凭证池不可达不阻塞运行 */ }
})

/** confirm → runScenario(dataSetSelection 权威键)→ 跳执行详情 */
async function onConfirm(
  dataSetSelection: DataSetSelection[],
  opts?: {
    stepTo?: number
    nRuns?: number
    parallel?: number
    serviceBindings?: Record<string, ServiceBinding>
    injectionEntryIds?: string[]
  },
) {
  if (dispatching.value) return
  dispatching.value = true
  lastRunError.value = null
  try {
    const resp = await runScenario({
      scenarioId: props.scenarioId,
      dataSetIds: dataSetSelection.map((s) => s.datasetId),
      ...(dataSetSelection.length ? { dataSetSelection } : {}),
      ...(opts?.stepTo != null ? { stepTo: opts.stepTo } : {}),
      ...(opts?.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
      ...(opts?.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
      ...(opts?.serviceBindings && Object.keys(opts.serviceBindings).length
        ? { serviceBindings: opts.serviceBindings } : {}),
      ...(opts?.injectionEntryIds?.length
        ? { injectionEntryIds: opts.injectionEntryIds } : {}),
    })
    ElMessage.success(`运行已发起: ${resp.runId}`)
    emit('close')
    if (resp.executionId != null) router.push(executionUrl(resp.executionId))
    else router.push('/executions')
  } catch (e) {
    lastRunError.value = (e as Error).message
    showError('运行', e)
  } finally {
    dispatching.value = false
  }
}

/** 存/删方案:整表 PUT(Task 10 窄端点),本地 schemes 同步收缩 */
async function onSaveScheme(scheme: RunScheme) {
  try {
    const next = [...schemes.value.filter((s) => s.name !== scheme.name), scheme]
      .sort((a, b) => a.name.localeCompare(b.name))
    await putRunSchemes(props.scenarioId, next)
    schemes.value = next
    ElMessage.success(`方案「${scheme.name}」已保存`)
  } catch (e) {
    showError('保存方案', e)
  }
}
async function onDeleteScheme(name: string) {
  try {
    const next = schemes.value.filter((s) => s.name !== name)
    await putRunSchemes(props.scenarioId, next)
    schemes.value = next
    ElMessage.success(`方案「${name}」已删除`)
  } catch (e) {
    showError('删除方案', e)
  }
}
</script>
