/**
 * useRunAssembly —— 执行装配的**唯一公共体**(执行设计 §1.5)。
 *
 * CaseComposer / SchemeWorkbench / 执行器(/run)此前各持一份装配副本:
 * RunPanelHost(已无消费方,死代码)、CaseComposer 内联装配、
 * SchemeWorkbench 的派生镜像。本组合式收编公共部分 —— 4 路并行取数、
 * serviceRows / stepNames 派生、dispatch 段、另存后重取;
 * 失效判定**只消费** useInjectableSurface(掩空决策没有第二个落点,
 * 本文件不复算)。
 *
 * 边界(§1.5 两条划清):
 * - 显式绑定 / 降级 / 总量闸三个纯函数在 utils/run-bindings.ts,不进这里
 *   (避免 composable 变成既装配又判定的混合体);
 * - CaseComposer 专属四段(saveDraft 先落盘、800ms 导航延时、未保存新用例
 *   守卫、initialSchemeId 深链)留作调用方逻辑,不收编。
 *
 * authz M2a S6 后绑定语义 = 「服务键 → 别名」,凭证池(authOptions)派生
 * 随 URL/credential 绑定退役一并删除 — 别名候选/降级由 RunConfigPanel /
 * SchemeRunConfigSection 自取注册表判定,装配体不再取凭证池。
 *
 * 时序坑(从 RunPanelHost 搬进来的唯一一条):load() 里 dataSets / draft /
 * schemes 的赋值必须在**同一个同步 tick** 内落完,中间插一个 await 会让
 * 消费方在一个不完整的判定面上先求值一次,活着的方案闪现「已失效」。
 * 另存后整表替换会重置默认态绑定 = 已知 deferred 行为,
 * 不登记在 DEFERRED.md,别去那份清单找依据。
 */
import { computed, ref, type Ref } from 'vue'
import {
  createRunScheme, getScenario, getScenarioDraft, listDataSets,
  listRunSchemes, runScenario,
  type DataSetSelection, type RunScenarioResult, type RunRequest,
  type SchemeV2, type ServiceBinding,
} from '@/api/scenario-composer'
import type { DebugSpec, RunOptions } from '@/types/m2'
import type { DataSetSummary, Scenario, ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { normalizeRegistry } from '@/utils/assertion-registry'
import { useInjectableSurface } from '@/composables/useInjectableSurface'
import { stepService } from '@/types/plate'

/** confirm 上送形状(RunDialog 面板 emit 的 opts,与 RunRequest 对齐) */
export interface RunConfirmOpts {
  schemeId: string
  schemeName: string
  stepTo?: number
  nRuns?: number
  parallel?: number
  serviceBindings?: Record<string, ServiceBinding>
  injectionEntryIds?: string[]
  /** authz M2a S2:本次执行环境(缺省 = 按链路解析) */
  environmentId?: number
  /** C6:调试执行装载(单 case 且 nRuns=1;发起后进调试台) */
  debug?: Pick<DebugSpec, 'pause' | 'breakpoints'>
  /** authz M2a S8:'project' = 场景所属普通项目的项目凭证池 */
  credentialSource?: 'personal' | 'project'
}

export function useRunAssembly(scenarioId: Ref<string | null | undefined>) {
  // ── 取数落点 ─────────────────────────────────────────────────
  const scenario = ref<Scenario | null>(null)
  const draft = ref<ScenarioDraft | null>(null)
  const dataSets = ref<DataSetSummary[]>([])
  const schemes = ref<SchemeV2[]>([])
  const registry = ref<AssertionRegistry>({ entries: [] })
  const loading = ref(false)
  const loaded = ref(false)
  const loadError = ref<string | null>(null)

  const steps = computed(() =>
    ((draft.value?.definition?.steps ?? []) as Array<Record<string, unknown>>))

  // ── 判定面:唯一消费面,本组合式不复算死集 ────────────────────
  const surface = useInjectableSurface(
    steps as Ref<any[]>,
    computed(() => registry.value.entries),
  )

  // ── 派生(与退役的 RunPanelHost / CaseComposer 副本同式)────────
  /** 绑定行 = 声明 ∪ 引用并集(spec D3):声明行带 declaredUrl,
   * 引用未声明的键 declaredUrl=null(面板标红可救燃)。 */
  const serviceRows = computed(() => {
    const declared = (draft.value?.definition?.config as
      { services?: Record<string, unknown> } | undefined)?.services ?? {}
    const rows = new Map<string, string | null>()
    for (const [k, v] of Object.entries(declared))
      rows.set(k, typeof v === 'string' ? v : null)
    for (const st of steps.value) {
      const svc = stepService(st)
      if (svc && !rows.has(svc)) rows.set(svc, null)
    }
    return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
  })

  /** 绑定下拉选项(owner 凭证池 ∪ 场景内置 users)已随 authz M2a S6 绑定
   *  瘦身退役 — 绑定选注册表别名,不再选凭证;别名候选/降级判定见
   *  utils/run-bindings.aliasCandidates / degradedAlias(面板自取注册表)。 */

  /** stepTo 下拉展示名:平台编排态 orchestration.steps[].name(plate 无 name) */
  const stepNames = computed<string[]>(() =>
    ((draft.value?.orchestration as { steps?: { name?: string }[] } | undefined)
      ?.steps ?? []).map((s) => s.name ?? ''))
  const stepCount = computed(() =>
    scenario.value?.stepCount ?? steps.value.length)

  // ── 取数(时序坑见文件头)─────────────────────────────────────
  async function load(): Promise<boolean> {
    const sid = scenarioId.value
    if (!sid || sid === 'new') return false
    loading.value = true
    loadError.value = null
    try {
      const [sc, dr, dss, schemesList] = await Promise.all([
        getScenario(sid),
        getScenarioDraft(sid),
        listDataSets({ scenarioId: sid }),
        listRunSchemes(sid),
      ])
      // ⚠ 以下赋值必须同一个同步 tick 落完(不得插 await):消费方的自建
      // 方案失效判定同时读 dataSets 与 deadIds(由 registry 派生),中间插
      // await 会让方案在不完整的判定面上先求值一次 → 活方案闪现「已失效」。
      scenario.value = sc
      draft.value = dr
      dataSets.value = dss
      registry.value = normalizeRegistry(dr.assertion_registry)
      schemes.value = schemesList
      loaded.value = true
    } catch (e) {
      loadError.value = e instanceof Error ? e.message : String(e)
      return false
    } finally {
      loading.value = false
    }
    return true
  }

  /** 方案表重取(另存成功后整表替换;新数组引用 → 面板绑定 watch 重置
   * 默认态绑定 = 已知 deferred 行为,接受)。 */
  async function refreshSchemes(): Promise<void> {
    const sid = scenarioId.value
    if (!sid || sid === 'new') return
    schemes.value = await listRunSchemes(sid)
  }

  /** 另存为方案(仅默认方案态):POST create(重名 409 等)→ 重取整表替换。
   * 异常原样抛出 — 各消费方的错误呈现不同(RunDialog 面板保留输入重试)。 */
  async function saveAsScheme(body: Omit<SchemeV2, 'schemeId' | 'isDefault'>): Promise<boolean> {
    const sid = scenarioId.value
    if (!sid) return false
    await createRunScheme(sid, body)
    await refreshSchemes()
    return true
  }

  /** dispatch 段:confirm 载荷 → RunRequest(dataSetIds 派生 + dataSetSelection
   * 权威键 + 溯源两键恒带;退役键 prefix/mergePolicy/auths/injectCredentials
   * 不出现)。网络/4xx 异常原样抛给调用方(各自的错误呈现不同)。 */
  async function dispatch(
    dataSetSelection: DataSetSelection[],
    opts: RunConfirmOpts,
  ): Promise<RunScenarioResult> {
    const sid = scenarioId.value
    if (!sid) throw new Error('scenarioId is not set')
    // W19:执行参数收进 runOptions(M2 生成物形状,内层 snake_case;
    // 全默认时不带键)
    const ro: RunOptions = {}
    if (opts.stepTo != null) ro.step_to = opts.stepTo
    if (opts.nRuns && opts.nRuns !== 1) ro.n_runs = opts.nRuns
    if (opts.parallel && opts.parallel !== 1) ro.parallel = opts.parallel
    if (opts.debug) ro.debug = opts.debug
    const body: RunRequest = {
      scenarioId: sid,
      schemeId: opts.schemeId,
      schemeName: opts.schemeName,
      dataSetIds: dataSetSelection.map((s) => s.datasetId),
      ...(dataSetSelection.length ? { dataSetSelection } : {}),
      ...(Object.keys(ro).length ? { runOptions: ro } : {}),
      ...(opts.serviceBindings && Object.keys(opts.serviceBindings).length
        ? { serviceBindings: opts.serviceBindings } : {}),
      ...(opts.injectionEntryIds?.length
        ? { injectionEntryIds: opts.injectionEntryIds } : {}),
      ...(opts.environmentId ? { environmentId: opts.environmentId } : {}),
      ...(opts.credentialSource === 'project'
        ? { credentialSource: 'project' } : {}),
    }
    return runScenario(body)
  }

  return {
    // 状态
    scenario, draft, dataSets, schemes, registry,
    loading, loaded, loadError,
    // 派生
    serviceRows, stepNames, stepCount, steps,
    surface,
    // 动作
    load, refreshSchemes, saveAsScheme, dispatch,
  }
}
