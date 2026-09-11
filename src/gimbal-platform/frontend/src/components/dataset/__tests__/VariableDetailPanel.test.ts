/**
 * VariableDetailPanel — 数据集单变量详情面板(spec v2 §6):
 * 四段面(基线/引用面/取数/行值)+ 取数链(ValueSourcePicker 复用,
 * query_safe 过滤 → resolveQueryCtx → 行选 → 列选值 → 应用)。
 * 取数 IO 全 mock(@/api/query-views);行/基线只断言上抛不落地。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const qvMock = vi.hoisted(() => ({
  fetchQueryViewIndex: vi.fn(),
  fetchQueryViewRows: vi.fn(),
}))
vi.mock('@/api/query-views', () => qvMock)
vi.mock('vue-router', () => ({
  // @/api/http 引 @/router(模块级 createRouter)— mock 必须补全
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: vi.fn() }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import VariableDetailPanel from '@/components/dataset/VariableDetailPanel.vue'
import type { GridVarColumn } from '@/utils/dataset-segments'
import type { PanelStepContext } from '@/utils/query-context'
import { fetchQueryViewIndex, fetchQueryViewRows } from '@/api/query-views'

/** 引用位:bl_no 输入于步骤0 body;exp_code 期望于步骤1 断言(跳转载体) */
function refCols(): GridVarColumn[] {
  return [
    { varName: 'bl_no', baseline: 'BL1', stepIndex: 0, source: 'body', field: 'bl_no' },
    { varName: 'exp_code', baseline: '200', stepIndex: 1, source: 'expect', field: '$.response_body.code',
      expect: { target: '$.response_body.code', operator: 'eq', strategyIdx: 0 } },
  ]
}

/** 步骤上下文:步骤0 服务 fin + headers auth u2 引用(修订 11 首命中);
 *  步骤1 无引用。users 表:u1 同域 fin(修订 10 域内首键应是 u1,但被
 *  headers 引用 u2 压过 — PANEL-2 断言的正是这个优先序)。 */
function stepCtxs(): PanelStepContext[] {
  return [
    { index: 0, label: '下单', service: 'fin', headers: { Authorization: 'Bearer ${auth.u2.token}' }, bodyTop: { bl_no: 'BL123' } },
    { index: 1, label: '查单', service: 'ops', headers: {}, bodyTop: {} },
  ]
}

const QUERY_CONFIG = {
  services: { fin: 'http://fin.example.com', ops: 'http://ops.example.com' },
  users: {
    u1: { url: 'http://fin.example.com/login' },
    u2: { url: 'http://ops.example.com/login' },
  },
}

const IDX_SAFE = { name: 'v_orders', endpoint_id: 'e1', method: 'GET', path: '/orders', params: [], query_params: [], items: '', label: '', columns: ['name', 'bl_no', 'cost'], query_safe: true, missing_required: [] }
const IDX_UNSAFE = { ...IDX_SAFE, name: 'v_mut', query_safe: false }
const IDX_PARAMS = { ...IDX_SAFE, name: 'v_by_bl', query_params: ['bl_no'], columns: ['name', 'bl_no'] }

function mountPanel(over: Partial<InstanceType<typeof VariableDetailPanel>['$props']> = {}) {
  return mount(VariableDetailPanel, {
    props: {
      varName: 'bl_no',
      baseline: 'BL1',
      refs: refCols(),
      rows: [{ bl_no: 'BL9' }, {}],
      caseNames: ['case-a', 'case-b'],
      stepContexts: stepCtxs(),
      queryConfig: QUERY_CONFIG,
      ...over,
    } as any,
    global: { plugins: [ElementPlus] },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  qvMock.fetchQueryViewIndex.mockReset()
  qvMock.fetchQueryViewRows.mockReset()
})
afterEach(() => { vi.restoreAllMocks() })

describe('VariableDetailPanel — 四段面渲染 + emits', () => {
  it('PANEL-1: 基线/引用面/取数/行值齐;引用面含期望徽标与 ↗;行值继承态标注', async () => {
    qvMock.fetchQueryViewIndex.mockResolvedValue([IDX_SAFE])
    const w = mountPanel()
    await flushPromises()
    // 基线(值来自 props;编辑即上抛)
    const base = w.find('input[aria-label="基线 bl_no"]')
    expect((base.element as HTMLInputElement).value).toBe('BL1')
    await base.setValue('BL2')
    expect(w.emitted('set-baseline')![0]).toEqual(['BL2'])
    // 引用面:两处引用;期望引用带「期望」徽标 + ↗(emit jump 携 strategyIdx)
    const refs = w.findAll('.vdp-ref')
    expect(refs.length).toBe(2)
    expect(refs[0].text()).toContain('步骤1 · 下单')
    expect(refs[0].text()).toContain('body · bl_no')
    expect(refs[1].text()).toContain('断言 $.response_body.code')
    expect(refs[1].find('.exp-col-badge').exists()).toBe(true)
    await refs[1].find('.exp-jump').trigger('click')
    expect(w.emitted('jump')![0][0]).toMatchObject({
      varName: 'exp_code', source: 'expect', stepIndex: 1,
      expect: { strategyIdx: 0 },
    })
    // 行值:覆写/继承两态;编辑上抛 (rowIndex, value)
    const rowVals = w.findAll('.vdp-rowval')
    expect(rowVals.length).toBe(2)
    expect(rowVals[0].find('.vdp-rowval-flag').text()).toBe('覆写')
    expect(rowVals[1].find('.vdp-rowval-flag').text()).toBe('继承基线')
    const r0 = w.find('input[aria-label="case-a bl_no"]')
    expect((r0.element as HTMLInputElement).value).toBe('BL9')
    expect((w.find('input[aria-label="case-b bl_no"]').element as HTMLInputElement).placeholder).toBe('BL1')
    await r0.setValue('BL8')
    expect(w.emitted('set-cell')![0]).toEqual([0, 'BL8'])
    w.unmount()
  })
})

describe('VariableDetailPanel — 取数链(ValueSourcePicker 复用)', () => {
  it('PANEL-2: 索引 query_safe 过滤 → 默认首视图 → 查询(resolveQueryCtx:headers auth 优先)→ 行选 → 列选值 → 设为基线/写入行', async () => {
    qvMock.fetchQueryViewIndex.mockResolvedValue([IDX_UNSAFE, IDX_SAFE])
    qvMock.fetchQueryViewRows.mockResolvedValue({
      view: 'v_orders', rows: [
        { name: '上海公司', bl_no: 'BL77', cost: '99' },
        { name: '北京公司', bl_no: 'BL88', cost: '45' },
      ],
      truncated: false, fetched_at: '2026-09-11T00:00:00Z', cached: false, stale: false,
    })
    const w = mountPanel()
    await flushPromises()
    // 索引拉取 + query_safe 过滤:变更型视图被滤掉,默认 = 首 safe 视图
    expect(fetchQueryViewIndex).toHaveBeenCalledTimes(1)
    expect((w.vm as any).views.length).toBe(1)
    expect((w.vm as any).viewChoice).toBe('v_orders')
    // 步骤上下文默认 = 首引用位步骤(步骤0)
    expect((w.vm as any).stepChoice).toBe(0)
    // 查询取数 → picker 开;headers auth 引用 u2 压过域内首键 u1(修订 11)
    await w.findAll('button').find((b) => b.text().includes('查询取数'))!.trigger('click')
    await flushPromises()
    expect(fetchQueryViewRows).toHaveBeenCalledTimes(1)
    expect(fetchQueryViewRows).toHaveBeenCalledWith('v_orders', {
      refresh: false,
      serviceUrl: 'http://fin.example.com',
      queryAlias: 'u2',
    })
    expect(w.find('.vsp-overlay').exists()).toBe(true)
    // 行选(第二行)→ picker 关,列选 overlay 开
    await w.findAll('.vsp-row')[1].trigger('click')
    expect((w.vm as any).pickerOpen).toBe(false)
    expect(w.find('.vdp-chooser-overlay').exists()).toBe(true)
    // 列选值:label 列打头 + 视图列(显示的是已选的第二行);点 bl_no 列 → 取数值可再手改
    const cells = w.findAll('.vdp-chooser-cell')
    expect(cells.map((c) => c.text())).toEqual(['name北京公司', 'bl_noBL88', 'cost45'])
    await cells[1].trigger('click')
    const picked = w.find('input[aria-label="取数值 bl_no"]')
    expect((picked.element as HTMLInputElement).value).toBe('BL88')
    await picked.setValue('BL77X')
    // 设为基线 / 写入行(caseNames 下拉选择第 2 行 = index 1)
    await w.findAll('button').find((b) => b.text().includes('设为基线'))!.trigger('click')
    expect(w.emitted('set-baseline')!.at(-1)).toEqual(['BL77X'])
    ;(w.vm as any).applyRowChoice = 1
    await flushPromises()   // disabled 解除要等渲染刷新,否则 click 不派发
    await w.findAll('button').find((b) => b.text().includes('写入该行'))!.trigger('click')
    expect(w.emitted('set-cell')!.at(-1)).toEqual([1, 'BL77X'])
    w.unmount()
  })

  it('PANEL-3: 参数面视图 — 预填自步骤 body 同名字面量;携参查询(refresh 复用)', async () => {
    qvMock.fetchQueryViewIndex.mockResolvedValue([IDX_PARAMS])
    qvMock.fetchQueryViewRows.mockResolvedValue({
      view: 'v_by_bl', rows: [{ name: '上海公司', bl_no: 'BL123' }],
      truncated: false, fetched_at: '', cached: false, stale: false,
    })
    const w = mountPanel()
    await flushPromises()
    await w.findAll('button').find((b) => b.text().includes('查询取数'))!.trigger('click')
    await flushPromises()
    // 参数段先呈现(有 query_params 不直拉);预填 = 步骤0 bodyTop.bl_no
    expect(fetchQueryViewRows).not.toHaveBeenCalled()
    const paramInput = w.find('.vsp-param-row input')
    expect((paramInput.element as HTMLInputElement).value).toBe('BL123')
    await paramInput.setValue('BL555')
    await w.find('.vsp-param-query').trigger('click')
    await flushPromises()
    expect(fetchQueryViewRows).toHaveBeenCalledWith('v_by_bl', {
      refresh: false,
      serviceUrl: 'http://fin.example.com',
      queryAlias: 'u2',
      params: { bl_no: 'BL555' },
    })
    // 行选 → 列选(name 列)→ 取数值
    await w.findAll('.vsp-row')[0].trigger('click')
    await w.findAll('.vdp-chooser-cell')[0].trigger('click')
    expect((w.find('input[aria-label="取数值 bl_no"]').element as HTMLInputElement).value).toBe('上海公司')
    w.unmount()
  })

  it('PANEL-4: 索引加载失败 → 错误态 + 重试;空索引 → 空态文案', async () => {
    qvMock.fetchQueryViewIndex.mockRejectedValueOnce(new Error('boom'))
    const w = mountPanel()
    await flushPromises()
    expect(w.find('.vdp-error').exists()).toBe(true)
    expect(w.find('.vdp-error').text()).toContain('boom')
    // 查询取数被禁(无可用视图)
    const qbtn = w.findAll('button').find((b) => b.text().includes('查询取数'))!
    expect(qbtn.attributes('disabled')).toBeDefined()
    // 重试 → 成功 → 错误态清空
    qvMock.fetchQueryViewIndex.mockResolvedValue([IDX_SAFE])
    await w.find('.vdp-error .vdp-linkbtn').trigger('click')
    await flushPromises()
    expect(w.find('.vdp-error').exists()).toBe(false)
    // 空索引态(独立挂载:未引用提示 + 无可取数视图文案)
    qvMock.fetchQueryViewIndex.mockResolvedValue([])
    const w2 = mountPanel({ refs: [] })
    await flushPromises()
    expect(w2.text()).toContain('无 query-safe 查询视图可取数')
    expect(w2.text()).toContain('未被引用')
    w.unmount()
    w2.unmount()
  })
})
