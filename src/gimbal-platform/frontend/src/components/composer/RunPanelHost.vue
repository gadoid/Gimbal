<!--
  RunPanelHost.vue — 运行面板宿主(spec v3 §6)

  两个执行入口共用的装配层:数据集入口(测试数据页「运行」/「运行此行」)
  与场景入口同款 RunDialog,场景加载不绑死 CaseComposer。自取数:
  getScenario(展示名/步数)+ getScenarioDraft(definition/
  orchestration.runSchemes/assertion_registry)+ listDataSets + 凭证池。
  dead 计算与 CaseComposer 同构(bodyPathSetOf(fieldPathsOf)维度)。
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
import { bodyPathSetOf, isDeadEntry, normalizeRegistry } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
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
/** dead 计算(spec v3 §2,与 CaseComposer 同构):body 字段树维度 */
function bodyPathsOfStep(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
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
    .filter((e) => isDeadEntry(e, steps.value.length, bodyPathsOfStep, assertTargetsOf))
    .map((e) => e.id))

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
