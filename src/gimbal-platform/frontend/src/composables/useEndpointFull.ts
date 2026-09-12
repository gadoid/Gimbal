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
 *     Map.has 被 Vue 跟踪),回填后 computed 自动重算。消费方**不需要**任何
 *     手工版本号或「读一下让它失效」的声明 —— 手工协议要求每个消费方在每处
 *     computed 里手写,漏一处即静默不重算(本容器不欠这份债)。
 *   - **失败负缓存**:失败记 `failedAt`,窗口 `FAILED_RETRY_MS` 内不再发起
 *     (plate 故障时渲染路径不再反复重发),窗口过后允许重试。
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
 * 需要取数时调 `ensureEndpointFull(eid)`(幂等,每端点每会话一次)。
 * **判定面的读函数不得内部取数**:一个「读里带取」的合体口把名字变成谎话
 * (叫读,内部却 `void ensureEndpointFull`),而它正是渲染期请求的入口 ——
 * 判定面渲染期零请求(IS-7)就是靠这条纪律钉住的。
 * **这条纪律的落实范围 = 判定面**(`composables/useInjectableSurface.ts`);
 * 画布 `components/composer/CaseComposerCanvas.vue:635-640` 的 `stepDecls` 与
 * `:1591-1596` 的 `currentFull` 两个 computed 仍在内部
 * `void ensureEndpointFull(eid)` —— 画布**渲染期会取数**,由会话缓存 + 负缓存
 * 兜底(不自维持)。已知问题(非本文件可收口):
 * `docs/known-issues/platform/declaration-cache/canvas-render-path-fetch.md`。
 */
import { reactive, shallowReactive } from 'vue'

import { getFullEndpoint } from '@/api/scenario-composer'
import { sanitizeEndpointFull } from '@/utils/declarations'
import type { EndpointFullView } from '@/types/plate'

/** 失败重试窗口(ms):窗口内不再发起,避免 plate 故障时渲染路径反复重发。 */
export const FAILED_RETRY_MS = 10_000

/** 会话级缓存 —— Vue 原生响应式容器。**shallow**(裁定 C8a):只跟踪「哪个 endpoint
 *  有条目」,不回填值身份 ⇒ 读回 `EndpointFullView` 本体而非 deep Proxy ——
 *  ①身份断言(`toBe`)比结构断言强,不该为 deep 代理降级成 `toEqual`;
 *  ②缓存条目是 API 不可变快照,只有「入缓存」一个变更事件,deep 跟踪的是永不
 *  变化的嵌套属性,而声明树每渲染被 `buildTree` 全量遍历 ⇒ 逐属性代理是白付开销。 */
const fullByEndpoint = shallowReactive(new Map<string, EndpointFullView>())
/** 进行中的请求(同 endpoint 并发收敛为同一 Promise) */
const inFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** eid → 失败时刻(ms);**负缓存**:窗口内不重发。值为标量,deep reactive 无副作用。 */
const failedAt = reactive(new Map<string, number>())

/** 缓存 miss 时拉 /full、**入口消毒**(幂等:出口已消毒一次,见 C8b)并回填(fail-soft);
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
      const clean = sanitizeEndpointFull(full)
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

/** 测试钩子:清空缓存(含负缓存)。仅供单测使用。 */
export function _resetEndpointFullCacheForTest() {
  fullByEndpoint.clear()
  inFlight.clear()
  failedAt.clear()
}
