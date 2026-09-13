/**
 * CaseDataSetsList — 测试数据页双区(spec v3 §5):
 * - DSL-1 同页双区,两区**各用其形**:数据集 = 卡片网格(可打开的资产),
 *   断言条目 = 紧凑表格(字段齐整的配置记录,一条一行)
 * - DSL-2 数据集卡「运行」→ RunPanelHost 挂载且 preset = 整库单选
 * - DSL-3 条目标题行点击 → 跳断言管理编辑器(编辑入口搬家至测试数据页)
 * - DSL-4 契约在途 → 契约依赖条目**不**标悬空(pending ≠ 判死)
 * - DSL-5 数据集卡预览 = 列清单(字段名定宽 + 该列取值),行/列截断都显式标出
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-td' } }),
  useRouter: () => ({ push: pushMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import CaseDataSetsList from '@/views/CaseDataSetsList.vue'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import { scenarioAssertionsUrl } from '@/utils/links'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-td', meta: { name: 'td' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-1', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-dead', name: '悬空',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ],
}

/** 单条数据集(无预览行)—— 默认夹具;DSL-5 自备带预览的一份 */
const DS_ONE = { datasetId: 'ds-1', scenarioId: 'sc-td', name: '正负流', rowCount: 2, preview: [] }

const storeMock = vi.hoisted(() => ({
  dataSetsStatus: 'idle',
  dataSetsOfScenario: vi.fn(),
  fetchDataSets: vi.fn(async () => {}),
  removeDataSet: vi.fn(async () => {}),
}))
vi.mock('@/stores/scenario-composer', () => ({
  useScenarioComposerStore: () => storeMock,
}))

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.push.mockReset()
  storeMock.dataSetsOfScenario.mockReset()
  storeMock.dataSetsOfScenario.mockReturnValue([DS_ONE])
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG } as any)
})
afterEach(() => { vi.restoreAllMocks() })

async function mountList() {
  const w = mount(CaseDataSetsList, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it('DSL-1: 双区各用其形 — 数据集卡片网格 + 断言条目紧凑表格(path/悬空/旧版)', async () => {
  const w = await mountList()
  expect(w.find('.page-title').text()).toContain('测试数据')

  // 区标题 + 数量徽章
  expect(w.findAll('.zone-name').map((n) => n.text())).toEqual(['数据集', '断言条目'])
  expect(w.findAll('.zone-count').map((n) => n.text())).toEqual(['1', '3'])

  // 区一:数据集 = 卡片(不是表格)
  expect(w.findAll('.ds-card')).toHaveLength(1)

  // 区二:断言条目 = 表格,一条一行
  const rows = w.findAll('.atbl-row')
  expect(rows).toHaveLength(3)

  const cells = (i: number) => rows[i].findAll('td').map((td) => td.text())
  expect(cells(0)).toEqual(['金额为负', '1', '$.amount', '-1', '0 条', ''])
  expect(rows[0].classes()).not.toContain('is-dead')       // 活条目不灰

  expect(cells(1).slice(0, 4)).toEqual(['悬空', '10', '$.x', '1'])
  expect(rows[1].classes()).toContain('is-dead')           // 悬空灰
  expect(cells(1)[5]).toBe('不进运行')                      // 状态列说明死因

  expect(rows[2].classes()).toContain('is-dead')           // 旧版灰
  expect(cells(2)).toEqual(['旧版条目', '—', '旧版条目,请重建', '—', '0 条', '旧版'])
  w.unmount()
})

it('DSL-2: 数据集卡「运行」→ RunPanelHost 挂载且 preset = 整库单选', async () => {
  const w = await mountList()
  expect(w.findComponent(RunPanelHost).exists()).toBe(false)
  await w.findAll('button').find((b) => b.text() === '运行')!.trigger('click')
  await flushPromises()
  const panel = w.findComponent(RunPanelHost)
  expect(panel.exists()).toBe(true)
  expect(panel.props('scenarioId')).toBe('sc-td')
  expect(panel.props('preset')).toEqual({ dataSetSelection: [{ datasetId: 'ds-1' }] })
  w.unmount()
})

it('DSL-3: 条目行点击 → 跳断言管理编辑器并带上**该行自己的** id(聚焦单条)', async () => {
  const w = await mountList()
  await w.findAll('.atbl-row')[0].trigger('click')
  expect(pushMock.push).toHaveBeenCalledWith(scenarioAssertionsUrl('sc-td', 'inj-1'))
  pushMock.push.mockReset()
  await w.findAll('.atbl-row')[1].trigger('click')
  expect(pushMock.push).toHaveBeenCalledWith(scenarioAssertionsUrl('sc-td', 'inj-dead'))
  w.unmount()
})

it('DSL-3b: 区标题「管理断言」与空列表的「去新建一条」→ 不带 id(全量视图,不是聚焦)', async () => {
  // 与 DSL-3 配对:两条入口都不该指向某一条 —— 带上 id 会落进一个
  // 无来由的聚焦态,用户就看不到列表了。
  const w = await mountList()
  await w.findAll('button').find((b) => b.text().includes('管理断言'))!.trigger('click')
  expect(pushMock.push).toHaveBeenCalledWith(scenarioAssertionsUrl('sc-td'))
  w.unmount()
})

it('DSL-4: 契约在途 → 契约依赖条目**不**标悬空(pending ≠ 判死),intrinsic 照常标;落定后按实际结果标', async () => {
  // 展示面与运行面板同口径(读 composable 的门控后死集):同一页里
  // 「能不能勾」与「标不标悬空」必须说同一句话 —— 契约未落定时那批条目
  // 不是"悬空",是"还没答案"。
  const { _resetEndpointFullCacheForTest } = await import('@/composables/useEndpointFull')
  _resetEndpointFullCacheForTest()
  const def = structuredClone(DEF) as any
  def.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-gate' } }
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
    definition: def,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-oob', name: '越界', path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
      { id: 'inj-carry', name: '契约依赖', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
    ] },
  } as any)
  let release: (v: unknown) => void = () => {}
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise((res) => { release = res }) as any)

  const w = await mountList()
  const rows = () => w.findAll('.atbl-row')
  expect(rows()[0].classes()).toContain('is-dead')        // intrinsic(step-oob):恒标
  expect(rows()[1].classes()).not.toContain('is-dead')    // 契约依赖:在途 ⇒ 尚未判定
  release({ id: 'ep-gate', request: { declarations: [] } })   // 声明面无此字段 ⇒ 有答案了
  await flushPromises()
  expect(rows()[1].classes()).toContain('is-dead')        // 落定 ⇒ 按实际结果标
  w.unmount()
})

it('DSL-5: 卡片预览 = 列清单(字段名定宽 + 该列取值);行/列截断都显式标出', async () => {
  storeMock.dataSetsOfScenario.mockReturnValue([{
    datasetId: 'ds-2', scenarioId: 'sc-td', name: '边界 amount 集',
    rowCount: 12,
    preview: [
      { amount: 0, channel: 'APP', orderNo: 'ORD-0001', remark: '零值', extra: 'x' },
      { amount: 1, channel: 'APP', orderNo: 'ORD-0002', remark: '最小值', extra: 'y' },
      { amount: 999, channel: 'H5', orderNo: 'ORD-0003', remark: '接近上限', extra: 'z' },
    ],
  }])
  const w = await mountList()

  const rows = w.findAll('.pv tbody tr')
  expect(rows).toHaveLength(4)                                   // 5 列 → 截到上限 4
  expect(rows.map((r) => r.find('th').text()))
    .toEqual(['amount', 'channel', 'orderNo', 'remark'])
  expect(rows[0].find('td').text()).toBe('0 · 1 · 999 …')
  // 尾缀判据是**整库行数** > 预览行数(后端 preview 上限 3 行),故每列都带 …
  expect(rows[3].find('td').text()).toBe('零值 · 最小值 · 接近上限 …')

  expect(w.find('.pv-more').text()).toBe('…另 1 个字段')          // 被截掉的列不能不说
  expect(w.find('.ds-card .row-count').text()).toBe('12 条')
  w.unmount()
})

it('DSL-6: 行数与列数都没超上限 ⇒ 既不出现 … 尾缀,也不出现「另 N 个字段」', async () => {
  // DSL-5 的反面:两条截断判据都必须能"静默",否则 DSL-5 的 … / 另 N 个字段
  // 可能只是恒定渲染,而不是真的在判截断。
  storeMock.dataSetsOfScenario.mockReturnValue([{
    datasetId: 'ds-3', scenarioId: 'sc-td', name: '整库',
    rowCount: 3,
    preview: [
      { a: '1', b: 'x' }, { a: '2', b: 'y' }, { a: '3', b: 'z' },
    ],
  }])
  const w = await mountList()

  const rows = w.findAll('.pv tbody tr')
  expect(rows).toHaveLength(2)
  expect(rows[0].find('td').text()).toBe('1 · 2 · 3')            // 3 行 = 预览行数 ⇒ 无尾缀
  expect(w.find('.pv-more').exists()).toBe(false)                // 2 列 < 上限 ⇒ 无提示
  w.unmount()
})
