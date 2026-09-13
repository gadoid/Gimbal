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
 *   - 每 endpoint 一次取数;并发收敛为同一 Promise。面有 **`FULL_TTL_MS`
 *     (300s)有效期**,与后端 `endpoint_declarations` 同量级 ⇒ 到期重取,
 *     plate 中途发版后编辑器判定与 dispatch 判定各自在 ~5 分钟内收敛到同一面。
 *   - **读 / 取各管一头**:TTL 只由取数口 `ensureEndpointFull` 把守;读口
 *     `getEndpointFull` 不看 TTL,过期也照样返回缓存里那份 —— 重取期间 UI
 *     不闪空,重取失败时旧面继续服务(与后端 D 的 fail-open-to-old 同向)。
 *   - **换面可观测**:`surfaceVersion(eid)` 只在取回的内容真变时自增 ⇒ 消费方
 *     拿它做记忆化键,换面即重判;内容相同的重取不自增,不惊动已算好的投影。
 *   - **会话级**(模块级容器,非 `<script setup>` 实例变量):画布的契约缓存
 *     收编进来时由「每挂载一份」升为「同一 SPA 会话内共用一份」。
 *   - 零持久化:缓存只活在本次页面会话(刷新即失效),不落库 / 不落
 *     localStorage —— Plate 始终是结构权威源,平台侧不留结构快照。
 *   - **响应式容器(Vue 原生)**:消费方**读缓存即建立依赖**(Map.get /
 *     Map.has 被 Vue 跟踪),回填后 computed 自动重算。消费方**不需要**任何
 *     手工版本号或「读一下让它失效」的声明 —— 手工协议要求每个消费方在每处
 *     computed 里手写,漏一处即静默不重算(本容器不欠这份债)。
 *   - **失败负缓存**:失败记 `failedAt`,窗口 `FAILED_RETRY_MS` 内不再发起
 *     (plate 故障时不反复重发),窗口过后允许重试。
 *     **优先于 TTL**:面到期不足以让一个刚失败的端点重发。
 *   - **消毒(Ruling C7/C8b/C9)**:`/full` 是不可信来源。消毒上移到
 *     `getFullEndpoint` **出口**(`sanitizeEndpointFull`,request + 每个 response;
 *     含不经本缓存的 `CaseComposerCatalog` 浏览面板)⇒ 所有消费方按构造拿到
 *     **路径可用性**干净的声明树(范围见 `sanitizeDeclarations`);本缓存
 *     **入口**再做一次(幂等)兜住被 mock 掉的出口。
 *     此前「路径可用性守卫」在 iterFlat → buildTree → buildNode →
 *     prefillBindings 上逐个冒出来 —— 边界选错了;守卫只该有一个。
 *
 * 消费方约定(**读 / 取分离**,裁定 C18):渲染期只在 computed 里读
 * `getEndpointFull` / `endpointFullState`(读缓存即建立响应依赖,**不取数**);
 * 需要取数时调 `ensureEndpointFull(eid)`(幂等;面 TTL 内不重取,
 * 负缓存窗口内不重发)。
 * **读函数不得内部取数**:一个「读里带取」的合体口把名字变成谎话
 * (叫读,内部却 `void ensureEndpointFull`),而它正是渲染期请求的入口 ——
 * 渲染期零请求(判定面 IS-7 / 画布 CANVAS-FETCH-2)就是靠这条纪律钉住的。
 * 取数时机由宿主显式给出:判定面是 `useInjectableSurface.ensure()`,
 * 画布是 `CaseComposerCanvas` 里按 step 端点集 `immediate: true` 的那次预拉
 * —— 它走的就是 `stepDecls` 会问到的同一份 step 列表(`local`),
 * **覆盖面**由 CANVAS-FETCH-1 钉住。
 */
import { reactive, shallowReactive } from 'vue'

import { getFullEndpoint } from '@/api/scenario-composer'
import { sanitizeEndpointFull } from '@/utils/declarations'
import type { EndpointFullView } from '@/types/plate'

/** 失败重试窗口(ms):窗口内不再发起,避免 plate 故障时渲染路径反复重发。
 *  **优先于 `/full` 面的 TTL**:刚失败的端点即便面已到期也不重发。 */
export const FAILED_RETRY_MS = 10_000

/** `/full` 契约面的有效期(ms):与后端 `endpoint_declarations` 的 300s 同量级。 */
export const FULL_TTL_MS = 300_000

/** 一条缓存条目:面本体 + TTL 的计时起点 + 面版本(见 `surfaceVersion`)。 */
interface FullEntry {
  view: EndpointFullView
  /** 回填时刻(ms):每次成功取回都推进(含面没变的那次,否则 TTL 会立刻再过期)。 */
  at: number
  /** 面版本:首取记 1,此后每次「取回的面与上一份不等」+1。 */
  rev: number
}

/** 会话级缓存 —— Vue 原生响应式容器。**shallow**(裁定 C8a):只跟踪「哪个 endpoint
 *  有条目」,不回填值身份 ⇒ 读回 `EndpointFullView` 本体而非 deep Proxy ——
 *  ①身份断言(`toBe`)比结构断言强,不该为 deep 代理降级成 `toEqual`;
 *  ②缓存条目是 API 不可变快照,只有「入缓存」一个变更事件,deep 跟踪的是永不
 *  变化的嵌套属性,而声明树每渲染被 `buildTree` 全量遍历 ⇒ 逐属性代理是白付开销。 */
const fullByEndpoint = shallowReactive(new Map<string, FullEntry>())
/** 进行中的请求(同 endpoint 并发收敛为同一 Promise) */
const inFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** eid → 失败时刻(ms);**负缓存**:窗口内不重发。值为标量,deep reactive 无副作用。 */
const failedAt = reactive(new Map<string, number>())

/** 面的等价判据:同一份契约序列化出来的 JSON 串相等即同一面。失效方向从严 ——
 *  键序若变只会把「同一面」误判成换面(多算一遍判定),不会把换面漏判。 */
function faceKeyOf(view: EndpointFullView): string {
  return JSON.stringify(view)
}

/** 回填一条面:推进计时起点;**取回的内容真变才动版本**。
 *  内容相同 ⇒ 沿用旧本体与旧版本 —— 一次「没有变化的重取」不该惊动按版本
 *  做键的记忆化投影,也不该换掉消费方手上的对象身份。 */
function storeFetched(endpointId: string, clean: EndpointFullView) {
  const prev = fullByEndpoint.get(endpointId)
  const now = Date.now()
  if (prev && faceKeyOf(prev.view) === faceKeyOf(clean)) {
    fullByEndpoint.set(endpointId, { view: prev.view, at: now, rev: prev.rev })
  } else {
    // 首取也要计一版(0 → 1):记忆化键必须跟着「从无面到有面」一起变
    fullByEndpoint.set(endpointId, { view: clean, at: now, rev: (prev?.rev ?? 0) + 1 })
  }
}

/** 缓存未到期 / 负缓存窗口内 / 在飞 → 直接返回;否则拉 /full、**入口消毒**
 *  (幂等:出口已消毒一次,见 C8b)并回填(fail-soft)。
 *  **TTL 只在这里把守**:`FULL_TTL_MS` 到期才重取。 */
export function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const entry = fullByEndpoint.get(endpointId)
  if (entry && Date.now() - entry.at < FULL_TTL_MS) return Promise.resolve(entry.view)
  const at = failedAt.get(endpointId)
  if (at !== undefined && Date.now() - at < FAILED_RETRY_MS) {
    return Promise.resolve(undefined)          // 负缓存命中:窗口内不重发(**面到期也不例外**)
  }
  const pending = inFlight.get(endpointId)
  if (pending) return pending
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      const clean = sanitizeEndpointFull(full)
      storeFetched(endpointId, clean)
      failedAt.delete(endpointId)
      return clean
    })
    .catch(() => {
      failedAt.set(endpointId, Date.now())     // 负缓存:窗口内不再发起;旧面留在缓存里继续服务
      return undefined
    })
    .finally(() => inFlight.delete(endpointId))
  inFlight.set(endpointId, p)
  return p
}

/** 同步读缓存(**不看 TTL**:过期也返回缓存里那份 —— 重取期间 UI 不闪空,重取
 *  失败时旧面继续服务);未拉取 → undefined。调用方自行 ensure。 */
export function getEndpointFull(endpointId: string): EndpointFullView | undefined {
  return fullByEndpoint.get(endpointId)?.view
}

/** 面的版本号:0 = 尚无面(未取 / 取数失败);首取记 1;此后每次**取回的面与
 *  上一份不等** +1(内容相同的重取不动)。消费方(判定面 `pathsOfStep` 的
 *  记忆化键)靠它感知换面 —— 版本一变,按旧面算出的投影即作废重判。 */
export function surfaceVersion(endpointId: string): number {
  return fullByEndpoint.get(endpointId)?.rev ?? 0
}

/** 端点级拉取状态:**上一次取数失败** = 'failed'(即便缓存里还留着上一份面 ——
 *  面在服务,但契约没刷新);已缓存且上次取数成功 = '';其余(未回填)= 'loading'。 */
export function endpointFullState(endpointId: string | undefined): 'loading' | 'failed' | '' {
  if (!endpointId) return ''
  if (failedAt.has(endpointId)) return 'failed'
  return fullByEndpoint.has(endpointId) ? '' : 'loading'
}

/** 测试钩子:清空缓存(含负缓存与面版本)。仅供单测使用。 */
export function _resetEndpointFullCacheForTest() {
  fullByEndpoint.clear()
  inFlight.clear()
  failedAt.clear()
}
