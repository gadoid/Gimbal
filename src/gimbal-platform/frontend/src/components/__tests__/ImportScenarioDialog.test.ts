// ImportScenarioDialog.test.ts — 导入确认单状态机(场景导入 v2.3 §8/W5)。
// 三分支:fatal(只读「知道了」)/ 正常(映射行 + 认证引用栏 + newId 回传
// 口径)/ 409 自愈(自动重预检)。
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ImportScenarioDialog from '@/components/ImportScenarioDialog.vue'

const importPrecheck = vi.fn()
const importScenario = vi.fn()
vi.mock('@/api/scenario-import', () => ({
  importPrecheck: (...a: unknown[]) => importPrecheck(...a),
  importScenario: (...a: unknown[]) => importScenario(...a),
}))
vi.mock('@/api/auth_sessions', () => ({
  listAll: vi.fn().mockResolvedValue([{ alias: 'qa1' }]),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const bundle = { scenarioId: 'sc-x', meta: { name: 'X' }, steps: [], config: {} }

function pre(over: Record<string, unknown> = {}) {
  return {
    blocking: false,
    formatError: null,
    convert: { ok: true, errors: [] },
    metaPlate: { fin: '1.0#1' },
    availableRevisions: {},
    idConflict: true,
    suggestedId: 'sc-import-abc',
    services: [
      { serviceKey: 'fin-service', suggestion: 'map', localAlias: 'fin-service',
        fieldsToAlias: 1, fieldsKeptLiteral: 2, createNameAvailable: false,
        sensitivePaths: ['$.api_token'] },
      { serviceKey: 'qa-svc', suggestion: 'create', localAlias: null,
        fieldsToAlias: 1, fieldsKeptLiteral: 0, createNameAvailable: true,
        sensitivePaths: [] },
    ],
    authRefs: [{ tag: 'qa1', inMyPool: false }],
    workingDeclarations: [],
    ...over,
  }
}

function mountDialog() {
  return mount(ImportScenarioDialog, {
    props: { open: true, bundle },
    attachTo: document.body,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ImportScenarioDialog 状态机', () => {
  it('fatal:blocking 时只显示判定面,无确认按钮', async () => {
    importPrecheck.mockResolvedValue(pre({
      blocking: true,
      convert: { ok: false, errors: ['meta_plate_invalid_ref: fin=1.0#9 修订不存在'] },
      availableRevisions: { '1.0': ['1.0#1', '1.0#2'] },
    }))
    const w = mountDialog()
    await flushPromises()
    expect(w.find('[data-testid="import-fatal"]').exists()).toBe(true)
    expect(w.text()).toContain('1.0#1、1.0#2')          // 可用修订引导
    expect(w.find('[data-testid="import-confirm"]').exists()).toBe(false)
    w.unmount()
  })

  it('正常:映射行/认证引用栏渲染;确认走 newId 回传口径', async () => {
    importPrecheck.mockResolvedValue(pre())
    importScenario.mockResolvedValue({ scenarioId: 'sc-import-abc', idMode: 'new' })
    const w = mountDialog()
    await flushPromises()

    expect(w.find('[data-testid="import-svc-fin-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="import-authrefs"]').text()).toContain('你的凭证池没有')
    expect(w.find('[data-testid="import-id-zone"]').exists()).toBe(true)

    await w.find('[data-testid="import-confirm"]').trigger('click')
    await flushPromises()

    // 决策默认 = 建议(fin-service→map,qa-svc→create);newId = suggestedId
    // (P4/R7:展示即最终);敏感字段无值覆盖字段(P7-⑥)
    expect(importScenario).toHaveBeenCalledWith({
      bundle,
      mappings: [
        { serviceKey: 'fin-service', decision: 'map' },
        { serviceKey: 'qa-svc', decision: 'create' },
      ],
      idMode: 'new',
      newId: 'sc-import-abc',
    })
    expect(w.emitted('imported')?.[0]).toEqual(['sc-import-abc'])
    w.unmount()
  })

  it('409 自愈:scenario_id_exists → 自动重新预检', async () => {
    importPrecheck.mockResolvedValue(pre())
    importScenario.mockRejectedValueOnce({
      response: { data: { detail: { code: 'scenario_id_exists' } } },
    })
    const w = mountDialog()
    await flushPromises()
    await w.find('[data-testid="import-confirm"]').trigger('click')
    await flushPromises()

    expect(importScenario).toHaveBeenCalledTimes(1)
    expect(importPrecheck).toHaveBeenCalledTimes(2)   // 409 后自动重预检
    expect(w.find('[data-testid="import-confirm"]').exists()).toBe(true)
    w.unmount()
  })
})
