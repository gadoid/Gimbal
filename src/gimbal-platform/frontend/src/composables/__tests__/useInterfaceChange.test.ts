/**
 * useInterfaceChange — 「接口有变更」信号的读侧策略。
 * 钉住:403(member 无适配中心读权限)是**永久**留白 → 置 loaded 不再打请求;
 * 网络抖动/5xx 是**暂时**失败 → 绝不置 loaded(否则一次抖动把信号打死到刷新);
 * 并发 ensure 合流成一次 catalogDiff;影响面查询限并发(待处理端点可能十几个)。
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('@/api/adaptations', () => ({
  catalogDiff: vi.fn(),
  impact: vi.fn(),
  impactBulk: vi.fn(),
}))
vi.mock('@/api/activity', () => ({ getActivity: vi.fn().mockResolvedValue({
  events: [], sources: { executions: true, scenarios: true, adaptations: true },
}) }))

/** 每个用例重取一份模块:loaded/changed 是 module 作用域单例。 */
async function fresh() {
  vi.resetModules()
  // 先取被测模块、再取 api:并发 import 会让两边拿到不同的 mock 实例
  const mod = await import('@/composables/useInterfaceChange')
  const api = await import('@/api/adaptations')
  // api 的 mock 工厂跨 resetModules 复用同一批 spy → 计数与实现都要归零
  vi.resetAllMocks()
  return { api, change: mod.useInterfaceChange() }
}

const httpErr = (status: number) => ({ response: { status } })
const report = (n: number) =>
  ({ pending: Array.from({ length: n }, (_, i) => ({ endpointId: `ep-${i}` })) }) as never

describe('useInterfaceChange', () => {
  it('member 403 → 信号留白并认栽,后续 ensure 不再打请求', async () => {
    const { api, change } = await fresh()
    vi.mocked(api.catalogDiff).mockRejectedValue(httpErr(403))

    await change.ensure()
    await change.ensure()
    expect(api.catalogDiff).toHaveBeenCalledTimes(1)
    expect(change.hasChange('sc-1')).toBe(false)
  })

  it('5xx 不置 loaded → 下次进入自动重试,成功后信号照常点亮', async () => {
    const { api, change } = await fresh()
    vi.mocked(api.catalogDiff).mockRejectedValueOnce(httpErr(500))
    await change.ensure()
    expect(change.hasChange('sc-1')).toBe(false)

    vi.mocked(api.catalogDiff).mockResolvedValue(report(1))
    vi.mocked(api.impactBulk).mockResolvedValue({
      'ep-0': [{ scenarioId: 'sc-1' }] as never,
    })
    await change.ensure()
    expect(api.catalogDiff).toHaveBeenCalledTimes(2)
    expect(change.hasChange('sc-1')).toBe(true)
  })

  it('并发 ensure 合流成一次 catalogDiff(三页同帧挂载只该打一次)', async () => {
    const { api, change } = await fresh()
    vi.mocked(api.catalogDiff).mockResolvedValue(report(0))
    await Promise.all([change.ensure(), change.ensure(), change.ensure()])
    expect(api.catalogDiff).toHaveBeenCalledTimes(1)
  })

  it('M5:一次 impactBulk 拿回全部 pending 端点的受影响面(不再逐端点)', async () => {
    const { api, change } = await fresh()
    vi.mocked(api.catalogDiff).mockResolvedValue(report(10))
    vi.mocked(api.impactBulk).mockImplementation(async (ids: string[]) => {
      const out: Record<string, unknown[]> = {}
      for (const id of ids) out[id] = [{ scenarioId: `sc-of-${id}` }]
      return out as never
    })

    await change.ensure()
    // 一次批量请求,10 个端点全部点名
    expect(api.impactBulk).toHaveBeenCalledTimes(1)
    expect(api.impactBulk).toHaveBeenCalledWith(
      Array.from({ length: 10 }, (_, i) => `ep-${i}`))
    expect(change.hasChange('sc-of-ep-0')).toBe(true)
    expect(change.hasChange('sc-of-ep-9')).toBe(true)
  })
})
