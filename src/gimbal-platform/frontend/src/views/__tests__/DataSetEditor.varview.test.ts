/**
 * DataSetEditor 变量优先双模式(spec v2 §6,2026-09-11;取代段网格测试):
 * 列宇宙 = config.vars 声明序(未声明引用列追加),一变量一列;
 * 「全部」= 变量网格(引用徽标/未引用灰/期望徽标+↗)/「单变量」=
 * VariableDetailPanel 独立渲染;视图切换纯过滤;CSV 宇宙不随视图收缩。
 * 骨架(api mock + route stub)复制 DataSetEditor.palette.test.ts。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// VAR-3 需断言 router.push 调参 — push 提升为 hoisted 共享句柄
const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  // datasetId 非 'new' → onMounted 走 getDataSet 载入既有 rows
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'ds-1' } }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

// 单变量面板 mount 即拉视图索引 — 编辑器级测试只需空索引(取数面由
// VariableDetailPanel.test.ts 独立覆盖)
vi.mock('@/api/query-views', () => ({
  fetchQueryViewIndex: vi.fn(async () => []),
  fetchQueryViewRows: vi.fn(async () => ({ view: '', rows: [], truncated: false, fetched_at: '', cached: false, stale: false })),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '@/views/DataSetEditor.vue'

/** 三步场景:step1(amount + exp_code)/ step2(bl_no)/ step3(无引用)。
 *  step3 的 plain 是直填字面量 — 不进网格列(VAR-9 断言面)。 */
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

/** 未引用变量:idle 声明于 config.vars 但无任何模板引用 → 列标灰(VAR-2) */
const DEF_UNREF = {
  ...DEF_2SEG,
  config: { vars: { amount: 100, exp_code: 200, bl_no: 'BL1', idle: '9' } },
}

/** 共享变量:amount 被 step1 + step2 同时引用 → 一列两徽标(VAR-8) */
const DEF_SHARED = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'shared' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} }, request: { kind: 'request', body: { amount: '${var.amount}' } }, strategy: [] },
    { kind: 'step', description: '查单', api: { headers: {} }, request: { kind: 'request', body: { amount: '${var.amount}' } }, strategy: [] },
  ],
}

/** 同 var 兼为输入与期望(VAR-5b 自然去重):一列,输入徽标 + 期望徽标并存 */
const DEF_DUPVAR = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'dup' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.amount}' }] },
  ],
}

/** 未声明引用:body 引用 ${var.extra} 但 config.vars 无 extra → 追加列(VAR-10) */
const DEF_UNDECLARED = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'undeclared' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} }, request: { kind: 'request', body: { amount: '${var.amount}', extra: '${var.extra}' } }, strategy: [] },
  ],
}

/** COMPAT-1 旧提升流数据集:rows 键 = var 名(amount)、直填列在场(remark)、
 *  断言 expected 为字面量(旧形态)。钉「打开不炸 + 直填不呈现」。 */
const DEF_OLD_PROMOTE = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'old' },
  config: { vars: { amount: '1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } },
      request: { kind: 'request', body: { amount: '${var.amount}', remark: '直填字面量' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.q' } }, request: { kind: 'request', body: { status: 'PAID' } }, strategy: [] },
  ],
}

/** 挂载工厂:getDataSet 返回 rows(默认 [{amount:'-1'}]),draft 返回入参 definition;
 *  orchestration.steps 带 name(= step.description)供徽标读步骤展示名。 */
async function mountEditor(def: typeof DEF_2SEG, rows: Array<Record<string, any>> = [{ amount: '-1' }]) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: def, orchestration: { steps: def.steps.map((s: any) => ({ name: s.description })), resourceMeta: {} } } as any,
  )
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'getDataSet').mockResolvedValue(
    { name: 'n', description: '', rows } as any,
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
  routerMock.push.mockReset()
})

// 让 vi.spyOn 不会跨测试泄漏(palette 测试同款纪律)
afterEach(() => {
  vi.restoreAllMocks()
})

describe('DataSetEditor — 变量优先「全部」网格(§6)', () => {
  it('VAR-1: 变量选择器在场,默认「全部(N 变量)」;列 = config.vars 声明序,一变量一列', async () => {
    const w = await mountEditor(DEF_2SEG)
    // 下拉容器在场;EP ≥2.5 重写版 el-select 选中回显在 .el-select 根文本
    expect(w.find('.var-picker .el-select').exists()).toBe(true)
    expect(w.find('.var-picker .el-select').text()).toContain('全部(3 变量)')
    expect((w.vm as any).varChoice).toBe('all')
    // 列头 = 变量名(声明序),无「步骤N -」前缀;直填 plain 不进列宇宙
    const heads = w.findAll('.row-field .th-data').map((t) => t.text()).join()
    expect(heads).toContain('amount')
    expect(heads).toContain('exp_code')
    expect(heads).toContain('bl_no')
    expect(heads).not.toContain('plain')
    expect(heads).not.toContain('步骤1 - amount')
    // 引用徽标:amount ← 步骤1·下单;bl_no ← 步骤2·查单(orchestration 名)
    expect(w.find('.row-field .th-data:nth-child(3)').text()).toContain('1·下单')
    expect(w.find('.row-field .th-data:nth-child(5)').text()).toContain('2·查单')
    // 行名列常驻
    expect(w.find('.data-name-input').exists()).toBe(true)
    w.unmount()
  })

  it('VAR-2: 未引用变量列标灰(表头 + 基线格),仍可编辑基线', async () => {
    const w = await mountEditor(DEF_UNREF as any)
    const heads = w.findAll('.row-field .th-data')
    // 声明序 [amount, exp_code, bl_no, idle] → idle 是第 4 数据列
    const idleTh = heads[3]
    expect(idleTh.text()).toContain('idle')
    expect(idleTh.classes()).toContain('col-unreferenced')
    expect(idleTh.findAll('.ref-badge').length).toBe(0)   // 无引用徽标
    // 基线格同灰;值可编辑(aria 完备)
    const idleBase = w.findAll('.row-baseline input.baseline-cell-input')[3]
    expect(idleBase.attributes('aria-label')).toBe('基线 idle')
    expect((idleBase.element as HTMLInputElement).value).toBe('9')
    await idleBase.setValue('99')
    expect((w.vm as any).draft.definition.config.vars.idle).toBe('99')
    w.unmount()
  })

  it('VAR-3: 期望徽标 + ↗ 跳断言卡(router.push focusStep/focusStrategy)', async () => {
    const w = await mountEditor(DEF_2SEG)
    // exp_code(声明序第 2 列)带期望徽标 + 跳转钮;非期望列不渲染
    const expTh = w.findAll('.row-field .th-data')[1]
    expect(expTh.text()).toContain('exp_code')
    expect(expTh.find('.exp-col-badge').exists()).toBe(true)
    const jumps = w.findAll('.row-field .th-data .exp-jump')
    expect(jumps.length).toBe(1)
    await jumps[0].trigger('click')
    // exp_code 断言 strategyIdx=0、stepIndex=0(0-based;绝不发空串)
    expect(routerMock.push).toHaveBeenCalledTimes(1)
    expect(routerMock.push).toHaveBeenCalledWith({
      path: '/composer/sc-ds',
      query: { step: '4', focusStep: '0', focusStrategy: '0' },
    })
    w.unmount()
  })

  it('VAR-5b: 同 var 兼为输入与期望 → 恰好一列(自然去重),输入徽标 + 期望徽标并存', async () => {
    const w = await mountEditor(DEF_DUPVAR as any)
    const heads = w.findAll('.row-field .th-data')
    expect(heads.length).toBe(1)
    expect(heads[0].text()).toContain('amount')
    expect(heads[0].findAll('.ref-badge').length).toBe(1)   // 输入引用徽标
    expect(heads[0].find('.exp-col-badge').exists()).toBe(true)
    w.unmount()
  })

  it('VAR-8: 共享变量(两步骤引用)→ 一列两徽标;无共享徽标残留类', async () => {
    const w = await mountEditor(DEF_SHARED as any)
    const heads = w.findAll('.row-field .th-data')
    expect(heads.length).toBe(1)                              // 一变量一列
    const badges = heads[0].findAll('.ref-badge')
    expect(badges.length).toBe(2)
    expect(badges[0].text()).toContain('1·下单')
    expect(badges[1].text()).toContain('2·查单')
    expect(w.find('.shared-mark').exists()).toBe(false)       // 旧共享徽标类退场
    w.unmount()
  })

  it('VAR-10: 未声明引用(body ${var.extra} ∉ config.vars)→ 追加列,基线空可声明', async () => {
    const w = await mountEditor(DEF_UNDECLARED as any, [{ amount: '5' }])
    const heads = w.findAll('.row-field .th-data').map((t) => t.text())
    // 声明列在前(amount),未声明引用列追加在后(extra)
    expect(heads[0]).toContain('amount')
    expect(heads[1]).toContain('extra')
    expect(heads[1]).toContain('1·下单')                     // 引用在场(非灰)
    // 基线空 → 行格 placeholder 空;基线行输入即声明
    const extraBase = w.findAll('.row-baseline input.baseline-cell-input')[1]
    expect((extraBase.element as HTMLInputElement).value).toBe('')
    await extraBase.setValue('E1')
    expect((w.vm as any).draft.definition.config.vars.extra).toBe('E1')
    expect((w.vm as any).baselineDirty).toBe(true)
    w.unmount()
  })

  it('VAR-9: 基线行 = config.vars 唯一编辑入口(声明序 aria);直填列彻底退场', async () => {
    const w = await mountEditor(DEF_2SEG)
    expect(w.find('.data-cell-direct').exists()).toBe(false)
    expect(w.find('.baseline-collapse').exists()).toBe(false)
    expect(w.find('input.baseline-direct-input').exists()).toBe(false)
    const baseLabels = w.findAll('.row-baseline input.baseline-cell-input')
      .map((i) => i.attributes('aria-label'))
    expect(baseLabels).toEqual(['基线 amount', '基线 exp_code', '基线 bl_no'])
    w.unmount()
  })

  it('VAR-6: TSV 粘贴/行增删/caseNames 保留(既有行为零回归)', async () => {
    const w = await mountEditor(DEF_2SEG)
    // 首列(amount)= 第一个数据格输入;粘单列纵向 3 值(1 行 → 3 行)
    const firstCell = w.findAll('input.data-cell-input')[0]
    const evt = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(evt, 'clipboardData', { value: { getData: () => 'a\nb\nc' } })
    await firstCell.element.dispatchEvent(evt)
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: 'a' }, { amount: 'b' }, { amount: 'c' }])
    expect((w.vm as any).caseNames).toEqual(['data-1', 'data-2', 'data-3'])
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    expect(w.findAll('.data-table tbody tr.row-data').length).toBe(4)
    const nameInput = w.find('input.data-name-input')
    await nameInput.setValue('edge-min')
    expect((nameInput.element as HTMLInputElement).value).toBe('edge-min')
    w.unmount()
  })

  it('VAR-7: 死行键软提示条 — 行键 ∉ config.vars → 标黄提示,可继续编辑', async () => {
    const w = await mountEditor(DEF_2SEG, [{ amount: '-1', ghost_key: 'x' }])
    const bar = w.find('.dead-keys-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.text()).toContain('ghost_key')
    expect(bar.text()).toContain('运行无效果')
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
    expect(addBtn!.attributes('disabled')).toBeUndefined()
    expect(w.find('input.data-cell-input').attributes('disabled')).toBeUndefined()
    w.unmount()
  })

  it('VAR-11: CSV 宇宙 = config.vars 声明序(含未引用列),不随单变量视图收缩', async () => {
    const w = await mountEditor(DEF_UNREF as any)
    // 切到单变量视图 — CSV 链不得随之收缩
    ;(w.vm as any).varChoice = 'idle'
    await flushPromises()
    const csv = await import('@/utils/csv-dataset')
    const exportSpy = vi.spyOn(csv, 'exportDataSetCsv').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('导出 CSV'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(exportSpy).toHaveBeenCalled()
    const args = exportSpy.mock.calls[0][0] as any
    expect(args.columns.map((c: any) => c.varName)).toEqual(['amount', 'exp_code', 'bl_no', 'idle'])
    expect(args.descriptions.length).toBe(4)
    const text = csv.buildDataSetCsv(args)
    expect(text.split('\n')[0]).toContain('idle')
    w.unmount()
  })
})

describe('DataSetEditor — 「单变量」详情面板(§6)', () => {
  it('VAR-4: 选单变量 → 面板替换网格;四段面齐(基线/引用面/取数/行值)', async () => {
    const w = await mountEditor(DEF_2SEG, [{ amount: '-1', bl_no: 'BL9' }])
    const rowsBefore = JSON.stringify((w.vm as any).rows)
    ;(w.vm as any).varChoice = 'bl_no'
    await flushPromises()
    // 面板在场,网格退场
    expect(w.find('.vdp').exists()).toBe(true)
    expect(w.find('.data-table').exists()).toBe(false)
    // 面板头 + 引用面:步骤2 · 查单 · body · bl_no
    expect(w.find('.vdp-title').text()).toBe('bl_no')
    const refText = w.find('.vdp-ref').text()
    expect(refText).toContain('步骤2 · 查单')
    expect(refText).toContain('body · bl_no')
    // 基线:config.vars 初值 BL1,编辑走同链(baselineDirty)
    const baseInput = w.find('input[aria-label="基线 bl_no"]')
    expect((baseInput.element as HTMLInputElement).value).toBe('BL1')
    await baseInput.setValue('BL2')
    expect((w.vm as any).draft.definition.config.vars.bl_no).toBe('BL2')
    expect((w.vm as any).baselineDirty).toBe(true)
    // 行值:BL9 覆写态;编辑写回 rows
    const rowInput = w.find('input[aria-label="data-1 bl_no"]')
    expect((rowInput.element as HTMLInputElement).value).toBe('BL9')
    expect(w.find('.vdp-rowval-flag').text()).toBe('覆写')
    await rowInput.setValue('BL8')
    expect((w.vm as any).rows[0].bl_no).toBe('BL8')
    // 纯视图过滤:rows/caseNames 结构不被切换破坏(amount 键还在)
    const rowsAfter = JSON.stringify((w.vm as any).rows)
    expect(rowsAfter).toBe(JSON.stringify([{ amount: '-1', bl_no: 'BL8' }]))
    expect(rowsAfter).not.toBe(rowsBefore)   // 只反映面板编辑,无额外形状变化
    // 取数段在场(空索引 → 空态文案;取数面行为由面板级测试覆盖)
    expect(w.text()).toContain('取数')
    expect(w.text()).toContain('无 query-safe 查询视图可取数')
    // 回「全部」→ 网格回来
    ;(w.vm as any).varChoice = 'all'
    await flushPromises()
    expect(w.find('.data-table').exists()).toBe(true)
    expect(w.find('.vdp').exists()).toBe(false)
    w.unmount()
  })

  it('VAR-4b: 所选变量彻底退场(声明被删且无引用)→ 回落「全部」', async () => {
    const w = await mountEditor(DEF_UNREF as any)
    ;(w.vm as any).varChoice = 'idle'
    await flushPromises()
    expect(w.find('.vdp').exists()).toBe(true)
    // idle 无引用位 — 删声明即彻底退场(bl_no 这类有引用的变量删声明后
    // 仍以「未声明引用列」存活,不触发回落)
    const vars = (w.vm as any).draft.definition.config.vars
    delete vars.idle
    await flushPromises()
    expect((w.vm as any).varChoice).toBe('all')
    expect(w.find('.data-table').exists()).toBe(true)
    w.unmount()
  })

  it('VAR-4c: 期望引用位在面板引用面 ↗ 跳断言卡', async () => {
    const w = await mountEditor(DEF_2SEG)
    ;(w.vm as any).varChoice = 'exp_code'
    await flushPromises()
    const jump = w.find('.vdp-ref .exp-jump')
    expect(jump.exists()).toBe(true)
    await jump.trigger('click')
    expect(routerMock.push).toHaveBeenCalledWith({
      path: '/composer/sc-ds',
      query: { step: '4', focusStep: '0', focusStrategy: '0' },
    })
    w.unmount()
  })
})

describe('DataSetEditor — 行详情(§6.2 v1 只读,按段分组)', () => {
  it('VAR-DET: 预览弹窗按段分组垂直呈现,含继承态标注', async () => {
    const w = await mountEditor(DEF_2SEG, [{ amount: '-1', exp_code: '400' }])
    ;(w.vm as any).toggleRow(0, true)
    await flushPromises()
    const btn = w.findAll('button').find((b) => b.text().includes('预览选中'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    // el-dialog teleport 到 body — 从 document 查(T12 模式)
    const segHeads = [...document.querySelectorAll('.detail-seg-head')].map((e) => e.textContent ?? '')
    expect(segHeads.join('|')).toContain('步骤1 · 下单')
    expect(segHeads.join('|')).toContain('步骤2 · 查单')
    const flags = [...document.querySelectorAll('.detail-flag')].map((e) => e.textContent ?? '')
    expect(flags).toContain('覆写')
    expect(flags).toContain('继承基线')
    w.unmount()
  })
})

describe('DataSetEditor — 老数据集兼容(旧提升流)', () => {
  it('COMPAT-1: 旧数据集(rows 键=var 名,直填列存在)打开不炸,单变量列 + TSV/保存全在', async () => {
    const w = await mountEditor(DEF_OLD_PROMOTE as any, [{ amount: '5' }, { amount: '6' }])
    // 单变量 → 无变量选择器,列作用域 = 唯一变量
    expect(w.findAll('.var-picker').length).toBe(0)
    const heads = w.findAll('.row-field .th-data').map((t) => t.text()).join()
    expect(heads).toContain('amount')
    expect(heads).not.toContain('remark')          // 直填列不出数据表格
    expect(w.findAll('.data-name-input').length).toBe(2)
    const cells = w.findAll('input.data-cell-input')
    expect(cells.length).toBe(2)
    expect((cells[0].element as HTMLInputElement).value).toBe('5')
    expect((cells[0].element as HTMLInputElement).placeholder).toBe('1')   // config.vars.amount
    expect(w.findAll('td.cell-override-value').length).toBe(2)
    expect(w.find('.dead-keys-bar').exists()).toBe(false)
    const baseLabels = w.findAll('.row-baseline input.baseline-cell-input')
      .map((i) => i.attributes('aria-label'))
    expect(baseLabels).toEqual(['基线 amount'])
    // 保存链不炸:点「保存基线」→ updateScenario 被调,rows 形状零变化
    const saveBtn = w.findAll('button').find((b) => b.text().includes('保存基线'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    expect((w.vm as any).rows).toEqual([{ amount: '5' }, { amount: '6' }])
    // TSV 粘贴链照常(行键仍落 var 名)
    const evt = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(evt, 'clipboardData', { value: { getData: () => '7\n8' } })
    await cells[0].element.dispatchEvent(evt)
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: '7' }, { amount: '8' }])
    w.unmount()
  })
})
