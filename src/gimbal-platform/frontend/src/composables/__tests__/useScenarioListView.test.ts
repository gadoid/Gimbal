/**
 * useScenarioListView — 三页共用的列表骨架。
 * 钉住:分桶谓词互补(卡与页计数同源)、搜索字段覆盖 tags/system、
 * 结果集缩小时页码自动钳回(否则停在空白页)、"筛空 vs 真无"判定、
 * 取数失败要冒泡成一句提示(store 吞异常,不 reject)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useScenarioListView } from '@/composables/useScenarioListView'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { toastState } from '@/utils/toast'
import * as composerApi from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue([]),
}))

const isPublic = (r: { visibility?: string }) => r.visibility === 'public'
const isMine = (r: { visibility?: string }) => !isPublic(r)

function scen(i: number, vis: 'private' | 'public'): Scenario {
  return {
    meta: {
      scenarioId: `sc-${i}`, name: `场景 ${i}`, description: '', module: '支付',
      priority: 1, author: 'Alice', owner: 'Alice', tags: [`t${i}`], system: ['fin'],
      updateTime: '2026-09-15T15:13:00',
    },
    steps: [], config: { vars: {} }, tags: [`t${i}`], starred: false, visibility: vis,
  } as unknown as Scenario
}

function seed(list: Scenario[]) {
  const store = useScenarioComposerStore()
  store.scenarios = list
  return store
}

describe('useScenarioListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastState.items.splice(0, toastState.items.length)
  })

  it('两个谓词把同一份列表切成互补的两桶,不重不漏', () => {
    seed([scen(1, 'private'), scen(2, 'public'), scen(3, 'private'), scen(4, 'public')])
    const mine = useScenarioListView(isMine)
    const pub = useScenarioListView(isPublic)
    expect(mine.total.value).toBe(2)
    expect(pub.total.value).toBe(2)
    expect(mine.rows.value.map((r) => r.meta.scenarioId)).toEqual(['sc-1', 'sc-3'])
    expect(pub.rows.value.map((r) => r.meta.scenarioId)).toEqual(['sc-2', 'sc-4'])
  })

  it('摊平行带上筛选层认得的键,FilterPopover 才能按 module/author/系统取值', () => {
    seed([scen(1, 'private')])
    const v = useScenarioListView(isMine)
    const row = v.filterableRows.value[0]!
    expect(row.module).toBe('支付')
    expect(row.author).toBe('Alice')
    expect(row.updated_at).toBe('2026-09-15T15:13:00')
    expect(row.system).toEqual(['fin'])
  })

  it('搜索命中名称 / scenarioId / tag(大小写无关)', async () => {
    seed([scen(1, 'private'), scen(2, 'private')])
    const v = useScenarioListView(isMine)
    v.q.value = '场景 2'
    expect(v.rows.value.map((r) => r.meta.scenarioId)).toEqual(['sc-2'])
    v.q.value = 'T1'
    expect(v.rows.value.map((r) => r.meta.scenarioId)).toEqual(['sc-1'])
    v.q.value = '   '
    expect(v.rows.value).toHaveLength(2)
    await flushPromises()
  })

  it('每页 20 条;结果集缩小时页码钳回最后一页,不留空白页', async () => {
    seed(Array.from({ length: 25 }, (_, i) => scen(i, 'private')))
    const v = useScenarioListView(isMine)
    expect(v.pageCount.value).toBe(2)
    v.page.value = 2
    expect(v.paged.value).toHaveLength(5)
    expect(v.paged.value[0]!.meta.scenarioId).toBe('sc-20')

    // 越界:筛到只剩 1 条,仍停在第 2 页 → 会渲染空表
    v.q.value = '场景 24'
    expect(v.total.value).toBe(1)
    await flushPromises()
    expect(v.page.value).toBe(1)
    expect(v.paged.value).toHaveLength(1)
  })

  it('filtering 区分「筛空了」和「本来就什么都没有」', () => {
    seed([])
    const v = useScenarioListView(isMine)
    expect(v.filtering.value).toBe(false)
    v.q.value = 'x'
    expect(v.filtering.value).toBe(true)
    v.q.value = ''
    v.filters.value = { ...v.filters.value, modules: ['支付'] }
    expect(v.filtering.value).toBe(true)
  })

  it('取数失败 → 冒泡成「加载场景失败」提示(store 吞异常不 reject)', async () => {
    vi.mocked(composerApi.listScenarios).mockRejectedValueOnce(new Error('502'))
    const v = useScenarioListView(isMine)
    await v.load()
    await flushPromises()
    expect(v.store.scenariosStatus).toBe('error')
    expect(toastState.items.some((t) => t.kind === 'error' && t.message.includes('加载场景失败: 502'))).toBe(true)
  })
})
