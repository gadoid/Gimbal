/**
 * RunPanelHost — 运行面板宿主(spec v3 §6):两个执行入口共用的装配层。
 * - RH-1 自取数装配:getScenario + getScenarioDraft + listDataSets → RunDialog
 *   挂载,assertionEntries/deadEntryIds(含 legacy)透传
 * - RH-2 confirm → runScenario(dataSetIds 派生 + dataSetSelection 权威键)
 *   → 跳执行详情
 * - RH-3 saveScheme → putRunSchemes(scenarioId, 整表)
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock.push }),
  useRoute: () => ({ params: { scenarioId: 'sc-host' } }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('@/api/auth_sessions', () => ({ list: async () => [{ alias: 'owner-1' }] }))

import * as api from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import { executionUrl } from '@/utils/links'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-host', meta: { name: 'host' },
  config: { vars: { amount: 100 }, services: { 'fin.test': 'http://fin' }, users: {} },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: {} }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-live', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ],
}
const DRAFT = {
  definition: DEF,
  orchestration: { steps: [{ name: '下单', enabled: true }, { name: '查单', enabled: true }], resourceMeta: {}, runSchemes: [] },
  assertion_registry: REG,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenario').mockResolvedValue(
    { meta: { scenarioId: 'sc-host', name: 'host' }, steps: DEF.steps, stepCount: 2 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'listDataSets').mockResolvedValue([
    { datasetId: 'ds-1', scenarioId: 'sc-host', name: 'A', rowCount: 2, preview: [] }] as any)
  vi.spyOn(api, 'runScenario').mockResolvedValue({ runId: 'r-1', executionId: 7 } as any)
  vi.spyOn(api, 'putRunSchemes').mockResolvedValue([] as any)
  pushMock.push.mockReset()
})
afterEach(() => { vi.restoreAllMocks() })

async function mountHost(props: Record<string, unknown> = {}) {
  const w = mount(RunPanelHost, {
    props: { scenarioId: 'sc-host', ...props } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
  await flushPromises()
  return w
}

it('RH-1: 自取数装配 — RunDialog 挂载 + 条目/死条目透传(legacy 入 deadEntryIds)', async () => {
  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.exists()).toBe(true)
  expect(dlg.props('assertionEntries')).toHaveLength(2)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-old'])   // legacy 恒死(isDeadEntry)
  expect(dlg.props('preset')).toBeNull()
  expect(dlg.props('serviceRows')).toEqual([{ service: 'fin.test', declaredUrl: 'http://fin' }])
  expect(dlg.props('stepOrchestrationNames')).toEqual(['下单', '查单'])
  w.unmount()
})

it('RH-2: confirm → runScenario 携带 dataSetSelection 权威键 → 跳执行详情', async () => {
  const w = await mountHost({
    preset: { dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }], injectionEntryIds: ['inj-live'] },
  })
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('preset')).toEqual({
    dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }],
    injectionEntryIds: ['inj-live'],
  })
  dlg.vm.$emit('confirm', [{ datasetId: 'ds-1', rowIndexes: [1] }], { injectionEntryIds: ['inj-live'] })
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.scenarioId).toBe('sc-host')
  expect(body.dataSetIds).toEqual(['ds-1'])
  expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
  expect(body.injectionEntryIds).toEqual(['inj-live'])
  expect(w.emitted('close')).toBeTruthy()
  expect(pushMock.push).toHaveBeenCalledWith(executionUrl(7))
  w.unmount()
})

it('RH-2b: 空选 confirm → 省略 dataSetSelection 键 + dataSetIds 空数组', async () => {
  // 无数据集(基线运行)是合法路径:权威键 dataSetSelection 不下送
  // (spec v3 §4 空选 = 基线),兼容键 dataSetIds 仍送空数组。
  vi.mocked(api.listDataSets).mockResolvedValue([])
  const w = await mountHost()
  await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.dataSetIds).toEqual([])
  expect('dataSetSelection' in body).toBe(false)
  w.unmount()
})

it('RH-3: saveScheme → putRunSchemes(scenarioId, 整表含新方案)', async () => {
  const w = await mountHost()
  const scheme = { name: '回归', dataSetIds: [], dataSetSelection: [], injectionEntryIds: ['inj-live'], serviceBindings: {} }
  w.findComponent(RunDialog).vm.$emit('saveScheme', scheme)
  await flushPromises()
  expect(api.putRunSchemes).toHaveBeenCalledWith('sc-host', [scheme])
  w.unmount()
})
