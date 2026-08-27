/**
 * adaptations store —— 徽章数据源(D3):
 *   - 静默 diff 一次 → pendingCount;
 *   - 失败(plate 502/网络)保留旧数据、只记 lastError;
 *   - 并发/重复调用合并为一次请求;force 才重拉。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAdaptationsStore } from '@/stores/adaptations'
import * as api from '@/api/adaptations'

function apiError(status?: number) {
  return Object.assign(new Error('boom'), { status })
}

const report = {
  pending: [
    { endpointId: 'fin.order.add', fromVersion: '1.0.0', toVersion: '1.1.0' },
    { endpointId: 'fin.order.cancel', fromVersion: '2.0.0', toVersion: '2.1.0' },
  ],
  anomalies: [],
  baselinedNow: 0,
}

describe('adaptations store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('refreshDiff 成功 → pendingCount 与 diffReport 落库', async () => {
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await store.refreshDiff(true)

    expect(store.pendingCount).toBe(2)
    expect(store.diffReport).toEqual(report)
    expect(store.lastError).toBe('')
  })

  it('失败 → lastError 记错,旧数据保留', async () => {
    vi.spyOn(api, 'catalogDiff').mockRejectedValue(apiError(502))
    const store = useAdaptationsStore()

    await store.refreshDiff(true)

    expect(store.lastError).toContain('目录服务不可用')
    expect(store.pendingCount).toBe(0)
    expect(store.diffReport).toBeNull()
  })

  it('并发双调用 → 只发一次请求', async () => {
    const spy = vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await Promise.all([store.refreshDiff(true), store.refreshDiff(true)])

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('ensureBadgeLoaded 幂等;refreshDiff(true) 才重拉', async () => {
    const spy = vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await store.ensureBadgeLoaded()
    await store.ensureBadgeLoaded()
    expect(spy).toHaveBeenCalledTimes(1)

    await store.refreshDiff(true)
    expect(spy).toHaveBeenCalledTimes(2)
  })
})
