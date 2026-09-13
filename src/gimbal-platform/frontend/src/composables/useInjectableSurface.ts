/**
 * useInjectableSurface —— 判定面的**唯一消费面**(spec 架构收敛 §2.1)。
 *
 * 判定、记忆化、预取时机、死因分组都在这里,**视图只消费**:可注入面 / 断言
 * 目标 / 死判 / 契约在途信号(本文件导出为 `pathsOfStep` / `deadOf` /
 * `pending` / `deadIds` 等)只有这一份派生 —— 视图**不得**各自复刻:同一判据
 * 不许有多种命名,契约在途信号也不许只落在一部分视图里。
 *
 * 取数时机(修 F 的结构成因):**读 / 取分离** —— `ensure()` 是**唯一副作用**,
 * 由宿主在挂载 / 步骤面变化时调用;判定与候选走纯缓存读(面 →
 * `declaredSurfaceFor`,取态 → `declarationsFor`),因此渲染期**零请求**
 * (IS-7 钉住)。纯判定不与网络 I/O 耦合:任何人再造一个
 * "读里带取"的口(内部 `void ensureEndpointFull(eid)`),IS-7 会立刻红。
 *
 * 死因分组(修 C):`dead` 把判死条目分成两组 ——
 *   - `intrinsic`:任何时刻都死(legacy / step-oob / override-no-match,以及
 *     **判定面已给答案**时的 path-unresolvable)。宿主把它无条件并入
 *     `deadEntryIds` ⇒ 契约在途窗口里,真悬空条目照旧禁选(此前
 *     RunDialog 把整个 deadIds 掩空,连不依赖契约的死因一起放行);
 *   - `contractDependent`:仅因**契约未落定(在途)**而暂判 path-unresolvable
 *     的那批(契约到位后可能变活)⇒ 只在契约落定后并入。
 *   `pending` = "还没答案"(任一被引用端点在途)。取数**失败**不是悬置理由
 *   ——失败也是答案:声明面退回 body 面 ⇒ 此时 path-unresolvable 即真死,
 *   归 `intrinsic`(IS-3 钉住)。
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { injectablePathSetOf, registryIssues } from '@/utils/assertion-registry'
import type { RegistryIssue } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { iterFlat, resolveState, toTemplatePath } from '@/utils/declarations'
import type { DeclarationEntryView, FieldState } from '@/types/plate'
import {
  endpointFullState, ensureEndpointFull, getEndpointFull, surfaceVersion,
} from '@/composables/useEndpointFull'

export interface InjectableSurface {
  pathsOfStep(si: number): ReadonlySet<string>
  deadOf(e: AssertionEntry | LegacyAssertionEntry): RegistryIssue[]
  /** 死因分组(spec §2.1):intrinsic 任何时刻都死;contractDependent 仅因契约
   *  **在途**(还没答案)而暂判死 —— 取数失败 ⇒ 从严归 intrinsic */
  dead: ComputedRef<{ intrinsic: string[]; contractDependent: string[] }>
  /** **门控后**的死条目 id 集 = `intrinsic ∪ (pending ? ∅ : contractDependent)`
   *  —— 禁选(RunDialog)与「悬空」标注(数据页 / 断言管理)共用的唯一派生:
   *  同一页里"能不能勾"与"标不标悬空"必须同口径,否则用户在数据页看到
   *  「悬空」、在运行面板看到可勾,正是 C 要消灭的自相矛盾。 */
  deadIds: ComputedRef<string[]>
  stateOf(si: number, path: string): FieldState | undefined
  pending: ComputedRef<boolean>
  /** 换面信号(spec §3.3):**被条目引用**的端点中至少一个在本会话内换过面
   *  (`surfaceVersion` 越过首取的那一版)。换面即重判 —— dead 集合已按新面
   *  重算,因新面而悬空的条目照常进 `deadIds`(悬空标注的唯一口径 ⇒ 灰显)。
   *  **非阻断**:本组合式从不改写 `entries`,勾选状态原样保留,提交也不因它
   *  被拦 —— 已选中的悬空条目交 dispatch 侧既有的 dangling skip 兜底,
   *  不新造失败态。**呈现位**由视图绑定(与其他判定面信号同一处)。 */
  surfaceChanged: ComputedRef<boolean>
  ensure(): void
}

export function useInjectableSurface(
  steps: Ref<any[]>,
  entries: Ref<Array<AssertionEntry | LegacyAssertionEntry>>,
): InjectableSurface {
  /** steps[si] 的契约端点 id(**读,不取数**) */
  function endpointIdOf(si: number): string | undefined {
    const eid = (steps.value[si] as { api?: { view_hints?: { endpoint_id?: string } } } | null)
      ?.api?.view_hints?.endpoint_id
    return typeof eid === 'string' && eid ? eid : undefined
  }

  /* ── 读 / 取分离(C18)─────────────────────────────────────────
   * **读**(本文件的 pathsOfStep / stateOf):纯缓存读,绝不取数 —— 渲染期
   * 只走这里。任何"读里带取"的合体口都不许入读路径:读函数内部若
   * `void ensureEndpointFull(eid)`,读路径经它 = 渲染期发请求。
   * **取**:`ensure()` 显式、幂等,由宿主在挂载 / 步骤面变化时调用,覆盖
   * **全部带 endpoint_id 的步骤** —— 读端不取数 ⇒ 取数必须一次取全,否则
   * "给新条目挑契约字段"这条路径(候选/取态要问任意 si,含无条目引用的 si)
   * 永远没有数据。幂等 + 面 TTL + 负缓存 ⇒ 同一端点在 TTL 内只取一次。 */
  const stepEndpointIds = computed<string[]>(() => {
    const out = new Set<string>()
    for (let si = 0; si < steps.value.length; si++) {
      const eid = endpointIdOf(si)
      if (eid) out.add(eid)
    }
    return [...out]
  })
  function ensure(): void {
    for (const eid of stepEndpointIds.value) void ensureEndpointFull(eid)
  }
  watch(stepEndpointIds, () => ensure(), { immediate: false })

  /* ── 在途面:只为"被条目引用到的步骤"的端点 ──
   * 与预取面**故意不同**:未被引用的端点不可能影响任何条目的死判定(它不进
   * dead 投影),却足以让判定面整体悬置 ⇒ 不进 pending。
   * ⚠ 别"简化"成遍历全部带 endpoint_id 的步骤:那样慢 plate 下一个与条目
   * 无关的端点就能把整个判定面悬置。 */
  const neededEndpoints = computed<string[]>(() => {
    const out = new Set<string>()
    for (const e of entries.value) {
      if (isLegacyEntry(e)) continue
      const si = e.path?.stepIndex
      if (!Number.isInteger(si)) continue
      const eid = endpointIdOf(si)
      if (eid) out.add(eid)
    }
    return [...out]
  })

  /** 契约是否尚未落定:任一被引用端点状态为 'loading' */
  const pending = computed(() =>
    neededEndpoints.value.some((eid) => endpointFullState(eid) === 'loading'))

  /** 本会话内是否换过面:被引用端点里至少一个的面版本越过了首取那一版(1)。
   *  换面**不是**面悬置 —— `pending` 语义不因它改(spec §3.3)。 */
  const surfaceChanged = computed(() =>
    neededEndpoints.value.some((eid) => surfaceVersion(eid) > 1))

  /** 读:纯缓存读,绝不取数(渲染期只走这里)—— 声明**树**(条目 + children),
   *  供 `stateOf` 取条目自身的 state;判定面的声明半不走这里(见下)。 */
  function declarationsFor(si: number): DeclarationEntryView[] | undefined {
    const eid = endpointIdOf(si)
    if (!eid) return undefined
    return getEndpointFull(eid)?.request?.declarations
  }

  /** 读:该步端点的**声明面** —— 后端随 /full 算好的扁平面(归一化 / 容器
   *  前缀 / 模板形态全展开,spec §2.2),归一化在平台侧完成。
   *  `null` / 缺席 = 声明面不可解析(降级)⇒ 可注入面只剩 body 半。 */
  function declaredSurfaceFor(si: number): readonly string[] | null | undefined {
    const eid = endpointIdOf(si)
    if (!eid) return undefined
    return getEndpointFull(eid)?.declared_surface
  }

  /* ── 记忆化:同一 (si, 步骤面版本, 该 si 自身的面版本) 只重建一次 ──
   * 键必须覆盖投影读的**每一个**输入:
   *  · **步骤面版本** = steps 的深变更计数(整表替换 / body 就地编辑);
   *  · **该 si 自身的面版本** = `surfaceVersion(endpointIdOf(si))`
   *    (0 = 尚无面 / 取数失败 —— 判定面只剩 body 面;首取起 1,换面再 +1。
   *    读 `shallowReactive` 容器的条目 ⇒ 本身响应式,契约落定与**换面**
   *    (spec §3.3)都让键变 ⇒ 判定立即按新面重算;面没变的重取版本不动
   *    ⇒ 已算好的投影不被无谓作废)。
   *  ⚠ 键里用**该 si 自己的**面版本,不是"被引用端点的联合版本":
   *  `pathsOfStep(si)` 会被**无条目引用**的 si 调(编辑器 `pendingPath`
   *  给新条目挑字段),那种 si 的端点不在联合版本里 ⇒ 它落定既不改键也不清
   *  缓存,候选集会永久停在 body 面(v3.1 §2.1 放宽服务的那条路径直接失效)。
   *  ⚠ 下面这个 **deep** watch 不是顺手加的、别当冗余删:body 就是被端点集合
   *  漏掉的那一维,删掉 = 重新引入"编辑 body 后判定滞后"的静默缺陷。
   *  开销:每次 steps 深变更多一遍遍历(O(steps)),**不是**每渲染 —— 可接受。 */
  const stepsRev = ref(0)
  watch(steps, () => { stepsRev.value++ }, { deep: true })
  const endpointSurfacesKey = computed(() =>
    stepEndpointIds.value.map((eid) => `${eid}:${surfaceVersion(eid)}`).join('|'))
  const pathsCache = new Map<string, ReadonlySet<string>>()
  watch([stepsRev, endpointSurfacesKey], () => pathsCache.clear())
  function pathsOfStep(si: number): ReadonlySet<string> {
    const eid = endpointIdOf(si)
    const key = `${si}|${stepsRev.value}|${eid ? surfaceVersion(eid) : 0}`
    const hit = pathsCache.get(key)
    if (hit) return hit
    const step = steps.value[si]
    const built = injectablePathSetOf(fieldPathsOf(step as any), declaredSurfaceFor(si))
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
    for (const d of iterFlat(declarationsFor(si))) {
      if (toTemplatePath(d.path) === key) {
        return resolveState(d.path, d.state, step?.field_states)
      }
    }
    return undefined
  }

  return { pathsOfStep, deadOf, dead, deadIds, stateOf, pending, surfaceChanged, ensure }
}
