<!--
  RunPanelHost.vue — 运行面板宿主(spec v3 §6)

  两个执行入口共用的装配层:数据集入口(测试数据页「运行」/「运行此行」)
  与场景入口同款 RunDialog,场景加载不绑死 CaseComposer。自取数:
  getScenario(展示名/步数)+ getScenarioDraft(definition/
  orchestration.runSchemes/assertion_registry)+ listDataSets + 凭证池。
  判定面消费 useInjectableSurface(唯一消费面,spec 架构收敛 §2.1);
  掩空决策(契约在途时「尚未判定」≠「判死」)由本宿主做并传给 RunDialog。
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
    :contract-degraded="contractDegraded"
    :preset="preset"
    @close="emit('close')"
    @retry-contract="surface.ensure({ force: true })"
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
import { normalizeRegistry } from '@/utils/assertion-registry'
import { useInjectableSurface } from '@/composables/useInjectableSurface'
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
/** 判定面(spec 架构收敛 §2.1):可注入面 / 悬空判定 / 死因分组 / 契约在途
 *  信号全部收在 useInjectableSurface —— 本宿主**只消费,不持有副本**(复刻
 *  一份即与编辑器/数据页的判据漂移)。
 *  时序坑仍在:本宿主自取数后才挂 RunDialog,`/full` 与挂载同 tick 才发起
 *  ⇒ 首判定只有 body 面;契约在途时 contractDependent 那批**不并入**
 *  deadEntryIds(而非在 RunDialog 侧掩空),preset 锚在 carry 的预勾才不会被
 *  静默丢掉(契约回来后 prop 变化,RunDialog 的收窄 watch 自然重跑)。 */
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())
/** 契约面在途(spec v3.1 §2.1)= 被条目引用的端点尚未回填 —— 传给 RunDialog 的
 *  信号与 deadEntryIds 的掩空决策**同源**,两者必须同步。 */
const contractPending = computed(() => surface.pending.value)
/** 契约面**降级**(被引用端点取数失败)= 悬空条目此刻从严判定(不可勾选)。
 *  与 deadEntryIds 同源,一起传给 RunDialog:那里正是用户看见「条目灰着、点不动」
 *  的地方,提示与重试入口必须在那儿,不能只留在编辑器/画布。 */
const contractDegraded = computed(() => surface.degraded.value)
/** 当前生效的死条目 = composable 的**门控后死集**(intrinsic ∪ 落定后的
 *  contractDependent):契约在途时 contractDependent 不判死(可能变活),
 *  intrinsic 恒判死(step-oob / legacy / override-no-match 不依赖判定面)。
 *  直接取 surface.deadIds —— 掩空决策**没有第二个落点**,展示面同这一份。 */
const deadEntryIds = surface.deadIds

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
