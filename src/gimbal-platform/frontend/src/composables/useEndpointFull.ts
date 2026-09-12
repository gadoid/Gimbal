/**
 * useEndpointFull.ts — plate `/full` 结构契约的**唯一**会话级缓存。
 *
 * 抽取自两份同款实现(CaseComposerCanvas 的端点契约缓存、useFieldDescriptions
 * 的字段说明缓存)—— 同一模式留两份副本就会各自漂移,收成一份:
 *
 *   - 每 endpoint 一个会话内恰好一次请求;并发收敛为同一 Promise。
 *   - 零持久化:Plate 是结构权威源,每次进页面拿最新结构(发版后零迁移)。
 *   - 失败 fail-soft:返回 undefined 且**不入缓存**(下次调用可重试),
 *     端点级状态记 'failed' 供占位/徽标降级。
 *   - Map 变更不触发 computed → 用版本号 `endpointFullVersion` 显式依赖。
 *
 * 消费方约定:在 computed 里 `void endpointFullVersion.value` 建立响应依赖,
 * 在需要时调 `ensureEndpointFull(eid)`(幂等)。
 */
import { ref, type Ref } from 'vue'

import { getFullEndpoint } from '@/api/scenario-composer'
import type { DeclarationEntryView, EndpointFullView } from '@/types/plate'

const fullByEndpoint = new Map<string, EndpointFullView>()
/** 进行中的请求(同 endpoint 并发收敛为同一 Promise) */
const inFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** 拉取失败端点(Set 无响应性,经版本号触发重算) */
const failed = new Set<string>()
/** 版本号 — Map/Set 变化不触发 computed;bump 让 computed 重算 */
const endpointFullVersion: Ref<number> = ref(0)

/** 缓存 miss 时拉 /full 并回填(fail-soft);命中缓存/在飞则直接返回 */
export function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const cached = fullByEndpoint.get(endpointId)
  if (cached) return Promise.resolve(cached)
  const pending = inFlight.get(endpointId)
  if (pending) return pending
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      fullByEndpoint.set(endpointId, full)
      failed.delete(endpointId)
      endpointFullVersion.value++
      return full
    })
    .catch(() => {
      failed.add(endpointId)          // 不入缓存 → 下次调用可重试
      endpointFullVersion.value++     // 失败也是状态变更:占位/徽标重算
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

/** 端点级拉取状态:已缓存 = ''、失败 = 'failed'、其余(未回填)= 'loading' */
export function endpointFullState(endpointId: string | undefined): 'loading' | 'failed' | '' {
  if (!endpointId) return ''
  if (fullByEndpoint.has(endpointId)) return ''
  return failed.has(endpointId) ? 'failed' : 'loading'
}

/** 步骤的契约声明面(读共享缓存;未拉取则发起)。上层投影用。
 *  无 endpoint_id / 未回填 → undefined(调用方降级为「只认 body 面」)。 */
export function requestDeclarationsOf(step: unknown): DeclarationEntryView[] | undefined {
  const eid = (step as { api?: { view_hints?: { endpoint_id?: string } } } | null | undefined)
    ?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return getEndpointFull(eid)?.request?.declarations
}

/** 测试钩子:清空缓存。仅供单测使用。 */
export function _resetEndpointFullCacheForTest() {
  fullByEndpoint.clear()
  inFlight.clear()
  failed.clear()
  endpointFullVersion.value++
}

export { endpointFullVersion }
