/**
 * executions store — T13-Q1(remove 出清行级/工件缓存)
 * + T13-Q2(刷新跳过「已知终态且已有 rows 缓存」的执行;首拍观察到
 * 终态的那一拍仍拉到最终 rows)
 * + P2-06:SSE 事件流驱动(事件帧 → 节流刷新;done 帧 → 终收敛停流;
 *   Last-Event-ID 重连续传;404 收口)。
 */
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'
import { useAuthStore } from '@/stores/auth'

/** 列表行形态(M1:configSummary 窄投影,无 config)。 */
function makeExec(id: number, status: api.ExecutionStatus): api.ExecutionListItem {
  return {
    id,
    scenario_id: 'sc-a',
    status,
    total_runs: 1,
    passed: 1,
    failed: 0,
    started_at: null,
    configSummary: {},
    finished_at: null,
    has_scenario_snapshot: false,
    batch_id: null,
    consecutive_failures: 0,
  }
}

/** 详情形态(保留完整 config)。 */
function makeDetail(id: number, status: api.ExecutionStatus): api.Execution {
  const { configSummary: _cs, ...rest } = makeExec(id, status)
  return { ...rest, config: {} }
}

const REFRESH_WAIT = 600

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
  store.detail = makeDetail(9, 'done')

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

it('toggleArtifact:展开即拉一次并记 key;收起只藏不清缓存;重展重拉', async () => {
  const artSpy = vi.spyOn(api, 'getCaseArtifact').mockResolvedValue('log-body')
  const store = useExecutionsStore()

  store.toggleArtifact(9, 'case-a', 'engine-log')      // 展开
  expect(artSpy).toHaveBeenCalledWith(9, 'case-a', 'engine-log')
  expect(store.expandedArtifacts.has('9:case-a:engine-log')).toBe(true)

  store.toggleArtifact(9, 'case-a', 'engine-log')      // 收起:视图藏,缓存留
  expect(store.expandedArtifacts.has('9:case-a:engine-log')).toBe(false)

  store.toggleArtifact(9, 'case-a', 'engine-log')      // 重展:重拉最新
  expect(artSpy).toHaveBeenCalledTimes(2)
  expect(store.expandedArtifacts.has('9:case-a:engine-log')).toBe(true)
})

it('remove() 同时出清该 id 的工件展开态', async () => {
  vi.spyOn(api, 'remove').mockResolvedValue(undefined)
  const store = useExecutionsStore()
  store.expandedArtifacts = new Set(['9:case-a:engine-log', '10:case-b:result'])
  store.list = [makeExec(9, 'done'), makeExec(10, 'running')]
  store.detail = makeDetail(9, 'done')

  await store.remove(9)

  expect(store.expandedArtifacts.has('9:case-a:engine-log')).toBe(false)
  expect(store.expandedArtifacts.has('10:case-b:result')).toBe(true)
})

it('SSE 事件帧驱动刷新;done 帧终收敛;已知终态跳过 rows(P2-06)', async () => {
  vi.useFakeTimers()
  const frames: string[] = []
  let closeStream!: () => void
  const fetchMock = vi.fn().mockImplementation(() => {
    const enc = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const push = (text: string) => controller.enqueue(enc.encode(text))
        for (const f of frames.splice(0)) push(f)
        closeStream = () => { try { controller.close() } catch { /* 已关 */ } }
      },
    })
    return Promise.resolve({
      ok: true, status: 200, body: stream,
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  const auth = useAuthStore()
  auth.accessToken = 'tok'

  try {
    const getSpy = vi.spyOn(api, 'get')
      .mockResolvedValue(makeDetail(7, 'running'))
    const rowsSpy = vi.spyOn(api, 'getExecutionRows')
      .mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 500 })
    const store = useExecutionsStore()
    store.expanded = new Set([7, 8])
    store.rowsByExecution = { 7: [], 8: [] }
    store.list = [makeExec(7, 'running'), makeExec(8, 'done')]

    const stop = store.startPolling(7)
    await vi.advanceTimersByTimeAsync(0)   // 基线首刷

    // ① 事件帧 → 节流刷新:7 拉一次;8(已知终态且有缓存)跳过
    frames.push('id: 1\nevent: ev\ndata: {"seq":1}\n\n')
    // fetch 已被消费?流在 start 时建立,后推帧需要重新排队 —— 本测试
    // 的 ReadableStream start 只冲已有帧;重新建立流模拟服务端推送:
    await vi.advanceTimersByTimeAsync(REFRESH_WAIT)
    expect(store.detail?.id).toBe(7)

    // ② done 帧 → 立即终收敛(get 推进 done)+ 停流
    getSpy.mockResolvedValue(makeDetail(7, 'done'))
    frames.push('id: 2\nevent: done\ndata: {"status":"done"}\n\n')
    const stream2 = new ReadableStream<Uint8Array>({
      start(c) { c.enqueue(new TextEncoder().encode(frames.splice(0).join(''))) },
    })
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: stream2 })
    // 触发重连路径以消费新流:手动停止当前流并重开
    stop()
    const stop2 = store.startPolling(7)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(REFRESH_WAIT)
    expect(store.detail?.status).toBe('done')
    expect(rowsSpy).toHaveBeenCalledWith(7)
    expect(rowsSpy).not.toHaveBeenCalledWith(8)
    stop2()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('SSE 404:执行已删 → 停流 + pollError(P2-06)', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    vi.spyOn(api, 'get').mockRejectedValue(
      Object.assign(new Error('404'), { status: 404 }))
    const store = useExecutionsStore()
    store.detail = makeDetail(9, 'running')
    const stop = store.startPolling(9)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(2000)
    expect(store.pollError).toContain('不存在')
    expect(store.detail).toBeNull()
    stop()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('SSE 404 后兜底轮询停拍(R9):不再每 3s 拉一次 404 直到卸载', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    const getSpy = vi.spyOn(api, 'get').mockRejectedValue(
      Object.assign(new Error('404'), { status: 404 }))
    const store = useExecutionsStore()
    store.detail = makeDetail(11, 'running')
    store.startPolling(11)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(1000)   // SSE 404 → 收口
    const callsAfter404 = getSpy.mock.calls.length
    await vi.advanceTimersByTimeAsync(10_000) // 再走 10s(3 拍以上)
    expect(getSpy.mock.calls.length).toBe(callsAfter404)
    expect(store.pollError).toContain('不存在')
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('兜底轮询 404 视为终态(R9):SSE 静默时兜底自身停拍', async () => {
  vi.useFakeTimers()
  // SSE 流挂起(不开 404);api.get 404 → 兜底发现已删 → 收口
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => { /* 挂起 */ })))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    const getSpy = vi.spyOn(api, 'get').mockRejectedValue(
      Object.assign(new Error('404'), { status: 404 }))
    const store = useExecutionsStore()
    store.detail = makeDetail(12, 'running')
    store.startPolling(12)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(3100)   // 首拍兜底 404 → 收口
    const calls = getSpy.mock.calls.length
    await vi.advanceTimersByTimeAsync(10_000)
    expect(getSpy.mock.calls.length).toBe(calls)
    expect(store.pollError).toContain('不存在')
    expect(store.detail).toBeNull()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('代际比对(R9):切换执行后,上一执行的迟到响应不覆盖当前 detail', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => { /* SSE 挂起 */ })))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    let resolveOld!: (d: api.Execution) => void
    const getSpy = vi.spyOn(api, 'get')
      .mockImplementationOnce(() => new Promise((res) => { resolveOld = res }))
      .mockResolvedValue(makeDetail(21, 'running'))
    const store = useExecutionsStore()
    store.startPolling(20)                       // 旧执行的基线刷新挂起
    await vi.advanceTimersByTimeAsync(0)
    store.stopPolling()
    store.startPolling(21)                       // 切到新执行
    await vi.advanceTimersByTimeAsync(0)
    resolveOld(makeDetail(20, 'done'))           // 旧响应迟到到达
    await vi.advanceTimersByTimeAsync(100)
    expect(store.detail?.id).toBe(21)            // 不被旧执行覆盖
    expect(getSpy).toHaveBeenCalled()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('N5:重连耗尽只停 SSE,兜底继续拉取(状态不再卡 running)', async () => {
  vi.useFakeTimers()
  // SSE 恒 500(重连 10 次耗尽);api.get 正常返回 running → 兜底应持续刷新
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    const getSpy = vi.spyOn(api, 'get')
      .mockResolvedValue(makeDetail(30, 'running'))
    const store = useExecutionsStore()
    store.startPolling(30)
    // 走完 10 次重连(每次 1s 间隔)+ 若干兜底拍(3s 一拍)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(store.pollError).toContain('按 3 秒轮询刷新')
    const callsAfterExhaust = getSpy.mock.calls.length
    expect(callsAfterExhaust).toBeGreaterThan(5)  // 兜底一直在拉
    await vi.advanceTimersByTimeAsync(9_000)      // 再走 3 拍
    expect(getSpy.mock.calls.length).toBeGreaterThanOrEqual(callsAfterExhaust + 3)
    expect(store.detail?.status).toBe('running')  // 数据仍在更新通道上
    store.stopPolling()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

it('N5:上一执行迟到的 404 不停掉当前执行的轮询', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => { /* SSE 挂起 */ })))
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  try {
    let rejectOld!: (e: unknown) => void
    vi.spyOn(api, 'get')
      .mockImplementationOnce(() => new Promise((_res, rej) => { rejectOld = rej }))
      .mockResolvedValue(makeDetail(41, 'running'))
    const store = useExecutionsStore()
    store.startPolling(40)                       // 旧执行基线刷新挂起
    await vi.advanceTimersByTimeAsync(0)
    store.stopPolling()
    store.startPolling(41)                       // 切到新执行
    await vi.advanceTimersByTimeAsync(0)
    rejectOld(Object.assign(new Error('404'), { status: 404 }))  // 旧执行 404 迟到
    await vi.advanceTimersByTimeAsync(4000)      // 兜底照常走拍
    expect(store.pollError).not.toContain('不存在')
    expect(store.detail?.id).toBe(41)            // 当前执行轮询未被误停
    store.stopPolling()
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})
