/**
 * useEndpointFull.ts — plate `/full` 结构契约的**会话级共享缓存**。
 * 共享面 = 判定面(四处悬空投影:编辑器 / CaseComposer / CaseDataSetsList /
 * RunPanelHost)∪ 画布渲染 ∪ useFieldDescriptions 的字段说明。
 * **不是唯一取数口**:`CaseComposerCatalog` 的目录面板直接调
 * `getFullEndpoint`(用户触发的浏览取数,不属判定路径,故不合并)。
 *
 * 抽取自两份同款实现(CaseComposerCanvas 的端点契约缓存、useFieldDescriptions
 * 的字段说明缓存)—— 同一模式留两份副本就会各自漂移,收成一份:
 *
 *   - 每 endpoint 一个会话内恰好一次请求;并发收敛为同一 Promise。
 *   - **会话级**(模块级容器,非 `<script setup>` 实例变量):画布的契约缓存
 *     收编进来时由「每挂载一份」升为「同一 SPA 会话内不再重取」——
 *     plate 中途发版需刷新页面才见新结构(前端缓存**无 TTL**,与后端
 *     `endpoint_declarations` 的 300s TTL 不同;差异方向:前端更粘)。
 *   - 零持久化:缓存只活在本次页面会话(刷新即失效),不落库 / 不落
 *     localStorage —— Plate 始终是结构权威源,平台侧不留结构快照。
 *   - **响应式容器(Vue 原生)**:消费方**读缓存即建立依赖**(Map.get /
 *     Map.has 被 Vue 跟踪),回填后 computed 自动重算 —— 旧的
 *     「手工版本号 + `void x.value`」协议已退役:
 *     那套协议要每个消费方在每处 computed 里手写声明,漏一处即静默不重算。
 *   - **失败负缓存**:失败记 `failedAt`,窗口 `FAILED_RETRY_MS` 内不再发起
 *     (plate 故障时渲染路径不再反复重发),窗口过后允许重试。
 *   - **入口消毒(Ruling C7)**:`/full` 是不可信来源,入缓存时**一次**
 *     `sanitizeDeclarations` ⇒ 所有消费方(画布 `buildNode`/`suffixOf`、
 *     编辑器、后续 composable)拿到的**按构造就是干净的**,且零逐调用开销。
 *     此前「路径可用性守卫」在 iterFlat → buildTree → buildNode →
 *     prefillBindings 上逐个冒出来 —— 边界选错了;守卫只该有一个。
 *
 * 消费方约定:直接在 computed 里读 `getEndpointFull` / `endpointFullState` /
 * `requestDeclarationsOf` 即建立响应依赖;需要取数时调
 * `ensureEndpointFull(eid)`(幂等)。
 */
import { reactive, shallowReactive } from 'vue'

import { getFullEndpoint } from '@/api/scenario-composer'
import { hasUsablePath } from '@/utils/declarations'
import type { DeclarationEntryView, EndpointFullView } from '@/types/plate'

/** 失败重试窗口(ms):窗口内不再发起,避免 plate 故障时渲染路径反复重发。 */
export const FAILED_RETRY_MS = 10_000

/** 会话级缓存 —— Vue 原生响应式容器。**shallow**:只跟踪「哪个 endpoint 有
 *  条目」,不回填值身份 ⇒ 读回的是 `EndpointFullView` 本体而非 deep Proxy
 *  (EF-1 的 `toBe` 身份断言与画布渲染热路径都依赖这一点;声明树每次渲染会被
 *  `buildTree` 全量遍历,deep Proxy 的逐属性代理是白付的开销 —— 缓存条目
 *  是 API 快照,只有「入缓存」这一个变更事件,shallow 正是该语义)。 */
const fullByEndpoint = shallowReactive(new Map<string, EndpointFullView>())
/** 进行中的请求(同 endpoint 并发收敛为同一 Promise) */
const inFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** eid → 失败时刻(ms);**负缓存**:窗口内不重发。值为标量,deep reactive 无副作用。 */
const failedAt = reactive(new Map<string, number>())

/**
 * 声明树入口消毒(**纯函数**,不改入参):路径不可用(`path: 7` / `path: ''`,
 * 判据 = `hasUsablePath` 唯一定义)的条目**自身剔除、children 提升**到原位置
 * (children 为数组且非空时拼接;非数组则直接丢弃)—— 与 `iterFlat` 逐字同纪律,
 * **绝不整棵剪枝**(容器缺 path 时整棵剪掉会让子孙从树里消失 = 语义丢失)。
 *
 * 递归下钻到可用条目的 children:画布 `buildNode` 的递归下降只认
 * `entry.children`,故子孙也必须在入缓存时一并干净。可用条目的 children
 * 未被改动时**原对象原样返回**(不造新对象/新数组),保证对干净入参零扰动
 * ——画布/编辑器的既有身份与浅比较语义不变。
 */
export function sanitizeDeclarations(
  decls: DeclarationEntryView[] | undefined | null,
): DeclarationEntryView[] {
  const out: DeclarationEntryView[] = []
  for (const e of decls ?? []) {
    if (!e || typeof e !== 'object') continue
    const kids = (e as { children?: unknown }).children
    const cleaned = Array.isArray(kids)
      ? sanitizeDeclarations(kids as DeclarationEntryView[])
      : undefined
    if (!hasUsablePath(e)) {
      // 自身不可用:剔除自身,children 提升到原位置(非数组/空 → 丢弃)
      if (cleaned?.length) out.push(...cleaned)
      continue
    }
    if (!Array.isArray(kids) || isSameRefs(kids, cleaned!)) { out.push(e); continue }
    out.push({ ...e, children: cleaned })
  }
  return out
}

/** cleaned 与 raw 逐位同一引用(消毒对该层无改动)⇒ 保留原条目对象。 */
function isSameRefs(raw: unknown[], cleaned: DeclarationEntryView[]): boolean {
  return cleaned.length === raw.length && cleaned.every((c, i) => c === raw[i])
}

/** `/full` → 消毒后的 `/full`;request.declarations 无改动时**原对象原样返回**。 */
function sanitizeFull(full: EndpointFullView): EndpointFullView {
  const decls = full?.request?.declarations
  if (!Array.isArray(decls)) return full
  const clean = sanitizeDeclarations(decls)
  if (clean.length === decls.length && clean.every((d, i) => d === decls[i])) return full
  return { ...full, request: { ...full.request!, declarations: clean } }
}

/** 缓存 miss 时拉 /full、**入口消毒**并回填(fail-soft);
 *  命中缓存 / 负缓存窗口内 / 在飞 → 直接返回。 */
export function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const cached = fullByEndpoint.get(endpointId)
  if (cached) return Promise.resolve(cached)
  const at = failedAt.get(endpointId)
  if (at !== undefined && Date.now() - at < FAILED_RETRY_MS) {
    return Promise.resolve(undefined)          // 负缓存命中:窗口内不重发
  }
  const pending = inFlight.get(endpointId)
  if (pending) return pending
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      const clean = sanitizeFull(full)
      fullByEndpoint.set(endpointId, clean)
      failedAt.delete(endpointId)
      return clean
    })
    .catch(() => {
      failedAt.set(endpointId, Date.now())     // 负缓存:窗口内不再发起
      return undefined
    })
    .finally(() => inFlight.delete(endpointId))
  inFlight.set(endpointId, p)
  return p
}

/** 同步读缓存(未拉取/失败 → undefined);调用方自行 ensure */
export function getEndpointFull(endpointId: string): EndpointFullView | undefined {
  return fullByEndpoint.get(endpointId)
}

/** 端点级拉取状态:已缓存 = ''、失败(负缓存窗口内)= 'failed'、其余(未回填)= 'loading' */
export function endpointFullState(endpointId: string | undefined): 'loading' | 'failed' | '' {
  if (!endpointId) return ''
  if (fullByEndpoint.has(endpointId)) return ''
  return failedAt.has(endpointId) ? 'failed' : 'loading'
}

/** 步骤的契约声明面(读共享缓存;未拉取则发起)。上层投影用。
 *  无 endpoint_id / 未回填 → undefined(调用方降级为「只认 body 面」)。
 *  返回的即**入口消毒后**的树 ⇒ 消费方(含画布 `buildTree`)零守卫。 */
export function requestDeclarationsOf(step: unknown): DeclarationEntryView[] | undefined {
  const eid = (step as { api?: { view_hints?: { endpoint_id?: string } } } | null | undefined)
    ?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return getEndpointFull(eid)?.request?.declarations
}

/** 测试钩子:清空缓存(含负缓存)。仅供单测使用。 */
export function _resetEndpointFullCacheForTest() {
  fullByEndpoint.clear()
  inFlight.clear()
  failedAt.clear()
}
