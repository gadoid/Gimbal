<!--
  RunPanelHost.vue — 运行面板宿主(方案工作台阶段③,spec 2026-09-15 §7)

  两个执行入口共用的装配层:数据集入口(测试数据页卡片「运行」/数据集编辑器行级「运行」)
  与场景入口同款 RunDialog,场景加载不绑死 CaseComposer。自取数:
  getScenario(展示名/步数)+ getScenarioDraft(definition/
  assertion_registry)+ listDataSets + listRunSchemes(V2 直连新 CRUD,
  不经 draft 侧)+ 凭证池。另存为方案走 createRunScheme(POST)后重取;
  overlay 与 preset 链路已随 RunDialog v2 退役。
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
    :service-rows="serviceRows"
    :auth-options="authOptions"
    :step-orchestration-names="stepNames"
    :assertion-entries="registry.entries"
    :dead-entry-ids="deadEntryIds"
    @close="emit('close')"
    @confirm="onConfirm"
    @save-as-scheme="onSaveAsScheme"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import RunDialog from './RunDialog.vue'
import {
  createRunScheme, getScenario, getScenarioDraft, listDataSets, listRunSchemes,
  runScenario,
} from '@/api/scenario-composer'
import type {
  DataSetSelection, SchemeV2, ServiceBinding,
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
}>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()

const scenario = ref<Scenario | null>(null)
const draft = ref<Awaited<ReturnType<typeof getScenarioDraft>> | null>(null)
const dataSets = ref<DataSetSummary[]>([])
const authAliases = ref<string[]>([])
const schemes = ref<SchemeV2[]>([])
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
 *  deadEntryIds(而非在消费侧掩空)—— 锚定契约依赖条目的自建方案才不会
 *  在窗口内误报失效(契约回来后 prop 变化,消费侧的失效判定自然重算)。 */
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())
/** 当前生效的死条目 = composable 的**门控后死集**(intrinsic ∪ 落定后的
 *  contractDependent):契约在途时 contractDependent 不判死(可能变活),
 *  intrinsic 恒判死(step-oob / legacy / override-no-match 不依赖判定面)。
 *  直接取 surface.deadIds —— 掩空决策**没有第二个落点**,展示面同这一份。
 *  (阶段③ v2 消费面 = RunDialog 自建方案失效判定:injectionEntryIds 悬空
 *  ⇒ 方案「配置已失效 — 不可运行」;pending 误判死会让活着方案误报失效。) */
const deadEntryIds = surface.deadIds

onMounted(async () => {
  try {
    const [sc, dr, dss, schemesList] = await Promise.all([
      getScenario(props.scenarioId),
      getScenarioDraft(props.scenarioId),
      listDataSets({ scenarioId: props.scenarioId }),
      listRunSchemes(props.scenarioId),
    ])
    // ⚠ 下面的赋值必须在**同一个同步 tick** 内落完(dataSets / registry /
    // schemes 之间不得插 await):RunDialog 的自建方案失效判定同时读
    // dataSets 与 deadEntryIds(由 registry 派生),中间插一个 await 会让
    // 方案在一个不完整的判定面上先求值一次 → 活着方案闪现「已失效」。
    scenario.value = sc
    draft.value = dr
    dataSets.value = dss
    registry.value = normalizeRegistry(dr.assertion_registry)
    schemes.value = schemesList
  } catch (e) {
    showError('加载运行面板', e)
    return
  }
  try {
    authAliases.value = (await listAuthSessions()).map((s) => s.alias)
  } catch { /* 凭证池不可达不阻塞运行 */ }
})

/** confirm → runScenario(dataSetSelection 权威键 + 溯源两键)→ 跳执行详情 */
async function onConfirm(
  dataSetSelection: DataSetSelection[],
  opts: {
    /** 溯源:本次执行按哪个方案发起(默认/自建两态都带) */
    schemeId: string
    schemeName: string
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
      schemeId: opts.schemeId,
      schemeName: opts.schemeName,
      dataSetIds: dataSetSelection.map((s) => s.datasetId),
      ...(dataSetSelection.length ? { dataSetSelection } : {}),
      ...(opts.stepTo != null ? { stepTo: opts.stepTo } : {}),
      ...(opts.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
      ...(opts.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
      ...(opts.serviceBindings && Object.keys(opts.serviceBindings).length
        ? { serviceBindings: opts.serviceBindings } : {}),
      ...(opts.injectionEntryIds?.length
        ? { injectionEntryIds: opts.injectionEntryIds } : {}),
    })
    toast.success(`运行已发起: ${resp.runId}`)
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

/** 另存为方案(仅默认方案态):POST createRunScheme(重名 409)→ 成功后
 *  重取 schemes 整表替换传给 RunDialog(新数组引用 → 其绑定 watch 重置
 *  默认态绑定 = 已知 deferred 行为,接受);失败弹错不关弹窗,可重试。 */
async function onSaveAsScheme(body: Omit<SchemeV2, 'schemeId' | 'isDefault'>) {
  try {
    await createRunScheme(props.scenarioId, body)
    schemes.value = await listRunSchemes(props.scenarioId)
    toast.success(`方案「${body.name}」已另存`)
  } catch (e) {
    showError('另存为方案', e)
  }
}
</script>
