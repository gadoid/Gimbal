/**
 * useScenarioName — 面包屑场景名解析契约。
 * 核心:缓存是 reactive Map — composer 保存改名 seedScenarioName 后,
 * **已挂载的消费者即时更新**(P3 修复:改名后顶条不再显示旧名)。
 * 其余:拉取成功缓存 / 失败静默回退 id / inflight 去重。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { seedScenarioName, useScenarioName } from '@/composables/useScenarioName'
import * as api from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  getScenario: vi.fn(),
}))

function scenario(name: string) {
  return { meta: { scenarioId: 'sc-1', name } } as never
}

describe('useScenarioName', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // 缓存是模块级 reactive Map(未导出清除口)——各用例用独立 id 隔离
  })

  it('未命中缓存 → 拉取后返回 name', async () => {
    vi.mocked(api.getScenario).mockResolvedValue(scenario('订单创建'))
    const name = useScenarioName(ref('sc-fresh'))
    expect(name.value).toBe('')   // 拉取前为空(回退由消费方 || id 兜)
    await vi.waitFor(() => expect(name.value).toBe('订单创建'))
    expect(api.getScenario).toHaveBeenCalledWith('sc-fresh')
  })

  it('seedScenarioName 后已挂载消费者即时更新(改名同步契约)', () => {
    const name = useScenarioName(ref('sc-seeded'))
    expect(name.value).toBe('')
    // composer 保存改名 → 顶条面包屑即时跟随
    seedScenarioName('sc-seeded', '新名字')
    expect(name.value).toBe('新名字')
    seedScenarioName('sc-seeded', '再改名')
    expect(name.value).toBe('再改名')
  })

  it('拉取失败 → 静默保持空(消费方回退 id),不抛错', async () => {
    vi.mocked(api.getScenario).mockRejectedValue(new Error('offline'))
    const name = useScenarioName(ref('sc-broken'))
    await vi.waitFor(() => expect(api.getScenario).toHaveBeenCalled())
    expect(name.value).toBe('')
  })

  it('空 id → 空串且不发请求', () => {
    const name = useScenarioName(ref(''))
    expect(name.value).toBe('')
    expect(api.getScenario).not.toHaveBeenCalled()
  })
})
