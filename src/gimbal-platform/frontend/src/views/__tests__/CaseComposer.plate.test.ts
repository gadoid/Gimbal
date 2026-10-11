/**
 * CaseComposer — 水合保留 meta.plate(2026-10-12 自举导出失效根因回归)。
 *
 * 契约:loadScenario 重建 definition.meta 时先整份铺开读侧 meta 再覆盖
 * 编排器管理的字段 —— meta.plate(版本声明)必须原样进草稿。丢了它:
 * 锚点步骤的 call(Release 6.2 已剥离派生字段)在 /convert 直通校验
 * 必炸(「scenario payload failed validation … call.protocol Field
 * required」),保存还会把无版本声明的损坏写回库。
 * 建件/mock 结构抄 CaseComposer.crumb.test.ts。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import CaseComposer from '@/views/CaseComposer.vue'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-boot-demo' },
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
  listAll: vi.fn(() => Promise.resolve(vi.fn(() => Promise.resolve([])))),
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))

function scenario(): Scenario {
  return {
    meta: {
      scenarioId: 'sc-boot-demo',
      name: '自举-适配链路',
      description: '',
      module: 'self-bootstrap',
      priority: 1,
      author: 'sb',
      owner: 'sb',
      tags: [],
      system: ['platform'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
      // 读侧 meta 携带版本声明(自举场景钉 working;业务场景钉精确修订)
      plate: { platform: 'working' },
    },
    // 锚点步骤 + 6.2 存储形态 call(无派生字段)
    steps: [{
      kind: 'step',
      endpoint: 'platform.auth.post_login',
      call: { kind: 'call', service: 'platform-service', headers: {} },
      request: { kind: 'request', body: {} },
      strategy: [],
    }] as Scenario['steps'],
    orchestration: { steps: [{ enabled: true, name: '' }], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

function mountPage() {
  return mount(CaseComposer, {
    global: {
      plugins: [createPinia()],
      stubs: { teleport: true, ScenarioExportMenu: true, CaseComposerMeta: true },
    },
  })
}

describe('CaseComposer — 水合保留 meta.plate', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('读侧 meta.plate 进草稿定义(丢它 = 锚点步骤 convert 必炸)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(scenario())
    const w = mountPage()
    await flushPromises()

    const store = useScenarioDraftStore()
    expect(store.draft?.definition.meta.plate)
      .toEqual({ platform: 'working' })
    // 锚点与存储形态 call 同样原样进草稿(供导出/保存走投影)
    expect(store.draft?.definition.steps[0].endpoint)
      .toBe('platform.auth.post_login')
    w.unmount()
  })

  it('读侧无 meta.plate 时草稿也不凭空造(过渡形态原样)', async () => {
    const s = scenario()
    delete (s.meta as Record<string, unknown>).plate
    vi.spyOn(api, 'getScenario').mockResolvedValue(s)
    const w = mountPage()
    await flushPromises()

    const store = useScenarioDraftStore()
    expect(store.draft?.definition.meta.plate).toBeUndefined()
    w.unmount()
  })
})
