/**
 * CollapsedTopbar — 编辑流页统一面包屑(Phase 1 骨架规范强制条)。
 *
 * 契约:
 * - /composer/:id → 场景库 / <场景名||id>(→场景详情)/ 编排;
 *   面包屑场景名与 CaseComposer.crumb 同款(name-first,id 兜底);
 * - /constants → 工作台 / 常量池(深链来源,见 F-sitemap);
 * - 末段不可点,中间层级可点;未匹配路由不出面包屑。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CollapsedTopbar from '@/components/chrome/CollapsedTopbar.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

function scenario(name: string): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name,
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: [],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 0,
    tags: [],
  }
}

// 模块级 route mock,按用例改写
const mockRoute: { path: string; params: Record<string, string> } = {
  path: '/composer/sc-demo',
  params: { scenarioId: 'sc-demo' },
}

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn() }),
  }
})

vi.mock('@/api/scenario-composer', () => ({
  getScenario: vi.fn(),
}))

function mountBar() {
  return mount(CollapsedTopbar, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('CollapsedTopbar — 统一面包屑', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockRoute.path = '/composer/sc-demo'
    mockRoute.params = { scenarioId: 'sc-demo' }
    vi.mocked(api.getScenario).mockResolvedValue(scenario('订单创建 e2e'))
  })

  it('编排页:场景库 / 场景名(→场景详情)/ 编排,末段不可点', async () => {
    const w = mountBar()
    await flushPromises()
    const links = w.findAll('a.crumb-link')
    expect(links.map((l) => l.text())).toEqual(['场景库', '订单创建 e2e'])
    expect(links[0].attributes('href')).toBe('/scenarios')
    expect(links[1].attributes('href')).toBe('/scenarios/sc-demo/detail')
    expect(w.find('.crumb-current').text()).toBe('编排')
    w.unmount()
  })

  it('未命名场景回退 scenarioId(crumb 契约与 composer 一致)', async () => {
    // 独立 scenarioId:名称缓存按 id 记,避免与上一用例串话
    mockRoute.params = { scenarioId: 'sc-plain' }
    vi.mocked(api.getScenario).mockResolvedValue(scenario(''))
    const w = mountBar()
    await flushPromises()
    expect(w.findAll('a.crumb-link')[1].text()).toBe('sc-plain')
    w.unmount()
  })

  it('/composer/new 新建草稿:中间段「新建场景」不可点,且不发起取名请求', async () => {
    mockRoute.path = '/composer/new'
    mockRoute.params = { scenarioId: 'new' }
    const w = mountBar()
    await flushPromises()
    // 可点段只剩「场景库」;不可点段 = 新建场景 + 末段编排
    expect(w.findAll('a.crumb-link').map((l) => l.text())).toEqual(['场景库'])
    expect(w.findAll('.crumb-current').map((s) => s.text())).toEqual(['新建场景', '编排'])
    // 不对 'new' 发 getScenario(404 噪声归零)
    expect(api.getScenario).not.toHaveBeenCalledWith('new')
    w.unmount()
  })

  it('方案工作台页:末段「方案」', async () => {
    mockRoute.path = '/scenarios/sc-demo/schemes'
    const w = mountBar()
    await flushPromises()
    expect(w.find('.crumb-current').text()).toBe('方案')
    w.unmount()
  })

  it('常量池:工作台 / 常量池(不出现「场景库」)', async () => {
    mockRoute.path = '/constants'
    mockRoute.params = {}
    const w = mountBar()
    await flushPromises()
    const links = w.findAll('a.crumb-link')
    expect(links.map((l) => l.text())).toEqual(['工作台'])
    expect(links[0].attributes('href')).toBe('/home')
    expect(w.find('.crumb-current').text()).toBe('常量池')
    w.unmount()
  })

  it('品牌信号点在场(收拢后唯一带走的身份符号)', () => {
    const w = mountBar()
    expect(w.find('.status-dot').exists()).toBe(true)
    expect(w.find('.brand-text').text()).toBe('platform')
    w.unmount()
  })
})
