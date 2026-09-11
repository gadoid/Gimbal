/**
 * AssertionRegistryEditor — 断言管理注册表编辑器(spec v2 §7):
 * 条目列表(锚定徽标/偏离摘要/死条目灰)+ 详情(anchor 跳编排器 +
 * injection/asserts 编辑)+ 手工新建 + 整体 PUT(只动 assertion_registry 键)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-rg' } }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import AssertionRegistryEditor from '@/views/AssertionRegistryEditor.vue'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-rg', meta: { name: 'rg' },
  config: { vars: { amount: 100, bl_no: 'BL1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: { bl_no: '${var.bl_no}' } }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-1', name: '金额为负',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
      injection: [{ varName: 'amount', value: '-1' }],
      asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }] },
    { id: 'inj-dead', name: '死条目',
      anchor: { stepIndex: 9, source: 'body', jsonpath: '$.x' },
      injection: [{ varName: 'ghost', value: '1' }], asserts: [] },
  ],
}

async function mountEditor(draft: any = { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG }) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(draft as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  const w = mount(AssertionRegistryEditor, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => { setActivePinia(createPinia()); routerMock.push.mockReset() })
afterEach(() => { vi.restoreAllMocks() })

it('ARE-1: 列表渲染条目(名称/锚定徽标/偏离摘要/期望数)', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(2)
  expect(rows[0].text()).toContain('金额为负')
  expect(rows[0].text()).toContain('步骤1 · $.amount')        // anchor 徽标
  expect(rows[0].text()).toContain('amount = -1')             // injection 摘要
  expect(rows[0].text()).toContain('1 期望')                  // asserts 数
  w.unmount()
})

it('ARE-2: 死条目标灰(stepIndex 越界 + var 未知);活条目不灰', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows[1].classes()).toContain('are-dead')
  expect(rows[0].classes()).not.toContain('are-dead')
  w.unmount()
})

it('ARE-3: anchor ↗ 跳编排器(focusStep query)', async () => {
  const w = await mountEditor()
  await w.findAll('.are-anchor-jump')[0].trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith({
    path: '/composer/sc-rg',
    query: { step: '4', focusStep: '0' },
  })
  w.unmount()
})

it('ARE-4: 手工新建 + injection 编辑(varName 候选 = config.vars)+ 保存只动 assertion_registry', async () => {
  const w = await mountEditor()
  await w.findAll('button').find((b) => b.text().includes('新建条目'))!.trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row').length).toBe(3)
  // 选中第 3 条:varName 下拉选 bl_no、值 BL9
  const rows = w.findAll('.are-row')
  await rows[2].trigger('click')
  await flushPromises()
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)
  ;(w.vm as any).pendingInject.varName = 'bl_no'    // script setup binding 经 vm 可写(EP 纪律)
  ;(w.vm as any).pendingInject.value = 'BL9'
  await w.find('.are-detail .are-add-inject').trigger('click')
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  expect(api.updateScenario).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.definition).toEqual(DEF)                        // definition 原样
  expect(payload.assertion_registry.entries.length).toBe(3)
  expect(payload.assertion_registry.entries[2].injection).toEqual([{ varName: 'bl_no', value: 'BL9' }])
  w.unmount()
})
