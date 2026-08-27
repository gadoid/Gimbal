/**
 * executions store — T13-Q1(remove 出清行级/工件缓存)
 * + T13-Q2(tick 跳过「已知终态且已有 rows 缓存」的执行;首拍观察到
 * 终态的那一拍仍拉到最终 rows)。
 */
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'

function makeExec(id: number, status: api.ExecutionStatus): api.Execution {
  return {
    id,
    scenario_id: 'sc-a',
    status,
    total_runs: 1,
    passed: 1,
    failed: 0,
    started_at: null,
    finished_at: null,
    config: {},
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

it('remove() 出清 list/detail + expanded/rows/工件缓存(不误伤其他 id)', async () => {
  const del = vi.spyOn(api, 'remove').mockResolvedValue(undefined)
  const store = useExecutionsStore()
  store.expanded = new Set([9])
  store.rowsByExecution = { 9: [], 10: [] }
  store.artifactText = { '9:case-a:engine-log': 'log', '10:case-b:result': '{ }' }
  store.artifactError = { '9:case-a:result': '拉取失败' }
  store.list = [makeExec(9, 'done'), makeExec(10, 'running')]
  store.detail = makeExec(9, 'done')

  await store.remove(9)

  expect(del).toHaveBeenCalledWith(9)
  expect(store.list.map((e) => e.id)).toEqual([10])
  expect(store.detail).toBeNull()
  expect(store.expanded.has(9)).toBe(false)
  expect(store.rowsByExecution[9]).toBeUndefined()
  expect(store.rowsByExecution[10]).toEqual([])
  expect(store.artifactText['9:case-a:engine-log']).toBeUndefined()
  expect(store.artifactText['10:case-b:result']).toBe('{ }')
  expect(store.artifactError['9:case-a:result']).toBeUndefined()
})

it('tick:已知终态且已有 rows 的执行跳过;首拍观察到终态的那一拍仍拉', async () => {
  vi.useFakeTimers()
  try {
    const getSpy = vi.spyOn(api, 'get')
      .mockResolvedValue(makeExec(7, 'running'))
    const rowsSpy = vi.spyOn(api, 'getExecutionRows')
      .mockResolvedValue({ items: [] })
    const store = useExecutionsStore()
    // 7 = 轮询对象(list 快照 running,终态由 detail 推进);
    // 8 = 其他已展开执行,list 快照终态 → tick 跳过。
    store.expanded = new Set([7, 8])
    store.rowsByExecution = { 7: [], 8: [] }
    store.list = [makeExec(7, 'running'), makeExec(8, 'done')]

    store.startPolling(7)
    await vi.advanceTimersByTimeAsync(1000) // tick 1:7 拉一次,8 跳过
    expect(rowsSpy).toHaveBeenCalledWith(7)
    expect(rowsSpy).not.toHaveBeenCalledWith(8)

    // 7 收敛为终态的那一拍(FIRST 观察):终态判定之前仍拉到最终 rows。
    getSpy.mockResolvedValue(makeExec(7, 'done'))
    const before = rowsSpy.mock.calls.length
    await vi.advanceTimersByTimeAsync(1000) // tick 2:prevDetail=running → 7 仍拉
    expect(rowsSpy.mock.calls.length).toBe(before + 1)
    expect(store.detail?.status).toBe('done')

    // 终态后轮询停止:不再有任何 rows 拉取。
    await vi.advanceTimersByTimeAsync(3000)
    expect(rowsSpy.mock.calls.length).toBe(before + 1)
    store.stopPolling()
  } finally {
    vi.useRealTimers()
  }
})
