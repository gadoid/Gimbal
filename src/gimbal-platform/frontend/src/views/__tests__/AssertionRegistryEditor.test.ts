/**
 * AssertionRegistryEditor — 断言管理编辑器(spec v3 §5):
 * 条目列表(path 徽标/值摘要/期望数/死条目灰/旧版条目灰不可选)+
 * 详情(path 只读跳编排器 / value 类型化编辑 / asserts 编辑)+
 * 手工新建(步骤 + jsonpath)+ 整体 PUT(只动 assertion_registry 键)。
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
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
      value: -1,
      asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }] },
    { id: 'inj-dead', name: '悬空条目',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' },
      value: 1, asserts: [] },
    { id: 'inj-legacy', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
      injection: [{ varName: 'amount', value: '-1' }], asserts: [] },
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

it('ARE-1: 列表渲染条目(名称/path 徽标/值摘要/期望数)', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(3)
  expect(rows[0].text()).toContain('金额为负')
  expect(rows[0].text()).toContain('步骤1 · $.amount')        // path 徽标
  expect(rows[0].text()).toContain('-1')                      // value 摘要
  expect(rows[0].text()).toContain('1 期望')                  // asserts 数
  w.unmount()
})

it('ARE-2: 悬空条目灰(stepIndex 越界)+ 旧版条目灰且不可选;活条目不灰', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows[1].classes()).toContain('are-dead')
  expect(rows[2].classes()).toContain('are-legacy')
  expect(rows[0].classes()).not.toContain('are-dead')
  // 旧版条目点击不进详情(不可编辑,spec v3 §8)
  await rows[2].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(false)
  w.unmount()
})

it('ARE-3: path ↗ 跳编排器(focusStep query)', async () => {
  const w = await mountEditor()
  await w.findAll('.are-anchor-jump')[0].trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith({
    path: '/composer/sc-rg',
    query: { step: '4', focusStep: '0' },
  })
  w.unmount()
})

it('ARE-4: 手工新建(步骤+jsonpath)+ value num 类型化编辑 + 保存只动 assertion_registry', async () => {
  const w = await mountEditor()
  // 手工新建:pendingPath 填 $.bl_no → 新建条目
  ;(w.vm as any).pendingPath.jsonpath = '$.bl_no'
  await w.findAll('button').find((b) => b.text().includes('新建条目'))!.trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row').length).toBe(4)
  const rows = w.findAll('.are-row')
  await rows[3].trigger('click')
  await flushPromises()
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)
  // value 类型化编辑:num 类 '-7' → 落条目为 number -7(原样不 coerce 串)
  ;(w.vm as any).valueDraft.kind = 'num'
  ;(w.vm as any).valueDraft.text = '-7'
  ;(w.vm as any).applyValue()
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  expect(api.updateScenario).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.definition).toEqual(DEF)                        // definition 原样
  const e3 = payload.assertion_registry.entries[3]
  expect(e3.path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.bl_no' })
  expect(e3.value).toBe(-7)
  expect(e3.asserts).toEqual([])
  w.unmount()
})


// ── 值送达面注记(与后端 run_injection._assign_strategy 同语义)──────

function draftWithValue(value: unknown) {
  return {
    definition: DEF,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-v', name: '值形状', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
        value, asserts: [] },
    ] },
  }
}

async function selectOnlyRow(w: any) {
  await w.findAll('.are-row')[0].trigger('click')
  await flushPromises()
}

it('ARE-5: 引用形字符串值($.x / ${...})→ 显形注记(引擎先当上下文读)', async () => {
  for (const v of ['$.amount', '${var.amount}']) {
    const w = await mountEditor(draftWithValue(v))
    await selectOnlyRow(w)
    const note = w.find('.are-val-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('上下文引用')
    expect(note.text()).toContain('覆写')
    w.unmount()
  }
})

it('ARE-6: JSON null 值 → 显形注记(null 送不到引擎)', async () => {
  const w = await mountEditor(draftWithValue(null))
  await selectOnlyRow(w)
  const note = w.find('.are-val-note')
  expect(note.exists()).toBe(true)
  expect(note.text()).toContain('送不到引擎')
  w.unmount()
})

it('ARE-7: 普通字面量值 → 无注记(不误报)', async () => {
  for (const v of ['hello', '-1', 0, false, { a: 1 }]) {
    const w = await mountEditor(draftWithValue(v))
    await selectOnlyRow(w)
    expect(w.find('.are-detail').exists()).toBe(true)   // 详情在,注记不在
    expect(w.find('.are-val-note').exists()).toBe(false)
    w.unmount()
  }
})
