/**
 * DataSetEditor 段网格(spec §6.2,2026-09-10):列作用域收缩到单 step 段。
 * 段 tabs 派生(引用扫描)/ 段内列过滤 / 行名列常驻钉选 / "全部"阈值 ≤8
 * 默认全部 / 直填列退场数据表格(基线区可编辑)/ 期望列徽标。
 * 骨架(api mock + route stub)复制 DataSetEditor.palette.test.ts。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  // datasetId 非 'new' → onMounted 会走 getDataSet 载入既有 rows(SEG-1 注释契约)
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'ds-1' } }),
  useRouter: () => ({ push: vi.fn() }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '@/views/DataSetEditor.vue'

/** 三步场景:step1(amount + exp_code)/ step2(bl_no)/ step3(无引用)→ 两段。
 *  步骤带 view_hints.endpoint_id — 基线区(deriveBaselineColumns 有 endpoint_id
 *  纪律)需要它才能渲染 step3 的 plain 直填行(SEG-4 基线区断言面)。 */
const DEF_2SEG = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 's' },
  config: { vars: { amount: 100, exp_code: 200, bl_no: 'BL1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } }, request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' }] },
    { kind: 'step', description: '查单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.q' } }, request: { kind: 'request', body: { bl_no: '${var.bl_no}' } }, strategy: [] },
    { kind: 'step', description: '第三步', api: { headers: {}, view_hints: { endpoint_id: 'fin.demo' } }, request: { kind: 'request', body: { plain: 'x' } }, strategy: [] },
  ],
}

/** 9 列场景(SEG-3):step1 九个 ${var} 字段 + step2 一个 → 总列数 10 > 8 → 默认第一段 */
const DEF_9COLS = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 's9' },
  config: { vars: Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`f${i + 1}`, `${i + 1}`]).concat([['other', 'x']])) },
  steps: [
    {
      kind: 'step', description: '宽步骤', api: { headers: {} },
      request: { kind: 'request', body: Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`f${i + 1}`, '${var.f' + (i + 1) + '}'])) },
      strategy: [],
    },
    { kind: 'step', description: '窄步骤', api: { headers: {} }, request: { kind: 'request', body: { other: '${var.other}' } }, strategy: [] },
  ],
}

/** 挂载工厂:getDataSet 返回 rows:[{amount:'-1'}],draft 返回入参 definition。 */
async function mountEditor(def: typeof DEF_2SEG) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: def, orchestration: { steps: [], resourceMeta: {} } } as any,
  )
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'getDataSet').mockResolvedValue(
    { name: 'n', description: '', rows: [{ amount: '-1' }] } as any,
  )
  vi.spyOn(api, 'getFullEndpoint').mockImplementation(async (eid: string) => ({
    id: eid, request: { declarations: [] },
  } as any))
  const w = mount(DataSetEditor, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
})

// 让 vi.spyOn 不会跨测试泄漏(palette 测试同款纪律)
afterEach(() => {
  vi.restoreAllMocks()
})

describe('DataSetEditor — 段网格(§6.2)', () => {
  it('SEG-1: 段 tabs 派生(两段)+ "全部";总列数 ≤8 默认全部;行名列常驻', async () => {
    const w = await mountEditor(DEF_2SEG)
    const tabs = w.findAll('.seg-tab')
    expect(tabs.map((t) => t.text()).join('|')).toContain('步骤1')
    expect(tabs.map((t) => t.text()).join('|')).toContain('步骤2')
    expect(tabs.map((t) => t.text()).join('|')).toContain('全部')
    expect(w.find('.seg-tab.active').text()).toContain('全部')   // 3 列 ≤8 → 默认全部
    // 行名列钉选:数据表格首列数据名输入在场
    expect(w.find('.data-name-input').exists()).toBe(true)
    w.unmount()
  })

  it('SEG-2: 切段 → 段内列过滤(输入+期望并排),他段列退场', async () => {
    const w = await mountEditor(DEF_2SEG)
    await w.findAll('.seg-tab').find((t) => t.text().includes('步骤1'))!.trigger('click')
    // 段1 列头:amount + exp_code(期望徽标);bl_no 退场
    const heads = w.findAll('.row-field .th-data').map((t) => t.text()).join()
    expect(heads).toContain('amount')
    expect(heads).toContain('exp_code')
    expect(heads).toContain('期望')        // 期望列徽标文案
    expect(heads).not.toContain('bl_no')
    w.unmount()
  })

  it('SEG-3: 总列数 >8 默认第一段(阈值 8)', async () => {
    // 9 列场景:step1 9 个 ${var} 字段 + step2 1 个 → 默认选中步骤1
    const w = await mountEditor(DEF_9COLS as any)
    expect(w.find('.seg-tab.active').text()).toContain('步骤1')
    w.unmount()
  })

  it('SEG-4: 直填列退场数据表格;基线区直填行改为可编辑输入', async () => {
    const w = await mountEditor(DEF_2SEG)   // step3 plain 字面量(直填列)
    await w.findAll('.seg-tab').find((t) => t.text().includes('全部'))!.trigger('click')
    // 数据表格无直填输入(.data-cell-direct 退场)
    expect(w.find('.data-cell-direct').exists()).toBe(false)
    // 基线区直填行有编辑输入(展开基线折叠后可见;展开方式以现场结构为准 —
    // 与 palette 测试同款:先展开基线折叠,再展开全部步骤分组)
    await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
    await flushPromises()
    const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
    for (const h of groupHeaders) await h.trigger('click')
    await flushPromises()
    // 断言:基线区 plain 行内 input.baseline-direct-input 存在
    expect(w.find('input.baseline-direct-input').exists()).toBe(true)
    w.unmount()
  })

  it('SEG-5: 期望列可编辑(行值 = row[varName]),placeholder = config.vars 基线', async () => {
    const w = await mountEditor(DEF_2SEG)
    const expInput = w.findAll('.data-cell-input').find((el) =>
      (el.element as HTMLInputElement).placeholder === '200')
    expect(expInput).toBeTruthy()          // exp_code 基线 200
    w.unmount()
  })

  it('SEG-6: TSV 粘贴/行增删/caseNames 保留(既有行为零回归)', async () => {
    const w = await mountEditor(DEF_2SEG)
    // 段视图:切到步骤1(amount + exp_code 并排)
    await w.findAll('.seg-tab').find((t) => t.text().includes('步骤1'))!.trigger('click')
    await flushPromises()
    // 段内首列(amount)= 第一个数据格输入;粘单列纵向 3 值(1 行 → 3 行)
    const firstCell = w.findAll('input.data-cell-input')[0]
    const evt = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(evt, 'clipboardData', { value: { getData: () => 'a\nb\nc' } })
    await firstCell.element.dispatchEvent(evt)
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: 'a' }, { amount: 'b' }, { amount: 'c' }])
    // caseNames 同步补齐(粘贴自动增行)
    expect((w.vm as any).caseNames).toEqual(['data-1', 'data-2', 'data-3'])
    // + 新增数据按钮加行
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    expect(w.findAll('.data-table tbody tr.row-data').length).toBe(4)
    // 行名输入可改
    const nameInput = w.find('input.data-name-input')
    await nameInput.setValue('edge-min')
    expect((nameInput.element as HTMLInputElement).value).toBe('edge-min')
    w.unmount()
  })
})
