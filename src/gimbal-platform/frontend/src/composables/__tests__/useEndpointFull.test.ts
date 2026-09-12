/**
 * useEndpointFull — plate /full 结构契约的**唯一**会话级缓存。
 *
 * 契约:每 endpoint 一个会话内恰好一次请求(并发收敛为同一 Promise);
 * 成功入缓存并 bump 版本号(响应式触发器);失败不入缓存(下次可重试)
 * 并记 'failed';版本号在成功与失败时都 bump。
 *
 * 抽取自 CaseComposerCanvas 与 useFieldDescriptions 里各自的一份同款实现。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '@/api/scenario-composer'
import {
  _resetEndpointFullCacheForTest,
  endpointFullState,
  endpointFullVersion,
  ensureEndpointFull,
  getEndpointFull,
} from '@/composables/useEndpointFull'

const FULL = { id: 'fin.order.add', request: { declarations: [] } } as any

describe('useEndpointFull — /full 会话级缓存', () => {
  beforeEach(() => {
    _resetEndpointFullCacheForTest()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('EF-1: 首次拉取后入缓存,再次 ensure 不再发请求', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    expect(getEndpointFull('fin.order.add')).toBeUndefined()

    const first = await ensureEndpointFull('fin.order.add')
    expect(first).toBe(FULL)
    expect(getEndpointFull('fin.order.add')).toBe(FULL)

    const second = await ensureEndpointFull('fin.order.add')
    expect(second).toBe(FULL)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('EF-2: 并发 ensure 同一 endpoint → 收敛为一次请求,结果同一份', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    const [a, b] = await Promise.all([
      ensureEndpointFull('fin.order.add'),
      ensureEndpointFull('fin.order.add'),
    ])
    expect(a).toBe(FULL)
    expect(b).toBe(FULL)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('EF-3: 失败 → undefined 且 state=failed;失败不入缓存,下次仍可重试', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(FULL)

    expect(await ensureEndpointFull('fin.order.add')).toBeUndefined()
    expect(getEndpointFull('fin.order.add')).toBeUndefined()
    expect(endpointFullState('fin.order.add')).toBe('failed')

    // 重试成功 → 转缓存态
    expect(await ensureEndpointFull('fin.order.add')).toBe(FULL)
    expect(endpointFullState('fin.order.add')).toBe('')
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('EF-4: state — 已缓存 = ""、失败 = failed、未拉过 = loading、无 id = ""', () => {
    expect(endpointFullState(undefined)).toBe('')
    expect(endpointFullState('never.requested')).toBe('loading')
  })

  it('EF-5: 版本号在成功与失败时都 bump(computed 重算触发器)', async () => {
    vi.spyOn(api, 'getFullEndpoint')
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(FULL)
    const v0 = endpointFullVersion.value
    await ensureEndpointFull('e1')
    expect(endpointFullVersion.value).toBeGreaterThan(v0)
    const v1 = endpointFullVersion.value
    await ensureEndpointFull('e2')
    expect(endpointFullVersion.value).toBeGreaterThan(v1)
  })
})
