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

// DET-2 需断言 router.push 调参 — push 提升为 hoisted 共享句柄
// (vi.mock factory 早于顶层 const 初始化,直接闭包外层变量会 TDZ)
const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  // datasetId 非 'new' → onMounted 会走 getDataSet 载入既有 rows(SEG-1 注释契约)
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'ds-1' } }),
  useRouter: () => ({ push: routerMock.push }),
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

/** 同 var 兼为输入与期望(SEG-7b 去重回归):step1 body.amount 引用 ${var.amount},
 *  step1 断言 expected 也引用 ${var.amount} → gridColumnsOf 出两列同名列。 */
const DEF_DUPVAR = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'dup' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.amount}' }] },
  ],
}

/** DET-4 双用 var 双重撞号面:step1 body.amount 引用 ${var.amount}(输入列)+
 *  同 step 两条断言 expected 都引用 ${var.amount}(期望列 ×2,expects 不去重)
 *  → gridColumnsOf 三列同名 amount — 旧行详情键(it.varName)与旧网格列键
 *  (stepIndex:source:varName,两期望列同 step 同 var)均撞号,键差异化后共存。 */
const DEF_DUALVAR2 = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'dual2' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [
        { kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.amount}' },
        { kind: 'assertion', target: '$.response_body.msg', operator: 'contains', expected: '${var.amount}' },
      ] },
  ],
}

/** COMPAT-1 旧提升流数据集:rows 键 = var 名(amount)、直填列在场(remark)、
 *  断言 expected 为字面量(无任何 ${var} 模板,旧形态)→ 引用扫描仅 step1 一段。
 *  两步都带 view_hints.endpoint_id — 段派生不设 endpoint_id 门(dataset-segments),
 *  但基线区 deriveBaselineColumns 有 endpoint_id 纪律(dataset-palette):没有它
 *  remark 直填行不进基线区,「基线区可编辑」断言面就钉不住(同 DEF_2SEG 注释)。 */
const DEF_OLD_PROMOTE = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 'old' },
  config: { vars: { amount: '1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.add' } },
      request: { kind: 'request', body: { amount: '${var.amount}', remark: '直填字面量' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {}, view_hints: { endpoint_id: 'fin.order.q' } },
      request: { kind: 'request', body: { status: 'PAID' } }, strategy: [] },
  ],
}

/** 挂载工厂:getDataSet 返回 rows(默认 [{amount:'-1'}]),draft 返回入参 definition;
 *  orchestration.steps 带 name(= step.description)供 stepLabel 读段头展示名。 */
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

  it('SEG-7(修轮回归): 单段模式下 CSV 导出覆盖全量 var 宇宙,段过滤不影响 CSV 链(brief ⑥)', async () => {
    const w = await mountEditor(DEF_2SEG)
    // 切到步骤1 段(段内仅 amount + exp_code)— CSV 链不得随之收缩
    await w.findAll('.seg-tab').find((t) => t.text().includes('步骤1'))!.trigger('click')
    await flushPromises()
    const csv = await import('@/utils/csv-dataset')
    const exportSpy = vi.spyOn(csv, 'exportDataSetCsv').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('导出 CSV'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(exportSpy).toHaveBeenCalled()
    const args = exportSpy.mock.calls[0][0] as any
    // 列宇宙 = 全段(步骤1 的 amount+exp_code 之外,步骤2 的 bl_no 不丢)
    expect(args.columns.map((c: any) => c.varName)).toEqual(['amount', 'exp_code', 'bl_no'])
    // descriptions 与列宇宙同长 → (description) 行守卫满足
    expect(args.descriptions.length).toBe(3)
    // 端到端:产出的 CSV 文本含 (description) 行,列头覆盖全宇宙
    const text = csv.buildDataSetCsv(args)
    expect(text).toContain('(description)')
    expect(text.split('\n')[0]).toContain('bl_no')
    w.unmount()
  })

  it('SEG-7b(修轮回归): 同 var 兼为输入与期望 → CSV 列宇宙 varName 去重(首现胜出,恰好一列)', async () => {
    // DEF_DUPVAR:step1 的 amount 既是输入列又是期望列 → 未去重时 CSV 会出现两个 amount 列
    const w = await mountEditor(DEF_DUPVAR as any)
    const csv = await import('@/utils/csv-dataset')
    const exportSpy = vi.spyOn(csv, 'exportDataSetCsv').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('导出 CSV'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(exportSpy).toHaveBeenCalled()
    const args = exportSpy.mock.calls[0][0] as any
    // 去重:恰好一列(输入列首现胜出)
    expect(args.columns.map((c: any) => c.varName)).toEqual(['amount'])
    // 端到端:CSV 列头 amount 恰好出现一次
    const text = csv.buildDataSetCsv(args)
    expect(text.split('\n')[0]).toBe('__case_name,amount')
    w.unmount()
  })
})

describe('DataSetEditor — 行详情 + 期望列头跳转 + 死行键(§6.2/§5.3/§7)', () => {
  it('DET-1: 预览弹窗升级行详情 — 按段分组垂直呈现,含继承态标注', async () => {
    const w = await mountEditor(DEF_2SEG, [{ amount: '-1', exp_code: '400' }])
    // 勾选首行 + 点「预览选中的数据」
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
    // 继承态标注:amount 行(row 有键)「覆写」;bl_no 行(row 无键)「继承基线」
    const flags = [...document.querySelectorAll('.detail-flag')].map((e) => e.textContent ?? '')
    expect(flags).toContain('覆写')
    expect(flags).toContain('继承基线')
    w.unmount()
  })

  it('DET-2: 期望列头 ↗ 跳转按钮 → router.push composer + focusStep/focusStrategy query', async () => {
    const w = await mountEditor(DEF_2SEG)
    // 默认「全部」(3 列 ≤8)→ exp_code 期望列头在场;非 expect 列不渲染跳转按钮
    const jumps = w.findAll('.row-field .th-data .exp-jump')
    expect(jumps.length).toBe(1)
    await jumps[0].trigger('click')
    // exp_code 断言 strategyIdx=0、stepIndex=0(0-based,Task 3 契约;绝不发空串)
    expect(routerMock.push).toHaveBeenCalledTimes(1)
    expect(routerMock.push).toHaveBeenCalledWith({
      path: '/composer/sc-ds',
      query: { step: '4', focusStep: '0', focusStrategy: '0' },
    })
    w.unmount()
  })

  it('DET-3: 死行键软提示条 — 行键 ∉ config.vars → 标黄提示,可继续编辑', async () => {
    const w = await mountEditor(DEF_2SEG, [{ amount: '-1', ghost_key: 'x' }])
    const bar = w.find('.dead-keys-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.text()).toContain('ghost_key')
    expect(bar.text()).toContain('运行无效果')
    // 软提示无阻断:新增数据可点、数据格可编辑(无 disabled)
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
    expect(addBtn!.attributes('disabled')).toBeUndefined()
    expect(w.find('input.data-cell-input').attributes('disabled')).toBeUndefined()
    w.unmount()
  })

  it('DET-4: 双用 var 重复列 key 差异化 — 同 var 输入列 + 双期望列共存,无重复键告警', async () => {
    // 全生命周期捕 console.warn:Vue 重复键在 keyed diff(更新期)冒
    // "Duplicate keys found" — 挂载后触发一次 tbody 重渲 + 弹窗渲染覆盖两面
    const warns: unknown[][] = []
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args: unknown[]) => { warns.push(args) })
    const w = await mountEditor(DEF_DUALVAR2 as any, [{ amount: '-1' }])
    // 网格:单段(无段 tabs),amount 三列并存(1 输入 + 2 同 var 期望,跳转钮 ×2)
    expect(w.findAll('.seg-tab').length).toBe(0)
    const heads = w.findAll('.row-field .th-data')
    expect(heads.length).toBe(3)
    expect(heads.filter((h) => h.text().includes('amount')).length).toBe(3)
    expect(w.findAll('.row-field .th-data .exp-jump').length).toBe(2)
    expect(w.findAll('colgroup col.col-data').length).toBe(3)
    // 数据格编辑(rows 替换 → tbody keyed diff)后行仍三列 — 键撞号会在此劣化
    await w.find('input.data-cell-input').setValue('42')
    await flushPromises()
    expect(w.findAll('.data-table tbody td.td-data').length).toBe(3)
    // 行详情:勾首行 → 预览 — 段内 3 项同名 amount(1 输入无徽标 + 2 期望徽标)
    ;(w.vm as any).toggleRow(0, true)
    await flushPromises()
    const btn = w.findAll('button').find((b) => b.text().includes('预览选中'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    const detailRows = [...document.querySelectorAll('.detail-seg .detail-row')]
    expect(detailRows.length).toBe(3)
    expect(detailRows.map((r) => r.querySelector('.detail-name')?.textContent))
      .toEqual(['amount', 'amount', 'amount'])
    expect(document.querySelectorAll('.detail-row .exp-col-badge').length).toBe(2)
    // 键差异化钉:整生命周期无 "Duplicate keys" 告警
    expect(warns.some((args) => args.some((a) => String(a).includes('Duplicate keys')))).toBe(false)
    warnSpy.mockRestore()
    w.unmount()
  })
})

describe('DataSetEditor — 老数据集兼容(旧提升流)', () => {
  it('COMPAT-1: 旧提升流数据集(rows 键=var 名,直填列存在)打开不炸,行名/TSV/三态全在', async () => {
    const w = await mountEditor(DEF_OLD_PROMOTE as any, [{ amount: '5' }, { amount: '6' }])
    // 段派生:仅 step1 一段(step2 无 ${var} 引用)→ 单段不渲染段 tabs,列作用域 = 唯一段
    expect(w.findAll('.seg-tab').length).toBe(0)
    const heads = w.findAll('.row-field .th-data').map((t) => t.text()).join()
    expect(heads).toContain('步骤1 - amount')
    expect(heads).not.toContain('remark')          // 直填列不出数据表格
    // 两行:数据名输入 ×2;amount 格值 '5'/'6'(override-value 三态正常,基线 = config.vars)
    expect(w.findAll('.data-name-input').length).toBe(2)
    const cells = w.findAll('input.data-cell-input')
    expect(cells.length).toBe(2)
    expect((cells[0].element as HTMLInputElement).value).toBe('5')
    expect((cells[1].element as HTMLInputElement).value).toBe('6')
    expect((cells[0].element as HTMLInputElement).placeholder).toBe('1')   // config.vars.amount
    expect(w.findAll('td.cell-override-value').length).toBe(2)
    // 行键 amount ∈ config.vars 列宇宙 → 无死键提示条(旧数据集不该被误报)
    expect(w.find('.dead-keys-bar').exists()).toBe(false)
    // remark 直填列退场数据表格后在基线区可编辑(SEG-4 同款展开路径)
    await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
    await flushPromises()
    const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
    for (const h of groupHeaders) await h.trigger('click')
    await flushPromises()
    const directs = w.findAll('input.baseline-direct-input')
      .map((d) => (d.element as HTMLInputElement).value)
    expect(directs).toContain('直填字面量')
    // 保存链不炸:点「保存基线」→ updateScenario 被调,rows 形状零变化
    const saveBtn = w.findAll('button').find((b) => b.text().includes('保存基线'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    expect((w.vm as any).rows).toEqual([{ amount: '5' }, { amount: '6' }])
    // TSV 粘贴链在兼容网格下照常(行键仍落 var 名)
    const evt = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(evt, 'clipboardData', { value: { getData: () => '7\n8' } })
    await cells[0].element.dispatchEvent(evt)
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: '7' }, { amount: '8' }])
    w.unmount()
  })
})
