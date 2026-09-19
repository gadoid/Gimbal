/**
 * ScenariosPublic — 公共场景页数据接线回归。
 * 钉住:public 分桶、名称/菜单两条详情入口(定义只读但必须可读)、
 * 执行走「数据集全集 + 无 schemeId」、复制到我的、被复制列如实留白、
 * 关注上限给一句人话而不是通用错误兜底。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ScenariosPublic from '@/views/ScenariosPublic.vue'
import * as composerApi from '@/api/scenario-composer'
import { toastState } from '@/utils/toast'
import type { Scenario } from '@/types/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue([]),
  listDataSets: vi.fn().mockResolvedValue([{ datasetId: 'd1' }, { datasetId: 'd2' }]),
  runScenario: vi.fn().mockResolvedValue({ runId: 'r-1' }),
  copyScenario: vi.fn(),
  starScenario: vi.fn().mockResolvedValue(undefined),
}))

function scen(id: string, vis: 'private' | 'public'): Scenario {
  return {
    meta: {
      scenarioId: id, name: id, description: '', module: 'm', priority: 1,
      author: 'Bob', owner: 'Bob', tags: [], system: ['fin'], updateTime: '2026-09-15T15:13:00',
    },
    steps: [], config: { vars: {} }, dataSetCount: 0, stepCount: 1, schemeCount: 0,
    tags: [], starred: false, visibility: vis,
  } as unknown as Scenario
}

let router: Router

function mountPage(scenarios: Scenario[]): VueWrapper {
  vi.mocked(composerApi.listScenarios).mockResolvedValue(scenarios)
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/public', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
  return mount(ScenariosPublic, {
    global: {
      plugins: [router],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        DropdownMenu: { template: '<div><slot /></div>' },
        DropdownMenuTrigger: { template: '<button><slot /></button>' },
        DropdownMenuContent: { template: '<div><slot /></div>' },
        DropdownMenuItem: { template: '<div><slot /></div>' },
        FilterPopover: { template: '<div/>' },
      },
    },
  })
}

const menuItem = (w: VueWrapper, text: string) =>
  w.findAll('.sl-menu-item').find((i) => i.text().includes(text))!

describe('ScenariosPublic — 公共场景页', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastState.items.splice(0, toastState.items.length)
  })

  it('只列 public 桶;私有场景不得混进来', async () => {
    const w = mountPage([scen('sc-p1', 'public'), scen('sc-mine', 'private'), scen('sc-p2', 'public')])
    await flushPromises()
    expect(w.text()).toContain('sc-p1')
    expect(w.text()).toContain('sc-p2')
    expect(w.text()).not.toContain('sc-mine')
    w.unmount()
  })

  it('没有「+ 新建场景」入口(有数据 / 空态都没有)', async () => {
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    expect(w.find('.slib-create').exists()).toBe(false)
    w.unmount()

    const empty = mountPage([])
    await flushPromises()
    expect(empty.find('.slib-create').exists()).toBe(false)
    empty.unmount()
  })

  it('点名称跳详情页:公共定义只读,但必须有读入口', async () => {
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    await w.find('[data-testid="pub-name-sc-p1"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/scenarios/sc-p1/detail')
    w.unmount()
  })

  it('⋯ 菜单第一项是「查看详情」,执行/复制到我的仍在', async () => {
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    expect(w.findAll('.sl-menu-item').map((i) => i.text())).toEqual(['查看详情', '执行', '复制到我的'])
    await menuItem(w, '查看详情').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/scenarios/sc-p1/detail')
    w.unmount()
  })

  it('「执行」= 该场景数据集全集 + 不带 schemeId(验证执行,不套方案)', async () => {
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    await menuItem(w, '执行').trigger('click')
    await flushPromises()
    expect(composerApi.listDataSets).toHaveBeenCalledWith({ scenarioId: 'sc-p1' })
    expect(composerApi.runScenario).toHaveBeenCalledWith({
      scenarioId: 'sc-p1', dataSetIds: ['d1', 'd2'],
    })
    expect(vi.mocked(composerApi.runScenario).mock.calls[0][0]).not.toHaveProperty('schemeId')
    w.unmount()
  })

  it('「复制到我的」落 copyScenario 并把新副本提示出来', async () => {
    vi.mocked(composerApi.copyScenario).mockResolvedValue(scen('sc-copy-1', 'private') as never)
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    await menuItem(w, '复制到我的').trigger('click')
    await flushPromises()
    expect(composerApi.copyScenario).toHaveBeenCalledWith('sc-p1')
    expect(toastState.items.some((t) => t.kind === 'success' && t.message.includes('sc-copy-1'))).toBe(true)
    w.unmount()
  })

  it('被复制列如实留白,表头 title 说明原因(不做估算)', async () => {
    const w = mountPage([scen('sc-p1', 'public')])
    await flushPromises()
    const th = w.findAll('th').find((t) => t.text() === '被复制')!
    expect(th.attributes('title')).toContain('后端暂无复制次数字段')
    expect(w.find('tbody tr').text()).toContain('—')
    w.unmount()
  })

  it('关注超上限 → 一句人话提示,不是通用错误兜底', async () => {
    const many = Array.from({ length: 20 }, (_, i) => {
      const s = scen(`f-${i}`, 'public')
      ;(s as { starred: boolean }).starred = true
      return s
    })
    // sc-p1 排首位:它是唯一未关注的行,★ 才会走「加关注」分支
    const w = mountPage([scen('sc-p1', 'public'), ...many])
    await flushPromises()
    await w.find('.star-btn').trigger('click')
    await flushPromises()
    const msg = toastState.items.find((t) => t.kind === 'error')?.message || ''
    expect(msg).toContain('关注上限 20')
    expect(composerApi.starScenario).not.toHaveBeenCalled()
    w.unmount()
  })
})
