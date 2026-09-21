/**
 * useActivityTimeline — 右栏时间线(M5-3 服务端合流后的前端面)。
 * 钉住:合流事件映射(文案/深链)、日历日分组、预览位/展开、
 * sources 降级语义、颜色筛流单选可取消与自动撤筛。
 * (三源合并/私有桶过滤/入池上限/无时间戳跳过等数据面语义已移服务端,
 * 见 backend tests/test_activity_api.py。)
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useActivityTimeline } from '@/composables/useActivityTimeline'
import * as activityApi from '@/api/activity'

vi.mock('@/api/activity', () => ({ getActivity: vi.fn() }))

const ago = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString()

const execEvent = (id: number, status: string, at: string | null, scenario = 'sc-a') =>
  ({ kind: 'execution', at: at ?? '', executionId: id, status, scenarioId: scenario }) as never
const batchEvent = (id: string, at: string, over = {}) =>
  ({ kind: 'adaptation', at, batchId: id, fromVersion: 'v1', toVersion: 'v2',
     status: 'completed', endpointId: 'fin.pay.create', opCount: 2, ...over }) as never
const scenEvent = (id: string, at: string) =>
  ({ kind: 'scenario', at, scenarioId: id, name: `场景 ${id}`, module: 'm' }) as never

async function loadWith(data: {
  events?: never[]
  sources?: Record<string, boolean>
}) {
  vi.mocked(activityApi.getActivity).mockResolvedValue({
    events: data.events ?? [],
    sources: data.sources ?? { executions: true, scenarios: true, adaptations: true },
  } as never)
  const t = useActivityTimeline()
  await t.load()
  return t
}

describe('useActivityTimeline', () => {
  beforeEach(() => {
    // 钉住时钟在午后:历日归属不随真实运行时刻漂
    vi.setSystemTime(new Date('2026-09-20T15:00:00'))
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('事件映射:执行/场景/适配各有文案与深链', async () => {
    const t = await loadWith({
      events: [
        execEvent(1, 'done', ago(1)), scenEvent('s1', ago(2)), batchEvent('b-new', ago(5)),
      ],
    })
    expect(t.status.value).toBe('ready')
    expect(t.events.value[0]!.title).toContain('执行 #1')
    expect(t.events.value[0]!.to).toContain('/executions/1')
    expect(t.events.value[1]!.title).toContain('更新场景 场景 s1')
    expect(t.events.value[1]!.to).toContain('/scenarios/s1/detail')
    expect(t.events.value[2]!.title).toContain('接口适配 v1 → v2')
    expect(t.events.value[2]!.to).toBe('/adaptations/batches/b-new')
  })

  it('常态只露最近 10 条,展开后给到池子', async () => {
    const t = await loadWith({
      events: Array.from({ length: 20 },
        (_, i) => execEvent(i + 1, 'done', ago(i + 1))) as never[],
    })
    expect(t.pooled.value).toHaveLength(20)
    expect(t.events.value).toHaveLength(10)          // 预览位
    expect(t.canExpand.value).toBe(true)
    t.toggleExpanded()
    expect(t.events.value).toHaveLength(20)
    t.toggleExpanded()
    expect(t.events.value).toHaveLength(10)
  })

  it('不足 10 条时不出现「查看更多」', async () => {
    const t = await loadWith({ events: [execEvent(1, 'done', ago(1))] })
    expect(t.canExpand.value).toBe(false)
  })

  it('按日历日分组:今天 / 昨天', async () => {
    const t = await loadWith({
      events: [execEvent(1, 'done', ago(1)), execEvent(2, 'done', ago(26))],
    })
    expect(t.days.value.map((g) => g.day)).toEqual(['今天', '昨天'])
    expect(t.days.value[1]!.events[0]!.title).toContain('执行 #2')
  })

  it('执行源挂掉 → 只丢执行类事件,其余照常上轴并标降级', async () => {
    const t = await loadWith({
      events: [scenEvent('s1', ago(2))],
      sources: { executions: false, scenarios: true, adaptations: true },
    })
    expect(t.events.value.map((e) => e.kind)).toEqual(['scenario'])
    expect(t.sources.exec).toBe(false)
    expect(t.degraded.value).toBe(true)
    expect(t.status.value).toBe('ready')       // 降级 ≠ 整块错误态
  })

  it('两源挂 + 成功源恰好为空 → error 态而不是假空态', async () => {
    const t = await loadWith({
      events: [],
      sources: { executions: false, scenarios: true, adaptations: false },
    })
    expect(t.sources.exec).toBe(false)
    expect(t.sources.adapt).toBe(false)
    expect(t.sources.scen).toBe(true)
    expect(t.status.value).toBe('error')
  })

  it('全源成功但无数据 → 空态(不是错误)', async () => {
    const t = await loadWith({ events: [] })
    expect(t.status.value).toBe('ready')
    expect(t.events.value).toHaveLength(0)
    expect(t.degraded.value).toBe(false)
  })

  it('颜色筛流:只看一类 / 换一类不叠加 / 再点同一颗取消', async () => {
    const t = await loadWith({
      events: [
        execEvent(1, 'done', ago(1)), execEvent(2, 'done', ago(2)),
        batchEvent('b1', ago(3)), scenEvent('s1', ago(4)),
      ],
    })
    expect(t.only.value).toBeNull()
    expect(t.counts.value).toEqual({ execution: 2, scenario: 1, adaptation: 1 })

    t.setOnly('execution')
    expect(t.visible.value.map((e) => e.kind)).toEqual(['execution', 'execution'])
    t.setOnly('adaptation')
    expect(t.visible.value.map((e) => e.kind)).toEqual(['adaptation'])
    t.setOnly('adaptation')
    expect(t.only.value).toBeNull()
    expect(t.visible.value).toHaveLength(4)
  })

  it('筛流改的是「可见池」:预览位与「查看更多」都跟着它走', async () => {
    const t = await loadWith({
      events: [
        ...Array.from({ length: 20 }, (_, i) => execEvent(i + 1, 'done', ago(i + 1))),
        batchEvent('b1', ago(1)),
      ],
    })
    expect(t.canExpand.value).toBe(true)
    t.toggleExpanded()
    expect(t.events.value).toHaveLength(21)
    // 展开态下换筛选条件 → 回到预览位,不停在半截长列表上
    t.setOnly('adaptation')
    expect(t.expanded.value).toBe(false)
    expect(t.events.value).toHaveLength(1)
    expect(t.canExpand.value).toBe(false)
  })

  it('重新取数后筛中的那一类一条不剩 → 自动撤筛', async () => {
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [execEvent(1, 'done', ago(1))],
      sources: { executions: true, scenarios: true, adaptations: true },
    } as never)
    const t = useActivityTimeline()
    await t.load()
    t.setOnly('execution')
    expect(t.visible.value).toHaveLength(1)

    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [],
      sources: { executions: false, scenarios: true, adaptations: true },
    } as never)
    await t.load()
    expect(t.counts.value.execution).toBe(0)
    expect(t.only.value).toBeNull()
  })
})
