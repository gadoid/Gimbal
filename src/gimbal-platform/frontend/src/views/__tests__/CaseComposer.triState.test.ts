/**
 * CaseComposer — W11 三态:未接入服务保存告警(2026-10-12)。
 *
 * 契约:无锚步骤的 call.service 落 unknown 桶(GET /service-aliases/classify)
 * 时,手动保存弹出非阻断告警(提示登记 external 或接入 plate),保存
 * 本身照常进行;自动保存不弹。读面失败 → 静默退场,不挡保存。
 * 建件/mock 结构抄 CaseComposer.plate.test.ts。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import * as aliasApi from '@/api/service-aliases'
import { toast } from '@/utils/toast'
import type { Scenario } from '@/types/scenario-composer'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-tri-demo' },
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
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
  listAll: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))
// 手动保存的引用者提示走动态 import('@/api/shares') —— 不 mock 的话
// jsdom XHR 挂起,保存停在 await 上永远到不了 update(autosave 测试走
// 自动路径绕开了这一段)。
vi.mock('@/api/shares', () => ({
  listScenarioReferrers: vi.fn(() => Promise.resolve({ items: [] })),
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
  promptAction: vi.fn(async () => null),
}))

function scenario(): Scenario {
  return {
    meta: {
      scenarioId: 'sc-tri-demo',
      name: '三态告警',
      description: '',
      module: 'tri',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
      plate: { fin: '1.0#1' },
    },
    // ① 锚定步骤(受管,pinned) ② 无锚步骤挂 unknown 服务 ③ 无锚步骤挂 external
    steps: [
      { kind: 'step', endpoint: 'fin.order.add',
        call: { kind: 'call', service: 'fin-service', headers: {} },
        request: { kind: 'request', body: {} }, strategy: [] },
      { kind: 'step',
        call: { kind: 'call', service: 'ghost-svc', method: 'POST',
                path: '/g', headers: {} },
        request: { kind: 'request', body: {} }, strategy: [] },
      { kind: 'step',
        call: { kind: 'call', service: 'pay-service', method: 'POST',
                path: '/p', headers: {} },
        request: { kind: 'request', body: {} }, strategy: [] },
    ] as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 3,
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

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'getScenario').mockResolvedValue(scenario())
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({} as never)
  vi.spyOn(api, 'listDataSets').mockResolvedValue([] as never)
  vi.spyOn(aliasApi, 'classifyServices').mockResolvedValue({
    plate: [], external: ['pay-service'], unknown: ['ghost-svc'],
  })
})

describe('CaseComposer — 未接入服务保存告警(W11)', () => {
  it('unknown 服务 → 手动保存弹非阻断告警,保存照常', async () => {
    const update = vi.fn().mockResolvedValue(scenario())
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = mountPage()
    await flushPromises()

    // 挂载即按无锚服务键集拉分类(锚定 fin 不进键集)
    expect(aliasApi.classifyServices).toHaveBeenCalledWith(
      ['ghost-svc', 'pay-service'])

    await w.find('button.primary-btn.outline').trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)          // 告警不阻断保存
    const warned = toast.warning as ReturnType<typeof vi.fn>
    expect(warned).toHaveBeenCalled()
    const first = warned.mock.calls[0][0] as { message: string }
    expect(first.message).toContain('ghost-svc')
    expect(first.message).toContain('未接入')
    // external 服务不进告警名单
    expect(first.message).not.toContain('pay-service')
    w.unmount()
  })

  it('分类读面失败 → 静默退场:不告警、不挡保存', async () => {
    vi.spyOn(aliasApi, 'classifyServices').mockRejectedValue(new Error('down'))
    const update = vi.fn().mockResolvedValue(scenario())
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = mountPage()
    await flushPromises()

    await w.find('button.primary-btn.outline').trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    const warned = (toast.warning as ReturnType<typeof vi.fn>).mock.calls
      .filter((c) => String((c[0] as { message?: string })?.message ?? c[0])
        .includes('未接入'))
    expect(warned).toHaveLength(0)
    w.unmount()
  })
})
