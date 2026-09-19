/**
 * useActivityTimeline — 右栏时间线的取数归一。
 * 钉住:三源合流后按时间倒序 + 截断、日历日分组、单源失败只丢该类事件、
 * member 的 403 是"确定性空集"而非降级、无时间戳的排队执行不进轴、
 * 公共原件的改动不算我的活动、场景事件有入池上限(否则刷满整轴)、
 * 卡头的颜色筛流是"单选可取消"且与预览位/展开态互不遗留。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useActivityTimeline } from '@/composables/useActivityTimeline'
import { ApiError } from '@/api/http'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import * as executionsApi from '@/api/executions'
import * as adaptationsApi from '@/api/adaptations'
import * as composerApi from '@/api/scenario-composer'

vi.mock('@/api/executions', () => ({ listExecutions: vi.fn() }))
vi.mock('@/api/adaptations', () => ({ listBatches: vi.fn() }))
vi.mock('@/api/scenario-composer', () => ({ listScenarios: vi.fn().mockResolvedValue([]) }))

const DAY = 86_400_000
const ago = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString()

const exec = (id: number, status: string, at: string | null, scenario = 'sc-a') => ({
  id, scenario_id: scenario, status, total_runs: 1, passed: 1, failed: 0,
  started_at: at, finished_at: at, config: {},
}) as never

const batch = (id: string, at: string, over = {}) => ({
  batchId: id, endpointId: 'fin.pay.create', fromVersion: 'v1', toVersion: 'v2',
  status: 'completed', operatorId: 1, createdAt: at, closedAt: at, opCounts: { api: 2 }, ...over,
}) as never

function scen(id: string, vis: 'private' | 'public', at: string) {
  return {
    meta: {
      scenarioId: id, name: `场景 ${id}`, module: 'm', priority: 1, author: 'Alice',
      owner: 'Alice', tags: [], system: [], updateTime: at,
    },
    steps: [], config: { vars: {} }, tags: [], starred: false, visibility: vis,
  } as never
}

async function loadWith(data: {
  exec?: Awaited<ReturnType<typeof listExecutionsShim>> | Error
  adapt?: unknown[] | Error
  scenarios?: never[]
}) {
  if (data.scenarios) {
    vi.mocked(composerApi.listScenarios).mockResolvedValue(data.scenarios as never)
  }
  if (data.exec instanceof Error) {
    vi.mocked(executionsApi.listExecutions).mockRejectedValue(data.exec)
  } else {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({ total: 0, items: data.exec ?? [] } as never)
  }
  if (data.adapt instanceof Error) {
    vi.mocked(adaptationsApi.listBatches).mockRejectedValue(data.adapt)
  } else {
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue((data.adapt ?? []) as never)
  }
  const t = useActivityTimeline()
  await t.load()
  return t
}

// 仅为上面签名服务,不参与运行时
function listExecutionsShim() { return [] as never[] }

describe('useActivityTimeline', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useScenarioComposerStore().scenariosLoaded = false
    vi.clearAllMocks()
    vi.mocked(composerApi.listScenarios).mockResolvedValue([] as never)
  })

  it('三源合流按时间倒序', async () => {
    const t = await loadWith({
      exec: [exec(1, 'done', ago(1)), exec(2, 'failed', ago(30))],
      adapt: [batch('b-new', ago(5)), batch('b-old', ago(200))],
      scenarios: [scen('s1', 'private', ago(2))],
    })
    expect(t.status.value).toBe('ready')
    expect(t.events.value.map((e) => e.kind))
      .toEqual(['execution', 'scenario', 'adaptation', 'execution', 'adaptation'])
    expect(t.events.value[0]!.title).toContain('执行 #1')
    expect(t.events.value[1]!.to).toContain('/scenarios/s1/detail')
    expect(t.events.value[2]!.to).toBe('/adaptations/batches/b-new')
  })

  it('常态只露最近 10 条,展开后给到池子', async () => {
    const t = await loadWith({
      exec: Array.from({ length: 20 }, (_, i) => exec(i + 1, 'done', ago(i + 1))),
    })
    expect(t.pooled.value).toHaveLength(20)
    expect(t.events.value).toHaveLength(10)          // 预览位
    expect(t.canExpand.value).toBe(true)
    expect(t.expanded.value).toBe(false)

    t.toggleExpanded()
    expect(t.events.value).toHaveLength(20)
    expect(t.expanded.value).toBe(true)
    t.toggleExpanded()
    expect(t.events.value).toHaveLength(10)
  })

  it('池子不超过 30 条(右栏是速览,不是执行历史页)', async () => {
    const t = await loadWith({
      exec: Array.from({ length: 20 }, (_, i) => exec(i + 1, 'done', ago(i + 1))),
      adapt: Array.from({ length: 20 }, (_, i) => batch(`b${i}`, ago(i + 1))),
      scenarios: Array.from({ length: 20 }, (_, i) => scen(`s${i}`, 'private', ago(i + 1))) as never[],
    })
    // 20 执行 + 10 适配(源上限)+ 10 场景(入池上限)= 40 合流 → 截到 30
    expect(t.pooled.value).toHaveLength(30)
    expect(t.canExpand.value).toBe(true)
  })

  it('不足 10 条时不出现「查看更多」', async () => {
    const t = await loadWith({ exec: [exec(1, 'done', ago(1))] })
    expect(t.canExpand.value).toBe(false)
  })

  it('按日历日分组:今天 / 昨天', async () => {
    const t = await loadWith({
      exec: [exec(1, 'done', ago(1)), exec(2, 'done', ago(26))],
    })
    expect(t.days.value.map((g) => g.day)).toEqual(['今天', '昨天'])
    expect(t.days.value[1]!.events[0]!.title).toContain('执行 #2')
  })

  it('执行源挂掉 → 只丢执行类事件,其余照常上轴并标降级', async () => {
    const t = await loadWith({
      exec: new Error('boom'),
      scenarios: [scen('s1', 'private', ago(2))],
    })
    expect(t.events.value.map((e) => e.kind)).toEqual(['scenario'])
    expect(t.sources.exec).toBe(false)
    expect(t.degraded.value).toBe(true)
    expect(t.status.value).toBe('ready')       // 降级 ≠ 整块错误态
  })

  it('member 的 403 是确定性空集:不算降级(否则右栏常年挂着警示)', async () => {
    const t = await loadWith({
      exec: [exec(1, 'done', ago(1))],
      adapt: new ApiError(403, 403, 'forbidden'),
    })
    expect(t.sources.adapt).toBe(true)
    expect(t.degraded.value).toBe(false)
    expect(t.events.value.map((e) => e.kind)).toEqual(['execution'])
  })

  it('排队中且无时间戳的执行不进轴(无处安放的时间点)', async () => {
    const t = await loadWith({ exec: [exec(7, 'queued', null), exec(8, 'done', ago(1))] })
    expect(t.events.value.map((e) => e.title)).toEqual(['执行 #8 完成'])
  })

  it('公共原件的改动不是「我的活动」;场景事件入池最多 10 条(取最新更新)', async () => {
    const many = Array.from({ length: 14 }, (_, i) => scen(`s${i}`, 'private', ago(i + 1)))
    const t = await loadWith({
      exec: [],
      scenarios: [...many, scen('pub', 'public', ago(0.5))] as never[],
    })
    const scenEvents = t.pooled.value.filter((e) => e.kind === 'scenario')
    expect(scenEvents).toHaveLength(10)
    expect(scenEvents.map((e) => e.title)).not.toContain('更新场景 场景 pub')
    expect(scenEvents[0]!.title).toContain('s0')          // 最新的一条
    expect(scenEvents[9]!.title).toContain('s9')          // 第 11 新往后的丢掉
  })

  it('两源挂 + 成功源恰好为空 → 无从判断,给 error 态而不是假空态', async () => {
    const broken = await loadWith({
      exec: new Error('boom'), adapt: new Error('boom'), scenarios: [] as never[],
    })
    expect(broken.sources.exec).toBe(false)
    expect(broken.sources.adapt).toBe(false)
    expect(broken.sources.scen).toBe(true)
    expect(broken.status.value).toBe('error')       // 空 ≠ 真没有活动
  })

  it('全源成功但无数据 → 空态(不是错误)', async () => {
    const empty = await loadWith({ exec: [], adapt: [] })
    expect(empty.status.value).toBe('ready')
    expect(empty.events.value).toHaveLength(0)
    expect(empty.degraded.value).toBe(false)
  })

  it('颜色筛流:只看一类 / 换一类不叠加 / 再点同一颗取消', async () => {
    const t = await loadWith({
      exec: [exec(1, 'done', ago(1)), exec(2, 'done', ago(2))],
      adapt: [batch('b1', ago(3))],
      scenarios: [scen('s1', 'private', ago(4))],
    })
    expect(t.only.value).toBeNull()
    expect(t.counts.value).toEqual({ execution: 2, scenario: 1, adaptation: 1 })

    t.setOnly('execution')
    expect(t.visible.value.map((e) => e.kind)).toEqual(['execution', 'execution'])
    expect(t.days.value).toHaveLength(1)                    // 筛后重新分组
    t.setOnly('adaptation')
    expect(t.visible.value.map((e) => e.kind)).toEqual(['adaptation'])
    t.setOnly('adaptation')
    expect(t.only.value).toBeNull()
    expect(t.visible.value).toHaveLength(4)
  })

  it('筛流改的是「可见池」:预览位与「查看更多」都跟着它走', async () => {
    const t = await loadWith({
      exec: Array.from({ length: 20 }, (_, i) => exec(i + 1, 'done', ago(i + 1))),
      adapt: [batch('b1', ago(1))],
    })
    expect(t.canExpand.value).toBe(true)
    t.toggleExpanded()
    expect(t.events.value).toHaveLength(21)
    // 展开态下换筛选条件 → 回到预览位,不停在半截长列表上
    t.setOnly('adaptation')
    expect(t.expanded.value).toBe(false)
    expect(t.events.value).toHaveLength(1)
    expect(t.canExpand.value).toBe(false)                   // 筛后不足 10 条,不该再有出口
  })

  it('重新取数后筛中的那一类一条不剩 → 自动撤筛(空轴看着会像"没活动")', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({ total: 1, items: [exec(1, 'done', ago(1))] } as never)
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([] as never)
    const t = useActivityTimeline()
    await t.load()
    t.setOnly('execution')
    expect(t.visible.value).toHaveLength(1)

    vi.mocked(executionsApi.listExecutions).mockRejectedValue(new Error('boom'))
    await t.load()
    expect(t.counts.value.execution).toBe(0)
    expect(t.only.value).toBeNull()
  })
})
