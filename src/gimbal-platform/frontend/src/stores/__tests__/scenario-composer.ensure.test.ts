/**
 * scenario-composer store — ensureWindow 的**单飞合流**契约(M1 store 退位)。
 *
 * 工作台同帧挂多张场景卡 + 时间线,每张 onMounted 都要场景数据。各走各的
 * API = 进一次 /home 打多个完全相同的 GET /api/scenarios;ensureWindow
 * 负责"已成功就复用、并发调用合流"(旧 ensureScenarios 的同一契约,数据
 * 面从全量列表换成第一页 ≤100 条投影窗)。
 * 另钉:失败不得置 loaded(否则一次网络抖动永久留白到刷新)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import * as api from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn(),
}))

const ENV = {
  items: [
    { meta: { scenarioId: 'a', name: 'A' }, visibility: 'private' },
  ],
  total: 1, page: 1, pageSize: 100,
} as never

describe('useScenarioComposerStore.ensureWindow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('并发调用只打一次 API,各自拿到同一份首窗', async () => {
    vi.mocked(api.listScenarios).mockResolvedValue(ENV)
    const store = useScenarioComposerStore()

    const [a, b, c] = await Promise.all([
      store.ensureWindow(),
      store.ensureWindow(),
      store.ensureWindow(),
    ])

    expect(api.listScenarios).toHaveBeenCalledTimes(1)
    expect(a).toHaveLength(1)
    expect(b).toHaveLength(1)
    expect(c).toHaveLength(1)
  })

  it('已成功加载 → 后续调用不再打网络', async () => {
    vi.mocked(api.listScenarios).mockResolvedValue(ENV)
    const store = useScenarioComposerStore()

    await store.ensureWindow()
    await store.ensureWindow()

    expect(api.listScenarios).toHaveBeenCalledTimes(1)
    expect(store.windowLoaded).toBe(true)
  })

  it('取数失败不置 loaded,下次进入自动重试并恢复', async () => {
    const store = useScenarioComposerStore()

    vi.mocked(api.listScenarios).mockRejectedValueOnce(new Error('boom'))
    await store.ensureWindow()
    expect(store.windowStatus).toBe('error')
    expect(store.windowLoaded).toBe(false)

    vi.mocked(api.listScenarios).mockResolvedValue(ENV)
    const rows = await store.ensureWindow()
    expect(api.listScenarios).toHaveBeenCalledTimes(2)
    expect(rows).toHaveLength(1)
    expect(store.windowLoaded).toBe(true)
  })

  it('invalidate 作废首窗 → 下次 ensureWindow 重新拉(退位后 mutation 的作废通道)', async () => {
    vi.mocked(api.listScenarios).mockResolvedValue(ENV)
    const store = useScenarioComposerStore()
    await store.ensureWindow()
    expect(api.listScenarios).toHaveBeenCalledTimes(1)

    store.invalidate()
    await store.ensureWindow()
    expect(api.listScenarios).toHaveBeenCalledTimes(2)
  })
})
