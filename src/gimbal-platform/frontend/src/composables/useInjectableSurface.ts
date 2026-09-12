/**
 * useInjectableSurface —— 判定面的**唯一消费面**(spec 架构收敛 §2.1)。
 *
 * 收敛前:四个视图各自定义 injectablePathsOfStep / assertTargetsOf / deadOf /
 * contractPending(四份副本,且已在同一波内漂移)。收敛后:判定、记忆化、
 * 预取时机、死因分组都在这里,**视图只消费**。
 *
 * 取数时机(修 F 的结构成因):`ensure()` 是**显式副作用**,由宿主在挂载 /
 * 步骤变化时调用;渲染期只读缓存 —— 纯判定不再与网络 I/O 耦合。
 *
 * 死因分组(修 C):`dead` 把判死条目分成两组 ——
 *   - `intrinsic`:任何时刻都死(legacy / step-oob / override-no-match,以及
 *     **判定面已给答案**时的 path-unresolvable)。宿主把它无条件并入
 *     `deadEntryIds` ⇒ 契约在途窗口里,真悬空条目照旧禁选(此前
 *     RunDialog 把整个 deadIds 掩空,连不依赖契约的死因一起放行);
 *   - `contractDependent`:仅因**契约未落定**而暂判 path-unresolvable 的那批
 *     (契约到位后可能变活)⇒ 只在契约落定后并入。
 *   `pending` = "还没答案"(任一被引用端点在途);`failed` = "答案拿不到"
 *   ⇒ 判定**从严**(声明面退回 body 面),此时 path-unresolvable 即真死,
 *   归 `intrinsic` 而**不悬置**。
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { injectablePathSetOf, registryIssues } from '@/utils/assertion-registry'
import type { RegistryIssue } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { iterFlat, resolveState, toTemplatePath } from '@/utils/declarations'
import type { FieldState } from '@/types/plate'
import {
  endpointFullState, ensureEndpointFull, getEndpointFull, requestDeclarationsOf,
} from '@/composables/useEndpointFull'

export interface InjectableSurface {
  pathsOfStep(si: number): ReadonlySet<string>
  deadOf(e: AssertionEntry | LegacyAssertionEntry): RegistryIssue[]
  /** 死因分组(spec §2.1):intrinsic 任何时刻都死;contractDependent 仅因契约未定/取数失败而判死 */
  dead: ComputedRef<{ intrinsic: string[]; contractDependent: string[] }>
  /** **门控后**的死条目 id 集 = `intrinsic ∪ (pending ? ∅ : contractDependent)`
   *  —— 禁选(RunDialog)与「悬空」标注(数据页 / 断言管理)共用的唯一派生:
   *  同一页里"能不能勾"与"标不标悬空"必须同口径,否则用户在数据页看到
   *  「悬空」、在运行面板看到可勾,正是 C 要消灭的自相矛盾。 */
  deadIds: ComputedRef<string[]>
  stateOf(si: number, path: string): FieldState | undefined
  pending: ComputedRef<boolean>
  ensure(): void
}

export function useInjectableSurface(
  steps: Ref<any[]>,
  entries: Ref<Array<AssertionEntry | LegacyAssertionEntry>>,
): InjectableSurface {
  /* ── 预取:只为"被条目引用到的步骤"的 endpoint 取数(显式副作用) ──
   * 未被任何条目引用的端点,其契约状态不可能影响 dead 判定 ⇒ 不进在途面
   * (旧的四份 contractPending 遍历全部带 endpoint_id 的步骤,慢 plate 下
   * 一个无关端点就能把判定面整个悬置)。 */
  const neededEndpoints = computed<string[]>(() => {
    const out = new Set<string>()
    for (const e of entries.value) {
      if (isLegacyEntry(e)) continue
      const si = e.path?.stepIndex
      if (!Number.isInteger(si)) continue
      const eid = steps.value[si]?.api?.view_hints?.endpoint_id
      if (typeof eid === 'string' && eid) out.add(eid)
    }
    return [...out]
  })
  function ensure(): void {
    for (const eid of neededEndpoints.value) void ensureEndpointFull(eid)
  }
  watch(neededEndpoints, () => ensure(), { immediate: false })

  /** 契约是否尚未落定:任一被引用端点状态为 'loading' */
  const pending = computed(() =>
    neededEndpoints.value.some((eid) => endpointFullState(eid) === 'loading'))

  /* ── 记忆化:同一 (si, 步骤面版本, 契约版本) 只重建一次 ──
   * 投影 = body 现状 × 契约声明,两维都得进键:
   *  · **契约版本** = 每个被引用端点的取数态(缓存命中 = 'v',否则 loading/
   *    failed)。契约回填 / 失败 / 负缓存重试都改版本 —— 只按 si 缓存而靠
   *    「端点集合变化」来清会在**契约落定**这条主路径上失效(集合没变,
   *    变的只是它的答案);
   *  · **步骤面版本** = steps 的深变更计数(整表替换 / body 就地编辑)。
   *    光靠端点集合的整表替换只能顺带清掉一部分:它只跟踪 view_hints,
   *    不跟踪 body —— 就地删一个字段时不重算,旧集合会被一直复用,
   *    判活判死静默漂移(IS-5 钉住)。
   *  ⚠ 下面这个 **deep** watch 不是顺手加的、别当冗余删:键必须覆盖投影读的
   *  每一个输入(body 就是被 neededEndpoints 漏掉的那一维)。删掉它 = 重新
   *  引入"编辑 body 后判定滞后"的静默缺陷(副本时代不存在,因为那时无缓存)。
   *  开销:每次 steps 深变更多一遍遍历(O(steps)),**不是**每渲染 —— 可接受。 */
  const stepsRev = ref(0)
  watch(steps, () => { stepsRev.value++ }, { deep: true })
  const contractVersion = computed(() =>
    neededEndpoints.value
      .map((eid) => `${eid}:${getEndpointFull(eid) ? 'v' : endpointFullState(eid)}`)
      .join('|'))
  const pathsCache = new Map<string, ReadonlySet<string>>()
  watch([stepsRev, contractVersion], () => pathsCache.clear())
  function pathsOfStep(si: number): ReadonlySet<string> {
    const key = `${si}|${stepsRev.value}|${contractVersion.value}`
    const hit = pathsCache.get(key)
    if (hit) return hit
    const step = steps.value[si]
    const built = injectablePathSetOf(fieldPathsOf(step as any), requestDeclarationsOf(step))
    pathsCache.set(key, built)
    return built
  }
  function assertTargetsOf(si: number): ReadonlySet<string> {
    const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
    return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)));
  }

  function deadOf(e: AssertionEntry | LegacyAssertionEntry): RegistryIssue[] {
    return registryIssues(e, steps.value.length, pathsOfStep, assertTargetsOf)
  }

  const dead = computed(() => {
    const intrinsic: string[] = []
    const contractDependent: string[] = []
    for (const e of entries.value) {
      const issues = deadOf(e)
      if (!issues.length) continue
      // 判据(spec §2.1):**契约未定**时,只有"全部 issue 都是 path-unresolvable"
      // 的条目可悬置(它可能在契约到位后变活);契约**取数失败**时判定从严
      // (faces 已退回 body 面),此时 path-unresolvable 即真死 ⇒ 归 intrinsic。
      const suspended = pending.value && issues.every((i) => i.kind === 'path-unresolvable')
      ;(suspended ? contractDependent : intrinsic).push(e.id)
    }
    return { intrinsic, contractDependent }
  })

  /** 门控后的死集(唯一派生):契约**在途**时只有 intrinsic 算死 ——
   *  contractDependent 是"还没答案",不是"判死"(spec §2.1)。
   *  宿主传给 RunDialog 的 deadEntryIds 与各视图的「悬空」标注都读这一份,
   *  掩空决策**没有第二个落点**,不可能再分叉。 */
  const deadIds = computed<string[]>(() => [
    ...dead.value.intrinsic,
    ...(pending.value ? [] : dead.value.contractDependent),
  ])

  /** 提示行的字段状态标注(原编辑器 stateOfPendingPath 的实现搬入并**显式按步**)。
   *  `si` 必填:编辑器候选来自"当前待选步骤",调用方(编辑器)手里就有该下标。 */
  function stateOf(si: number, path: string): FieldState | undefined {
    const step = steps.value[si] as any
    const key = toTemplatePath(path)
    for (const d of iterFlat(requestDeclarationsOf(step))) {
      if (toTemplatePath(d.path) === key) {
        return resolveState(d.path, d.state, step?.field_states)
      }
    }
    return undefined
  }

  return { pathsOfStep, deadOf, dead, deadIds, stateOf, pending, ensure }
}
