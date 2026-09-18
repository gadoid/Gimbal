/**
 * scenario-composer store — ensureScenarios 的**单飞合流**契约。
 *
 * 工作台同帧挂 3 张场景卡(我的 / 公共 / 关注),每张 onMounted 都要取
 * 场景列表。各走各的 API = 进一次 /home 打 3 个完全相同的
 * GET /api/scenarios;ensureScenarios 负责"已成功就复用、并发调用合流"。
 * 另钉:失败不得置 loaded(否则一次网络抖动永久留白到刷新)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import * as api from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn(),
}))

const ROWS = [
  { meta: { scenarioId: 'a', name: 'A' }, visibility: 'private' },
] as never

describe('useScenarioComposerStore.ensureScenarios', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('三卡并发调用只打一次 API,各自拿到同一份列表', async () => {
    vi.mocked(api.listScenarios).mockResolvedValue(ROWS)
    const store = useScenarioComposerStore()

    const [mine, pub, star] = await Promise.all([
      store.ensureScenarios(),
      store.ensureScenarios(),
      store.ensureScenarios(),
    ])

    expect(api.listScenarios).toHaveBeenCalledTimes(1)
    expect(mine).toHaveLength(1)
    expect(pub).toHaveLength(1)
    expect(star).toHaveLength(1)
  })

  it('已成功加载 → 后续调用不再打网络', async () => {
    vi.mocked(api.listScenarios).mockResolvedValue(ROWS)
    const store = useScenarioComposerStore()

    await store.ensureScenarios()
    await store.ensureScenarios()

    expect(api.listScenarios).toHaveBeenCalledTimes(1)
    expect(store.scenariosLoaded).toBe(true)
  })

  it('取数失败不置 loaded,下次进入自动重试并恢复', async () => {
    const store = useScenarioComposerStore()

    vi.mocked(api.listScenarios).mockRejectedValueOnce(new Error('boom'))
    await store.ensureScenarios()
    expect(store.scenariosStatus).toBe('error')
    expect(store.scenariosLoaded).toBe(false)

    vi.mocked(api.listScenarios).mockResolvedValue(ROWS)
    const rows = await store.ensureScenarios()
    expect(api.listScenarios).toHaveBeenCalledTimes(2)
    expect(rows).toHaveLength(1)
    expect(store.scenariosLoaded).toBe(true)
  })
})
