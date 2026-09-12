/**
 * CaseDataSetsList — 测试数据页双区(spec v3 §5):
 * - DSL-1 同页双区:数据集卡片网格(store)与断言条目卡片网格
 *   (getScenarioDraft + normalizeRegistry)同屏;v3 条目带 path 徽标,
 *   悬空灰;旧版条目灰显「旧版条目,请重建」不可执行
 * - DSL-2 数据集卡「运行」→ RunPanelHost 挂载且 preset = 整库单选
 * - DSL-3 条目卡点击 → 跳断言管理编辑器(编辑入口搬家至测试数据页)
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

const storeMock = vi.hoisted(() => ({
  dataSetsStatus: 'idle',
  dataSetsOfScenario: () => [
    { datasetId: 'ds-1', scenarioId: 'sc-td', name: '正负流', rowCount: 2, preview: [] },
  ],
  fetchDataSets: vi.fn(async () => {}),
  removeDataSet: vi.fn(async () => {}),
}))
vi.mock('@/stores/scenario-composer', () => ({
  useScenarioComposerStore: () => storeMock,
}))

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.push.mockReset()
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG } as any)
})
afterEach(() => { vi.restoreAllMocks() })

async function mountList() {
  const w = mount(CaseDataSetsList, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it('DSL-1: 测试数据页双区 — 数据集网格 + 断言条目网格(path 徽标/悬空灰/旧版灰)', async () => {
  const w = await mountList()
  expect(w.find('.page-title').text()).toContain('测试数据')
  expect(w.findAll('.card:not(.add-card):not(.td-entry)')).toHaveLength(1)   // 数据集区(条目区排除)
  const entryCards = w.findAll('.td-entry')
  expect(entryCards).toHaveLength(3)
  expect(entryCards[0].text()).toContain('金额为负')
  expect(entryCards[0].text()).toContain('步骤1 · $.amount')          // path 徽标
  expect(entryCards[0].classes()).not.toContain('is-dead')            // 活条目不灰(stepCount=0 会全灰 → 此处兜底)
  expect(entryCards[1].classes()).toContain('is-dead')                // 悬空灰
  expect(entryCards[2].classes()).toContain('is-dead')                // 旧版灰
  expect(entryCards[2].text()).toContain('旧版条目,请重建')
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

it('DSL-3: 条目卡点击 → 跳断言管理编辑器', async () => {
  const w = await mountList()
  await w.findAll('.td-entry')[0].trigger('click')
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
  const cards = () => w.findAll('.td-entry')
  expect(cards()[0].classes()).toContain('is-dead')        // intrinsic(step-oob):恒标
  expect(cards()[1].classes()).not.toContain('is-dead')    // 契约依赖:在途 ⇒ 尚未判定
  release({ id: 'ep-gate', request: { declarations: [] } })   // 声明面无此字段 ⇒ 有答案了
  await flushPromises()
  expect(cards()[1].classes()).toContain('is-dead')        // 落定 ⇒ 按实际结果标
  w.unmount()
})
