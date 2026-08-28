/**
 * CaseComposer — 面包屑场景标识显示 name(零获取:definition 在手)。
 *
 * 契约:crumb 的 scenarioId span 从裸 id 改为 `meta.name || id`
 * (未命名场景回退 id;URL/深链仍用 id,不在契约内)。
 * 建件/mock 结构抄 CaseComposer.run.test.ts(vue-router mock +
 * constants/auth/executions factory mock + getScenario spyOn)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn().mockResolvedValue(undefined) }),
  }
})
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))

function scenario(over: Partial<Scenario['meta']>): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
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
      ...over,
    },
    steps: [{ api: { service: 'fin-service', method: 'POST', path: '/x' } }] as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

function mountPage() {
  // stubs 与 run.test.ts 同款:teleport 收弹层 + popper 类组件防 jsdom 递归爆表
  return mount(CaseComposer, {
    global: {
      plugins: [ElementPlus, createPinia()],
      stubs: { teleport: true, ScenarioExportMenu: true, CaseComposerMeta: true },
    },
  })
}

describe('CaseComposer — 面包屑显示场景 name', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('有 name 时面包屑显示 name 而非 id', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(scenario({}))
    const w = mountPage()
    await flushPromises()

    expect(w.find('.crumb .scenario-id').text()).toBe('订单创建 e2e')
    w.unmount()
  })

  it('未命名(name 为空)回退显示 scenarioId', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(scenario({ name: '' }))
    const w = mountPage()
    await flushPromises()

    expect(w.find('.crumb .scenario-id').text()).toBe('sc-demo')
    w.unmount()
  })
})
