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
        fieldsToAlias: 0, fieldsKeptLiteral: 3, createNameAvailable: false,
        countsByDecision: {
          map: { fieldsToAlias: 0, fieldsKeptLiteral: 3 },
          create: { fieldsToAlias: 2, fieldsKeptLiteral: 1 },
          reuse: { fieldsToAlias: 0, fieldsKeptLiteral: 3 },
        },
        inconsistentPaths: [], sensitivePaths: ['$.api_token'] },
      { serviceKey: 'qa-svc', suggestion: 'create', localAlias: null,
        fieldsToAlias: 1, fieldsKeptLiteral: 0, createNameAvailable: true,
        inconsistentPaths: [], sensitivePaths: [] },
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

  it('取值不一致:保留字面值列标注 + 表下列出路径(§1 修复)', async () => {
    importPrecheck.mockResolvedValue(pre({
      services: [
        { serviceKey: 'fin-service', suggestion: 'map', localAlias: 'fin-service',
          fieldsToAlias: 0, fieldsKeptLiteral: 1, createNameAvailable: false,
          inconsistentPaths: ['$.remark'], sensitivePaths: [] },
      ],
    }))
    const w = mountDialog()
    await flushPromises()
    const row = w.find('[data-testid="import-svc-fin-service"]')
    expect(row.text()).toContain('取值不一致 1')
    const warn = w.find('[data-testid="import-inconsistent"]')
    expect(warn.exists()).toBe(true)
    expect(warn.text()).toContain('fin-service $.remark')
    expect(warn.text()).toContain('保留文件里的原值')
    w.unmount()
  })

  it('计数按当前决策显示:切到新建后交别名数随之变化(复盘 2026-10-15)', async () => {
    importPrecheck.mockResolvedValue(pre())
    const w = mountDialog()
    await flushPromises()
    const row = () => w.find('[data-testid="import-svc-fin-service"]')
    // 默认 = 建议 map:本机无值 → 交别名 0
    expect(row().text()).toMatch(/0/)
    // 切到新建:create 接管非敏感一致路径 → 交别名 2(保留 1)
    await row().find('input[value="create"]').trigger('change')
    await flushPromises()
    const tds = row().findAll('td')
    expect(tds[2].text()).toBe('2')
    expect(tds[3].text()).toContain('1')
    w.unmount()
  })

  it('锚定提示:未锚步骤列原因与 carry 降级后果;已锚只给计数(#323 前端补)', async () => {
    importPrecheck.mockResolvedValue(pre({
      anchoring: {
        anchored: [
          { index: 1, service: 'fin-service', method: 'POST', path: '/ok',
            endpoint: 'fin.ok', reason: null },
        ],
        unresolved: [
          // 漂移条目:endpoint 带被拒候选 —— 展示为排查信息,不是已锚
          { index: 0, service: 'fin-service', method: 'POST',
            path: '/api/order/orderEntrust/orderPage',
            endpoint: 'fin.order_entrust.order_page',
            reason: 'not_in_revision' },
          { index: 2, service: null, method: 'GET', path: '/x',
            endpoint: null, reason: 'not_in_catalog' },
        ],
      },
    }))
    const w = mountDialog()
    await flushPromises()
    const sec = w.find('[data-testid="import-anchoring"]')
    expect(sec.exists()).toBe(true)
    expect(sec.text()).toContain('已回填锚点 1 步')
    expect(sec.text()).toContain('步骤1')                     // index 0 → 步骤1
    expect(sec.text()).toContain('/api/order/orderEntrust/orderPage')
    expect(sec.text()).toContain('钉定修订内 method/path 已漂移')
    expect(sec.text()).toContain('working 曾命中 fin.order_entrust.order_page')
    expect(sec.text()).toContain('carry 降级注入')
    expect(sec.text()).toContain('步骤3')                     // index 2
    expect(sec.text()).toContain('端点清单中无匹配')
    w.unmount()
  })

  it('锚定提示:无可锚步骤时区块不出现(旧负载缺省同)', async () => {
    importPrecheck.mockResolvedValue(
      pre({ anchoring: { anchored: [], unresolved: [] } }))
    const w = mountDialog()
    await flushPromises()
    expect(w.find('[data-testid="import-anchoring"]').exists()).toBe(false)
    w.unmount()
  })
})
