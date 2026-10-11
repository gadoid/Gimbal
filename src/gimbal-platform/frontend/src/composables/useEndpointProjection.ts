/**
 * useEndpointProjection.ts — plate call 投影（4.8）的会话级共享缓存。
 *
 * M4/Release 6.2：场景 call 只存场景自有字段（service/user/path_params/
 * 追加 headers），method/path 模板等 binding 派生字段不落库 —— 编排页
 * 只读展示经投影查询取回。投影按修订不可变，会话级缓存即可（同
 * useEndpointFull 的共享纪律：一个端点一次拉取，全局复用）。
 */
import { ref } from 'vue'
import {
  getEndpointProjection, type CallProjectionView,
} from '@/api/scenario-composer'

const cache = new Map<string, CallProjectionView>()
const inflight = new Map<string, Promise<CallProjectionView>>()
const version = ref(0)

/** 测试钩子：清空投影缓存。 */
export function _resetEndpointProjectionCacheForTest(): void {
  cache.clear()
  inflight.clear()
  version.value++
}

export function ensureEndpointProjection(
  endpointId: string, ref?: string,
): Promise<CallProjectionView> {
  // M1:投影按修订不可变 —— 键含修订;缺省 working 与旧键一致
  const key = ref && ref !== 'working'
    ? `${endpointId}@${ref}` : endpointId
  const hit = cache.get(key)
  if (hit) return Promise.resolve(hit)
  let p = inflight.get(key)
  if (!p) {
    p = ref
      ? getEndpointProjection(endpointId, ref)
      : getEndpointProjection(endpointId)
      .then((item) => {
        cache.set(key, item)
        return item
      })
      .finally(() => { inflight.delete(key) })
    inflight.set(key, p)
  }
  return p
}

/** step 的投影展示面（method/path 模板）；无锚点/拉取失败 → null。 */
export function useEndpointProjection(
  endpointId: () => string | undefined,
  refOf?: () => string | undefined,
) {
  const proj = ref<CallProjectionView | null>(null)
  let lastKey = ''

  async function refresh(): Promise<void> {
    const eid = endpointId()
    if (!eid) { proj.value = null; lastKey = ''; return }
    const ref = refOf?.() || undefined
    const key = ref && ref !== 'working' ? `${eid}@${ref}` : eid
    if (lastKey === key && proj.value) return
    lastKey = key
    proj.value = cache.get(key) ?? null
    try {
      proj.value = await ensureEndpointProjection(eid, ref)
    } catch {
      proj.value = null   // 展示降级：只显示场景自有字段（service 等）
    }
  }

  void refresh()
  return { proj, refresh, version }
}
